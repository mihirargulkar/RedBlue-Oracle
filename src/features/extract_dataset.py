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
    
    # FILTER: Only keep the FIRST ping of a vehicle stopped at a specific station
    # This removes redundant 'STOPPED_AT' pings logged every 60s while the train is parked.
    df_vehicles = df_vehicles.drop_duplicates(subset=['trip_id', 'stop_id'], keep='first')
    print(f"Filtered redundant station pings. {len(df_vehicles)} unique stops remain.")
    
    # Convert timestamps to pandas datetime
    df_vehicles['actual_timestamp'] = pd.to_datetime(df_vehicles['actual_timestamp'])
    # ALIGN TIMEZONES: Supabase timestamps are UTC. GTFS schedules are local EST.
    # We must subtract 5 hours from actual_timestamp to align them before calculating delays.
    df_vehicles['actual_timestamp'] = df_vehicles['actual_timestamp'] - pd.Timedelta(hours=5)
    
    # Scheduled Arrival is currently a string like '14:30:00' or '25:30:00' (GTFS standard). 
    # Because trains cross midnight, we map actual live pings to the 3 closest adjacent days, 
    # find the literal delta natively, and select the minimal logical delay to determine the anchor operation day.
    def convert_gtfs_time(row):
        try:
            val = str(row['scheduled_arrival'])
            if pd.isna(val) or val == 'None':
                return pd.NaT
                
            h, m, s = map(int, val.split(':'))
            
            # Base GTFS logic for >24 hour times is shifting to next day
            days_add = 0
            if h >= 24:
                h -= 24
                days_add = 1
                
            actual = row['actual_timestamp']
            base_date = actual.date() + pd.Timedelta(days=days_add)
            
            # Create a localized time object representing the absolute scheduled time.
            base_time = pd.Timestamp(f"{base_date} {h:02d}:{m:02d}:{s:02d}")
            
            # Since actual date could be a bit before or after midnight during the operation day, 
            # we check Yesterday, Today, and Tomorrow and select the timestamp that yields the smallest delay.
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
                    
            return best_candidate
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
