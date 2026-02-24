from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import joblib
import pandas as pd
import numpy as np
import psycopg2
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="RedBlue Oracle API")

# Load DB Config
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "postgres"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password")
}

# --- Load Model Initialization ---
MODEL_PATH = "src/modeling/xgboost_model.joblib"
FEATURES_PATH = "src/modeling/xgboost_model_features.txt"

model = None
feature_columns = []

@app.on_event("startup")
def load_artifacts():
    global model, feature_columns
    try:
        model = joblib.load(MODEL_PATH)
        print(f"Loaded XGBoost model from {MODEL_PATH}")
        
        with open(FEATURES_PATH, "r") as f:
            feature_columns = [line.strip() for line in f.read().splitlines() if line.strip()]
        print(f"Loaded {len(feature_columns)} expected feature columns.")
    except Exception as e:
        print(f"Warning: Could not load model or features. Error: {e}")

# --- API Payloads ---
class PredictionRequest(BaseModel):
    stop_id: str
    route_id: str
    direction_id: int # 0 or 1

# --- Helper Functions ---
def get_latest_live_features(stop_id: str, route_id: str):
    """Hits the DB to get the most recent weather snapshot, congestion, headway, and upstream delay."""
    conn = psycopg2.connect(**DB_CONFIG)
    
    # 1. Latest Weather
    weather_query = "SELECT temp, precip_mm, wind_speed FROM weather_logs ORDER BY timestamp DESC LIMIT 1;"
    df_weather = pd.read_sql(weather_query, conn)
    
    # Defaults in case DB is completely empty
    temp = df_weather['temp'].iloc[0] if not df_weather.empty else 15.0
    precip_mm = df_weather['precip_mm'].iloc[0] if not df_weather.empty else 0.0
    wind_speed = df_weather['wind_speed'].iloc[0] if not df_weather.empty else 5.0
    
    # 2. Rolling Congestion and Upstream Delay (Simulated via recent line performance)
    # We query the last 5 trains on this specific route that reached any stopped status.
    performance_query = """
    SELECT 
        vp.stop_id,
        vp.timestamp AS actual_timestamp, 
        st.arrival_time AS scheduled_arrival
    FROM vehicle_positions vp
    LEFT JOIN stop_times st ON vp.trip_id = st.trip_id AND vp.stop_id = st.stop_id
    LEFT JOIN trips t ON vp.trip_id = t.trip_id
    WHERE t.route_id = %s AND vp.current_status = 'STOPPED_AT'
    ORDER BY vp.timestamp DESC LIMIT 5;
    """
    
    congestion = 0.0 # line congestion
    upstream_delay = 0.0 # general upstream delay
    headway_minutes = 10.0 # default reasonable headway
    
    with conn.cursor() as cur:
        cur.execute(performance_query, (route_id,))
        rows = cur.fetchall()
        
        delays = []
        last_seen_at_station = None
        
        for s_id, actual, sched in rows:
            # Headway: Find the most recent time ANY train was at THIS requested station
            if s_id == stop_id and last_seen_at_station is None:
                last_seen_at_station = actual
                
            if actual and sched:
                try:
                    h, m, s = map(int, str(sched).split(':'))
                    days_add = 0
                    if h >= 24:
                        h -= 24
                        days_add = 1
                        
                    base_date = actual.date() + pd.Timedelta(days=days_add)
                    base_time = pd.Timestamp(f"{base_date} {h:02d}:{m:02d}:{s:02d}")
            
                    candidates = [
                        base_time - pd.Timedelta(days=1),
                        base_time,
                        base_time + pd.Timedelta(days=1)
                    ]
            
                    # Find candidate scheduled timestamp closest to actual ping
                    best_diff = float('inf')
                    best_candidate = pd.NaT
                    for cand in candidates:
                        diff = abs((actual - cand).total_seconds())
                        if diff < best_diff:
                            best_diff = diff
                            best_candidate = cand

                    if not pd.isna(best_candidate):
                        delay_minutes = (actual - best_candidate).total_seconds() / 60.0
                        
                        # Only accept if realistically a delay (not an orphaned train artifact measuring 48 hours)
                        if abs(delay_minutes) < 300: 
                            delays.append(delay_minutes)
                except Exception:
                    pass
                    
        if delays:
            # We approximate rolling line congestion as the average of the last 3 seen
            congestion = sum(delays[:3]) / len(delays[:3]) if len(delays) >= 3 else sum(delays) / len(delays)
            # We approximate rolling upstream delay as the average of the last 2 seen
            upstream_delay = sum(delays[:2]) / len(delays[:2]) if len(delays) >= 2 else sum(delays) / len(delays)
            
        if last_seen_at_station:
            # Calculate exactly how many minutes have elapsed since the previous train left this exact stop
            elapsed = (datetime.now() - last_seen_at_station).total_seconds() / 60.0
            # Cap headway to prevent extreme outliers if the DB wasn't updated overnight
            headway_minutes = min(elapsed, 120.0)
            
    conn.close()
    return temp, precip_mm, wind_speed, congestion, headway_minutes, upstream_delay

