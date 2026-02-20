# PRD: GreenLine Oracle - Real-Time MBTA Delay Predictor

## 1. Product Vision & Objective

### The Problem
The MBTA's official predictions (via their V3 API / GTFS-Realtime feed) rely heavily on naive historical averages and simple physics (distance/speed). They routinely fail to account for complex, compounding variables like sudden weather shifts, cascading station congestion (e.g., student rush hour or TD Garden events), and historical line-specific degradation.

### The Solution
An end-to-end machine learning pipeline that ingests static schedules, live vehicle positions, and weather data to forecast train delays with a lower Mean Absolute Error (MAE) than the MBTA’s own proprietary API.

---

## 2. System Architecture

- **Data Ingestion (Extract):** Python worker (AWS Lambda/GCP Cloud Functions) pinging MBTA V3 API and Open-Meteo API every 60s.
- **Storage (Load):** Cloud-hosted PostgreSQL (Supabase/AWS RDS).
- **Transformation (Transform):** SQL views or dbt models joining static GTFS schedule with dynamic feeds.
- **Modeling:** XGBoost Regressor trained on historical data, updated weekly.
- **Serving:** FastAPI backend serving model weights.
- **UI:** Streamlit frontend dashboard.

---

## 3. Database Schema Design

### A. Static Tables (Updated Monthly)
- `routes`: `route_id`, `short_name`, `type`
- `trips`: `trip_id`, `route_id`, `direction_id`
- `stops`: `stop_id`, `stop_name`, `lat`, `lon`
- `stop_times`: `trip_id`, `stop_id`, `scheduled_arrival`

### B. Real-Time Streaming Tables (60s Cron)
- `vehicle_positions`: `vehicle_id`, `trip_id`, `current_stop_id`, `status`, `timestamp`
- `weather_logs`: `timestamp`, `temp`, `precip_mm`, `wind_speed`

### C. Target Variable: Actual Delay
`Actual Delay (min) = (Actual Timestamp - Scheduled Arrival) / 60`

---

## 4. Execution Plan & Milestones

### Phase 1: Pipeline & Data Collection (Weeks 1-2)
1. Setup MBTA V3 API key.
2. Parse GTFS Static ZIP and load into Postgres (Subway focus).
3. Implement real-time data gathering (/vehicles + weather).
4. Deploy to cloud scheduler for 2 weeks of data collection.

### Phase 2: Feature Engineering (Week 3)
- **Temporal:** Hour, Day, Weekend, Rush Hour.
- **Spatial:** One-hot encode Route/Direction.
- **Weather:** Rolling 3h precip, Temp.
- **Alpha Feature:** Rolling Line Congestion (Avg delay of last 3 trains at station).

### Phase 3: Model Training & Evaluation (Week 4)
- **Temporal Split:** 10 days train / 4 days validate.
- **Model:** XGBoost Regressor.
- **Evaluation:** Compare MAE against official MBTA predictions.

### Phase 4: UI & Deployment (Week 5)
- Streamlit app with Line/Station/Direction dropdowns.
- Comparative display: MBTA Prediction vs. Our Model with reasoning.
