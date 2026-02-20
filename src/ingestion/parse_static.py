import os
import zipfile
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

ZIP_PATH = os.getenv("GTFS_ZIP_PATH", "data/static/MBTA_GTFS.zip")
EXTRACT_PATH = os.getenv("GTFS_EXTRACT_PATH", "data/static/extracted")

def parse_static_gtfs():
    """Parses GTFS static files and filters for subway lines."""
    if not os.path.exists(ZIP_PATH):
        print(f"GTFS zip not found at {ZIP_PATH}. Run download_gtfs.py first.")
        return

    os.makedirs(EXTRACT_PATH, exist_ok=True)
    
    print(f"Extracting {ZIP_PATH}...")
    with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
        zip_ref.extractall(EXTRACT_PATH)

    # 1. Routes - Filter for Subway (Route Types 0 and 1)
    # 0 = Tram, Streetcar, Light rail
    # 1 = Subway, Metro
    print("Processing routes...")
    routes_df = pd.read_csv(os.path.join(EXTRACT_PATH, "routes.txt"))
    subway_routes = routes_df[routes_df['route_type'].isin([0, 1])]
    subway_route_ids = subway_routes['route_id'].unique()
    print(f"Found {len(subway_route_ids)} subway routes.")

    # 2. Trips
    print("Processing trips...")
    trips_df = pd.read_csv(os.path.join(EXTRACT_PATH, "trips.txt"))
    subway_trips = trips_df[trips_df['route_id'].isin(subway_route_ids)]
    subway_trip_ids = subway_trips['trip_id'].unique()
    print(f"Found {len(subway_trip_ids)} subway trips.")

    # 3. Stop Times
    print("Processing stop times...")
    # This file can be very large, process in chunks if necessary, but for MBTA subway it should fit in memory
    stop_times_df = pd.read_csv(os.path.join(EXTRACT_PATH, "stop_times.txt"))
    subway_stop_times = stop_times_df[stop_times_df['trip_id'].isin(subway_trip_ids)]
    print(f"Found {len(subway_stop_times)} subway stop time entries.")

    # 4. Stops
    print("Processing stops...")
    stops_df = pd.read_csv(os.path.join(EXTRACT_PATH, "stops.txt"))
    subway_stop_ids = subway_stop_times['stop_id'].unique()
    subway_stops = stops_df[stops_df['stop_id'].isin(subway_stop_ids)]
    print(f"Found {len(subway_stops)} subway stops.")

    # Save filtered data for review/loading
    output_dir = "data/static/filtered"
    os.makedirs(output_dir, exist_ok=True)
    subway_routes.to_csv(os.path.join(output_dir, "routes.csv"), index=False)
    subway_trips.to_csv(os.path.join(output_dir, "trips.csv"), index=False)
    subway_stop_times.to_csv(os.path.join(output_dir, "stop_times.csv"), index=False)
    subway_stops.to_csv(os.path.join(output_dir, "stops.csv"), index=False)
    
    print(f"Filtered subway GTFS data saved to {output_dir}")
    return subway_routes, subway_trips, subway_stop_times, subway_stops

if __name__ == "__main__":
    parse_static_gtfs()
