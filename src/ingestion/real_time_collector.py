import os
import requests
import json
import psycopg2
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

MBTA_API_KEY = os.getenv("MBTA_API_KEY")
MBTA_BASE_URL = "https://api-v3.mbta.com"

# DB Config
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "greenline_oracle"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password")
}

def get_vehicle_positions(retries=3, backoff=2):
    """Fetches real-time vehicle positions from MBTA API with retry logic."""
    url = f"{MBTA_BASE_URL}/vehicles"
    headers = {"x-api-key": MBTA_API_KEY} if MBTA_API_KEY else {}
    params = {"filter[route_type]": "0,1"}
    
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json().get('data', [])
        except requests.exceptions.RequestException as e:
            print(f"[Warning] MBTA API Attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(backoff ** attempt)
            else:
                print("[Error] Max retries reached for MBTA API.")
                return []

def get_weather(retries=3, backoff=2):
    """Fetches real-time weather from Open-Meteo with retry logic."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 42.3601,
        "longitude": -71.0589,
        "current_weather": "true"
    }
    
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json().get('current_weather', {})
        except requests.exceptions.RequestException as e:
            print(f"[Warning] Weather API Attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(backoff ** attempt)
            else:
                print("[Error] Max retries reached for Weather API.")
                return {}

def log_data_to_db(vehicles, weather):
    """Writes fetched data to the database with transaction safety."""
    if not vehicles and not weather:
        print("[Warning] No data to log.")
        return

    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        timestamp = datetime.now()
        
        # Log Weather
        if weather:
            cur.execute(
                "INSERT INTO weather_logs (timestamp, temp, precip_mm, wind_speed) VALUES (%s, %s, %s, %s)",
                (timestamp, weather.get('temperature'), weather.get('precipitation', 0.0), weather.get('windspeed'))
            )
        
        # Log Vehicles (Bulkish/Loop insertion inside single transaction)
        for v in vehicles:
            attrs = v.get('attributes', {})
            rels = v.get('relationships', {})
            
            trip_id = rels.get('trip', {}).get('data', {}).get('id') if rels.get('trip', {}).get('data') else None
            stop_id = rels.get('stop', {}).get('data', {}).get('id') if rels.get('stop', {}).get('data') else None
            
            cur.execute(
                """INSERT INTO vehicle_positions 
                   (vehicle_id, trip_id, stop_id, current_status, timestamp, lat, lon) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    v.get('id'),
                    trip_id,
                    stop_id,
                    attrs.get('current_status'),
                    timestamp,
                    attrs.get('latitude'),
                    attrs.get('longitude')
                )
            )
        
        conn.commit()
        print(f"[{timestamp}] Successfully logged {len(vehicles)} vehicles and weather data.")
    except Exception as e:
        if conn:
            conn.rollback() # Rollback on error
        print(f"[Critical] Error logging to DB: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()

def main(event=None, context=None):
    """Entry point for local execution or cloud functions."""
    vehicles = get_vehicle_positions()
    weather = get_weather()
    log_data_to_db(vehicles, weather)

if __name__ == "__main__":
    main()