# --- Routes ---
@app.get("/")
def health_check():
    return {"status": "healthy", "model_loaded": model is not None}

@app.post("/predict")
def predict_delay(req: PredictionRequest):
    if model is None:
        raise HTTPException(status_code=500, detail="Model is not loaded.")
        
    now = datetime.now()
    
    # 1. Fetch real-time live data block
    temp, precip_mm, wind_speed, congestion, headway_minutes, upstream_delay = get_latest_live_features(req.stop_id, req.route_id)
    
    # 2. Build explicit Feature Vector
    # Temporal
    hour = now.hour
    day_of_week = now.weekday()
    is_weekend = 1 if day_of_week in [5, 6] else 0
    is_rush_hour = 1 if ((hour >= 7 and hour <= 9) or (hour >= 16 and hour <= 18)) else 0
    
    feature_dict = {
        'hour_of_day': hour,
        'day_of_week': day_of_week,
        'is_weekend': is_weekend,
        'is_rush_hour': is_rush_hour,
        'temp': temp,
        'precip_mm': precip_mm,
        'wind_speed': wind_speed,
        'rolling_congestion_3_trains': congestion,
        'headway_minutes': headway_minutes,
        'rolling_upstream_delay': upstream_delay
    }
    
    # Ensure ordered and exactly matching the training feature columns.
    # Set categorical OHE variables to 0 if missing.
    target_route = f"route_id_{req.route_id}"
    target_dir = f"direction_id_{float(req.direction_id)}"
    
    # Check if the requested route even exists in the training data (currently just Blue/Red)
    # If not, fallback to the first active route to prevent the model from seeing ALL zeros.
    route_columns = [c for c in feature_columns if c.startswith('route_id_')]
    if target_route not in route_columns and len(route_columns) > 0:
        target_route = route_columns[0]
    
    # Build array
    input_array = []
    for col in feature_columns:
        if col in feature_dict:
            input_array.append(feature_dict[col])
        elif col == target_route:
            input_array.append(1.0)
        elif col == target_dir:
            input_array.append(1.0)
        elif col.startswith('route_id_') or col.startswith('direction_id_'):
            input_array.append(0.0)
        else:
            # Fallback numeric default
            input_array.append(0.0)
            
    # Formulate row
    X_pred = pd.DataFrame([input_array], columns=feature_columns)
    
    # Predict
    predicted_delay = float(model.predict(X_pred)[0])
    
    return {
        "scheduled_baseline": 0.0,
        "predicted_delay": round(predicted_delay, 2),
        "features_used": {
            "temp": round(temp, 1),
            "wind": round(wind_speed, 1),
            "line_congestion": round(congestion, 2),
            "is_rush_hour": bool(is_rush_hour),
            "headway_minutes": round(headway_minutes, 1),
            "upstream_delay": round(upstream_delay, 2)
        }
    }
