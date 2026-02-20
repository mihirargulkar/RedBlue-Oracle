import os
import requests
from dotenv import load_dotenv

load_dotenv()

GTFS_URL = "https://cdn.mbta.com/MBTA_GTFS.zip"
OUTPUT_PATH = os.getenv("GTFS_ZIP_PATH", "data/static/MBTA_GTFS.zip")

def download_gtfs():
    """Downloads the latest MBTA GTFS static data."""
    print(f"Downloading GTFS from {GTFS_URL}...")
    
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    
    try:
        response = requests.get(GTFS_URL, stream=True)
        response.raise_for_status()
        
        with open(OUTPUT_PATH, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"Successfully downloaded to {OUTPUT_PATH}")
    except Exception as e:
        print(f"Error downloading GTFS: {e}")

if __name__ == "__main__":
    download_gtfs()
