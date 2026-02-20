import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "greenline_oracle"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password")
}

DATA_DIR = "data/static/filtered"

def load_csv_to_db(filename, table_name, column_mapping):
    """Loads a filtered GTFS CSV into the database."""
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return

    df = pd.read_csv(path)
    # Select and rename columns based on mapping
    df = df[list(column_mapping.keys())].rename(columns=column_mapping)
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Clear existing data in table (optional, for refresh)
        # cur.execute(f"TRUNCATE TABLE {table_name} CASCADE;")
        
        # Efficient bulk insert
        from psycopg2.extras import execute_values
        query = f"INSERT INTO {table_name} ({', '.join(column_mapping.values())}) VALUES %s ON CONFLICT DO NOTHING"
        execute_values(cur, query, df.values.tolist())
        
        conn.commit()
        print(f"Loaded {len(df)} rows into {table_name}")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error loading {table_name}: {e}")

def load_all_static_data():
    """Orchestrates loading all filtered static data."""
    load_csv_to_db("routes.csv", "routes", {
        "route_id": "route_id",
        "route_short_name": "route_short_name",
        "route_long_name": "route_long_name",
        "route_type": "route_type"
    })
    
    load_csv_to_db("stops.csv", "stops", {
        "stop_id": "stop_id",
        "stop_name": "stop_name",
        "stop_lat": "stop_lat",
        "stop_lon": "stop_lon"
    })
    
    load_csv_to_db("trips.csv", "trips", {
        "trip_id": "trip_id",
        "route_id": "route_id",
        "direction_id": "direction_id",
        "trip_headsign": "trip_headsign"
    })
    
    load_csv_to_db("stop_times.csv", "stop_times", {
        "trip_id": "trip_id",
        "stop_id": "stop_id",
        "arrival_time": "arrival_time",
        "departure_time": "departure_time",
        "stop_sequence": "stop_sequence"
    })

if __name__ == "__main__":
    load_all_static_data()
