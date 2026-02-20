import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Database connection parameters from .env
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "greenline_oracle"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password")
}

SCHEMA_SQL = """
-- STATIC TABLES
CREATE TABLE IF NOT EXISTS routes (
    route_id VARCHAR(255) PRIMARY KEY,
    route_short_name VARCHAR(255),
    route_long_name TEXT,
    route_type INTEGER
);

CREATE TABLE IF NOT EXISTS trips (
    trip_id VARCHAR(255) PRIMARY KEY,
    route_id VARCHAR(255) REFERENCES routes(route_id),
    direction_id INTEGER,
    trip_headsign TEXT
);

CREATE TABLE IF NOT EXISTS stops (
    stop_id VARCHAR(255) PRIMARY KEY,
    stop_name VARCHAR(255),
    stop_lat DOUBLE PRECISION,
    stop_lon DOUBLE PRECISION
);

DROP TABLE IF EXISTS stop_times;
CREATE TABLE IF NOT EXISTS stop_times (
    id SERIAL PRIMARY KEY,
    trip_id VARCHAR(255) REFERENCES trips(trip_id),
    stop_id VARCHAR(255) REFERENCES stops(stop_id),
    arrival_time VARCHAR(20),
    departure_time VARCHAR(20),
    stop_sequence INTEGER
);

-- REAL-TIME TABLES
CREATE TABLE IF NOT EXISTS vehicle_positions (
    id SERIAL PRIMARY KEY,
    vehicle_id VARCHAR(255),
    trip_id VARCHAR(255),
    stop_id VARCHAR(255),
    current_status VARCHAR(50),
    timestamp TIMESTAMP,
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS weather_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP,
    temp DOUBLE PRECISION,
    precip_mm DOUBLE PRECISION,
    wind_speed DOUBLE PRECISION
);
"""

def init_db():
    """Initializes the PostgreSQL database with the required schema."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        print(f"Connected to database: {DB_CONFIG['database']}")
        
        cur.execute(SCHEMA_SQL)
        conn.commit()
        print("Database schema initialized successfully.")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error initializing database: {e}")

if __name__ == "__main__":
    init_db()
