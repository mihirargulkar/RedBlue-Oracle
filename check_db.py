import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD")
}

def check_db():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM vehicle_positions;")
    count = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM weather_logs;")
    weather_count = cur.fetchone()[0]
    
    cur.execute("SELECT MAX(timestamp) FROM vehicle_positions;")
    last_update = cur.fetchone()[0]
    
    print(f"Vehicle Positions Count: {count}")
    print(f"Weather Logs Count: {weather_count}")
    print(f"Last Update: {last_update}")
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_db()
