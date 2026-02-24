import streamlit as st
import psycopg2
import pandas as pd
import os
import joblib
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

MODEL_PATH = "src/modeling/xgboost_model.joblib"
FEATURES_PATH = "src/modeling/xgboost_model_features.txt"

@st.cache_resource
def load_model():
    model = joblib.load(MODEL_PATH)
    with open(FEATURES_PATH, "r") as f:
        feature_columns = [line.strip() for line in f.read().splitlines() if line.strip()]
    return model, feature_columns

try:
    model, feature_columns = load_model()
except Exception as e:
    st.error(f"Failed to load ML model: {e}")
    model, feature_columns = None, []

st.set_page_config(
    page_title="RedBlue Oracle",
    page_icon="🚇",
    layout="wide",
)

# Custom CSS for modern premium look
st.markdown("""
    <style>
    .metric-value {
        font-size: 3rem;
        font-weight: 800;
        color: #1a73e8;
    }
    .baseline-value {
        font-size: 2rem;
        font-weight: 600;
        text-decoration: line-through;
        color: #d93025;
    }
    .hero-container {
        padding: 2rem;
        border-radius: 12px;
        background: linear-gradient(135deg, #f1f3f4 0%, #e8eaed 100%);
        border: 1px solid #dadce0;
        margin-bottom: 2rem;
    }
    .dark .hero-container {
        background: linear-gradient(135deg, #202124 0%, #303134 100%);
        border: 1px solid #3c4043;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🚇 RedBlue Oracle")
st.markdown("**Real-Time Machine Learning predictions for Boston's MBTA system.**")
st.markdown("We ingest live vehicle positions, weather telemetry, and historical schedules to beat the MBTA's official predictions.")

st.divider()

col1, col2, col3 = st.columns(3)

# Load DB Config
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "postgres"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password")
}

def get_latest_live_features(stop_id: str, route_id: str):
    """Hits the DB to get the most recent weather snapshot, congestion, headway, and upstream delay."""
    conn = psycopg2.connect(**DB_CONFIG)
    
    weather_query = "SELECT temp, precip_mm, wind_speed FROM weather_logs ORDER BY timestamp DESC LIMIT 1;"
    df_weather = pd.read_sql(weather_query, conn)
    
    temp = df_weather['temp'].iloc[0] if not df_weather.empty else 15.0
    precip_mm = df_weather['precip_mm'].iloc[0] if not df_weather.empty else 0.0
    wind_speed = df_weather['wind_speed'].iloc[0] if not df_weather.empty else 5.0
    
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
    
    congestion = 0.0 
    upstream_delay = 0.0 
    headway_minutes = 10.0 
    
    with conn.cursor() as cur:
        cur.execute(performance_query, (route_id,))
        rows = cur.fetchall()
        
        delays = []
        last_seen_at_station = None
        
        for s_id, actual, sched in rows:
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
            
                    best_diff = float('inf')
                    best_candidate = pd.NaT
                    for cand in candidates:
                        diff = abs((actual - cand).total_seconds())
                        if diff < best_diff:
                            best_diff = diff
                            best_candidate = cand

                    if pd.notna(best_candidate):
                        delay_minutes = (actual - best_candidate).total_seconds() / 60.0
                        if abs(delay_minutes) < 300: 
                            delays.append(delay_minutes)
                except Exception:
                    pass
                    
        if delays:
            congestion = sum(delays[:3]) / len(delays[:3]) if len(delays) >= 3 else sum(delays) / len(delays)
            upstream_delay = sum(delays[:2]) / len(delays[:2]) if len(delays) >= 2 else sum(delays) / len(delays)
            
        if last_seen_at_station:
            elapsed = (datetime.now() - last_seen_at_station).total_seconds() / 60.0
            headway_minutes = min(elapsed, 120.0)
            
    conn.close()
    return temp, precip_mm, wind_speed, congestion, headway_minutes, upstream_delay

@st.cache_data(ttl=3600)
def get_routed_station_mapping():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        # Fetch station names mapping to stop IDs, grouped by route_id
        # We join stops -> stop_times -> trips to guarantee we only show stops active on the selected line
        query = """
        SELECT t.route_id, s.stop_name, s.stop_id 
        FROM stops s 
        JOIN stop_times st ON s.stop_id = st.stop_id 
        JOIN trips t ON st.trip_id = t.trip_id 
        WHERE t.route_id IN ('Blue', 'Red') 
        GROUP BY t.route_id, s.stop_name, s.stop_id 
        ORDER BY t.route_id, s.stop_name;
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Failed to connect to Database: {e}")
        return pd.DataFrame() # empty fallback

df_stations = get_routed_station_mapping()

# Our ML model is strictly trained on Blue and Red lines due to MBTA schedule availability constraints
lines = ["Blue", "Red"]

with col1:
    selected_line = st.selectbox("Subway Line", options=lines, index=0)

# Dynamically filter the stations based on the selected line
if not df_stations.empty:
    line_df = df_stations[df_stations['route_id'] == selected_line]
    
    # We drop duplicates on stop_name so the UI dropdown doesn't show "Government Center" twice
    # Even if there are multiple physical platforms (stop_ids) for it on that line. Usually the first is fine for the rough predictor.
    line_df = line_df.drop_duplicates(subset=['stop_name'], keep='first')
    station_map = dict(zip(line_df['stop_name'], line_df['stop_id']))
else:
    station_map = {"Park Street": "place-park"} # Hard fallback

station_names = list(station_map.keys())

with col2:
    selected_dir = st.selectbox("Direction", options=["Inbound (0)", "Outbound (1)"])
    direction_id = 0 if "Inbound" in selected_dir else 1
with col3:
    # Display human-readable names
    selected_station_name = st.selectbox("Station", options=station_names)
    # Grab the actual GTFS stop_id for the model
    selected_station_id = station_map.get(selected_station_name)

if st.button("🔮 Generate Oracle Prediction", type="primary", use_container_width=True):
    if model is None:
        st.error("ML Model is currently unavailable. Please check the logs.")
    else:
        with st.spinner("Querying Live Telemetry & Model Weights..."):
            try:
                now = datetime.now()
                
                # Fetch live data block from DB
                temp, precip_mm, wind_speed, congestion, headway_minutes, upstream_delay = get_latest_live_features(selected_station_id, selected_line)
                
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
                
                target_route = f"route_id_{selected_line}"
                target_dir = f"direction_id_{float(direction_id)}"
                
                route_columns = [c for c in feature_columns if c.startswith('route_id_')]
                if target_route not in route_columns and len(route_columns) > 0:
                    target_route = route_columns[0]
                
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
                        input_array.append(0.0)
                        
                X_pred = pd.DataFrame([input_array], columns=feature_columns)
                predicted = float(model.predict(X_pred)[0])
                predicted = round(predicted, 2)
                baseline = 0.0

                st.markdown("<div class='hero-container'>", unsafe_allow_html=True)
                
                m1, m2 = st.columns(2)
                
                with m1:
                    st.markdown("### ❌ MBTA Official Predict")
                    st.markdown(f"<span class='baseline-value'>{baseline} min</span><br><br><small><i>Assumes perfect schedule adherence.</i></small>", unsafe_allow_html=True)
                
                with m2:
                    st.markdown("### 🔴🔵 RedBlue Oracle")
                    
                    # Highlight color changes based on delay severity
                    color = "#1a73e8" # default blue
                    if predicted > 5:
                        color = "#f29900" # yellow
                    if predicted > 10:
                        color = "#d93025" # red
                        
                    st.markdown(f"<span class='metric-value' style='color:{color}'>+{predicted} min</span><br><br><small><i>Powered by XGBoost context modeling.</i></small>", unsafe_allow_html=True)
                    
                st.markdown("</div>", unsafe_allow_html=True)
                
                # Context Expanders
                with st.expander("Telemetry Context Log"):
                    st.write(f"⏱️ **Last Train Headway:** {round(headway_minutes, 1)} min ago")
                    st.write(f"🛤️ **Rolling Upstream Delay:** {round(upstream_delay, 2)} min delay")
                    st.write(f"🚆 **Rolling Line Congestion:** {round(congestion, 2)} min delay avg")
                    st.write("---")
                    st.write(f"🌡️ **Temperature:** {round(temp, 1)} °C")
                    st.write(f"💨 **Wind:** {round(wind_speed, 1)} km/h")
                    st.write(f"🏢 **Rush Hour Penalty Active:** {bool(is_rush_hour)}")

            except Exception as e:
                st.error(f"Unexpected error predicting delay: {e}")
