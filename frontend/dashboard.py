import streamlit as st
import requests
import psycopg2
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

API_URL = "http://localhost:8000/predict"

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
    with st.spinner("Querying Live Telemetry & Model Weights..."):
        try:
            payload = {
                "stop_id": selected_station_id,
                "route_id": selected_line,
                "direction_id": direction_id
            }
            res = requests.post(API_URL, json=payload, timeout=5)
            
            if res.status_code == 200:
                data = res.json()
                baseline = data["scheduled_baseline"]
                predicted = data["predicted_delay"]
                features = data["features_used"]
                
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
                    st.write(f"⏱️ **Last Train Headway:** {features.get('headway_minutes', 'N/A')} min ago")
                    st.write(f"🛤️ **Rolling Upstream Delay:** {features.get('upstream_delay', 'N/A')} min delay")
                    st.write(f"🚆 **Rolling Line Congestion:** {features.get('line_congestion', 0.0)} min delay avg")
                    st.write("---")
                    st.write(f"🌡️ **Temperature:** {features.get('temp', 15.0)} °C")
                    st.write(f"💨 **Wind:** {features.get('wind', 5.0)} km/h")
                    st.write(f"🏢 **Rush Hour Penalty Active:** {features.get('is_rush_hour', False)}")
            
            else:
                st.error(f"Backend Error: {res.text}")
                
        except requests.exceptions.ConnectionError:
            st.error("Cannot connect to FastAPI backend. Ensure you ran `uvicorn src.api.app:app --reload` in another terminal.")
        except Exception as e:
            st.error(f"Unexpected error: {e}")
