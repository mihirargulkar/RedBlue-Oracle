import os
import psycopg2
import pandas as pd
from dotenv import load_dotenv

def extract_raw_data():
    """Extracts raw vehicle positions, schedules, and weather from Supabase."""
    load_dotenv()
    
    # Supabase Connection string config
    DB_CONFIG = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "database": os.getenv("DB_NAME", "postgres"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "password")
    }
    
    print("Connecting to Supabase...")
    conn = psycopg2.connect(**DB_CONFIG)
    
    # 1. Complex Query to join live positions with static stop_times
    # We want to find the scheduled arrival for a specific (trip_id, stop_id) and 
    # join it with the actual live timestamp when the vehicle arrived/stopped there.
    query = """
    SELECT 
        vp.vehicle_id,
        vp.trip_id,
        vp.stop_id,
        vp.current_status,
        vp.timestamp AS actual_timestamp,
        vp.lat,
        vp.lon,
        st.arrival_time AS scheduled_arrival,
        t.route_id,
        t.direction_id
    FROM vehicle_positions vp
    LEFT JOIN stop_times st ON vp.trip_id = st.trip_id AND vp.stop_id = st.stop_id
    LEFT JOIN trips t ON vp.trip_id = t.trip_id
    WHERE vp.current_status = 'STOPPED_AT';
    """
    
    print("Extracting Vehicle & Scheduled data...")
    df_vehicles = pd.read_sql(query, conn)
    
    # 2. Extract Weather Logs
    print("Extracting Weather data...")
    df_weather = pd.read_sql("SELECT * FROM weather_logs", conn)
    
    conn.close()
    
    if df_vehicles.empty:
        print("Warning: No 'STOPPED_AT' vehicle data found yet.")
        return None
        
    print(f"Extracted {len(df_vehicles)} vehicle records and {len(df_weather)} weather records.")
    
    # 3. Clean and Merge
    print("Merging datasets and calculating delay constraints...")
    
    # Convert timestamps to pandas datetime
    df_vehicles['actual_timestamp'] = pd.to_datetime(df_vehicles['actual_timestamp'])
    
    # Scheduled Arrival is currently a string like '14:30:00'. We need to combine it with the specific calendar day.
    # For now, we approximate by extracting the base hour/minute and keeping it relative to actual timestamp's day.
    # Note: Handles MBTA GTFS times like "25:30:00" mapping to 1:30 AM the next day.
    def convert_gtfs_time(row):
        try:
            val = str(row['scheduled_arrival'])
            if pd.isna(val) or val == 'None':
                return pd.NaT
            h, m, s = map(int, val.split(':'))
            actual_date = row['actual_timestamp'].date()
            if h >= 24:
                h = h - 24
                actual_date = actual_date + pd.Timedelta(days=1)
            
            return pd.Timestamp(f"{actual_date} {h:02d}:{m:02d}:{s:02d}")
        except Exception:
            return pd.NaT

    df_vehicles['scheduled_timestamp'] = df_vehicles.apply(convert_gtfs_time, axis=1)
    df_vehicles = df_vehicles.dropna(subset=['scheduled_timestamp'])
    
    # Calculate Delay Target (Actual - Scheduled in minutes)
    df_vehicles['delay_minutes'] = (df_vehicles['actual_timestamp'] - df_vehicles['scheduled_timestamp']).dt.total_seconds() / 60.0
    
    # Join with nearest Weather snapshot (Asof merge)
    df_weather['timestamp'] = pd.to_datetime(df_weather['timestamp'])
    df_weather = df_weather.sort_values('timestamp')
    df_vehicles = df_vehicles.sort_values('actual_timestamp')
    
    final_df = pd.merge_asof(
        df_vehicles, 
        df_weather, 
        left_on='actual_timestamp', 
        right_on='timestamp', 
        direction='nearest',
        tolerance=pd.Timedelta('60min')
    )
    
    # Drop rows without matching weather within tolerance
    final_df = final_df.dropna(subset=['temp'])
    
    # Save to CSV for building features
    output_path = 'data/processed/extracted_raw_dataset.csv'
    final_df.to_csv(output_path, index=False)
    print(f"Saved {len(final_df)} joined rows to {output_path}")
    print(final_df[['trip_id', 'stop_id', 'delay_minutes', 'temp']].head())
    
    return final_df

if __name__ == "__main__":
    extract_raw_data()
