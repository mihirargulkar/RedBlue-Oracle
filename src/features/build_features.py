import pandas as pd
import numpy as np

def build_features(input_path='data/processed/extracted_raw_dataset.csv', output_path='data/processed/model_features.csv'):
    """Takes the raw joined dataset and engineers ML features."""
    print(f"Loading raw dataset from {input_path}...")
    try:
        df = pd.read_csv(input_path)
    except FileNotFoundError:
        print("Raw dataset not found. Run extract_dataset.py first.")
        return
        
    df['actual_timestamp'] = pd.to_datetime(df['actual_timestamp'])
    df['scheduled_timestamp'] = pd.to_datetime(df['scheduled_timestamp'])
    
    print("1. Engineering Temporal Features...")
    df['hour_of_day'] = df['actual_timestamp'].dt.hour
    df['day_of_week'] = df['actual_timestamp'].dt.dayofweek
    df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
    
    # Define Rush Hour explicitly (e.g. 7-9AM, 4-6PM)
    df['is_rush_hour'] = ((df['hour_of_day'] >= 7) & (df['hour_of_day'] <= 9)) | \
                         ((df['hour_of_day'] >= 16) & (df['hour_of_day'] <= 18))
    df['is_rush_hour'] = df['is_rush_hour'].astype(int)
    
    print("2. Engineering Spatial Features...")
    # Using Pandas get_dummies directly 
    df = pd.get_dummies(df, columns=['route_id', 'direction_id'], drop_first=False)
    
    print("3. Engineering Weather Features...")
    # Weather is already joined ('temp', 'precip_mm', 'wind_speed'), just ensure numerical format
    df['temp'] = pd.to_numeric(df['temp'], errors='coerce')
    df['precip_mm'] = pd.to_numeric(df['precip_mm'], errors='coerce')
    df['wind_speed'] = pd.to_numeric(df['wind_speed'], errors='coerce')
    
    print("4. Engineering Alpha Feature (Rolling Line Congestion)...")
    # Sort chronologically to compute rolling features
    df = df.sort_values(by=['trip_id', 'actual_timestamp'])
    
    # Calculate rolling congestion: Average delay of the previous 3 trains matching the exact same Station (stop_id)
    # Note: Requires sorting by stop_id and actual_timestamp.
    # We group by stop_id and compute the rolling average delay over the last 3 rows (which represent the 3 previous trains).
    
    df = df.sort_values(by=['stop_id', 'actual_timestamp'])
    df['rolling_congestion_3_trains'] = df.groupby('stop_id')['delay_minutes'].transform(
        lambda x: x.shift(1).rolling(window=3, min_periods=1).mean()
    )
    # Fill NAs for the very first train at a station (assume 0 congestion)
    df['rolling_congestion_3_trains'] = df['rolling_congestion_3_trains'].fillna(0)
    
    # Drop rows that are lacking critically needed targets
    df = df.dropna(subset=['delay_minutes'])
    
    # Select final ML feature columns
    target_col = 'delay_minutes'
    feature_cols = [
        'hour_of_day', 'day_of_week', 'is_weekend', 'is_rush_hour', 
        'temp', 'precip_mm', 'wind_speed', 'rolling_congestion_3_trains'
    ]
    # Dynamically inject one-hot encoded route and direction columns
    spatial_cols = [c for c in df.columns if 'route_id_' in c or 'direction_id_' in c]
    feature_cols.extend(spatial_cols)
    
    df_final = df[['trip_id', 'stop_id', 'actual_timestamp'] + feature_cols + [target_col]]
    
    print("Saving engineered features...")
    df_final.to_csv(output_path, index=False)
    print(f"Saved {len(df_final)} feature rows to {output_path}")
    print(df_final[feature_cols + [target_col]].head())

if __name__ == "__main__":
    build_features()
