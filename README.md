# RedBlue Oracle: Real-Time MBTA Delay Predictor

## What is this project?
RedBlue Oracle is an end-to-end machine learning pipeline that forecasts real-time train delays on the Boston MBTA's Red and Blue subway lines. It ingests live vehicle positions, static schedules, and weather telemetry to predict exactly how late a train will be at a given station. The project aims to provide more accurate predictions than the official MBTA API by accounting for dynamic variables like weather shifts and line-specific congestion.

Note: The MBTA only publishes static timetables for the Red and Blue lines, so the supervised ML model is specifically trained to predict delays for these routes.

## What did I do?
To build this full-stack predictive system, I designed and implemented the following:
*   **Real-time Data Pipeline**: Engineered an ingestion pipeline using Python and a PostgreSQL backend (Supabase) to continually merge live GTFS-Realtime vehicle pings with static MBTA schedules and Open-Meteo weather logs.
*   **Machine Learning Modeling**: Trained an XGBoost regression model on historical transit telemetry. I engineered custom features such as "rolling upstream delay", "line congestion", and weather impacts to capture compounding traffic effects.
*   **Performance Breakthrough**: Achieved a **54.7% improvement** in out-of-sample Mean Absolute Error (MAE) compared to baseline schedule adherence, reducing the average delay prediction error down to just **3.06 minutes**.
*   **API & User Interface**: Deployed the model weights via a FastAPI backend and built an interactive Streamlit frontend dashboard. The UI dynamically queries the database for active stations and provides context-rich ML predictions.

## Why did I do it?
The official MBTA transit predictions are often rigid and can be inaccurate during major disruptions or rush hour because they rely heavily on static logic. They struggle to dynamically factor in compiling upstream breakdowns, platform crowding, and harsh weather conditions. 

I built the RedBlue Oracle to prove that incorporating real-time geographic congestion and external telemetry (like extreme cold and wind speed) into a Machine Learning model can significantly outperform traditional schedule-based algorithms. This project serves as a showcase of my ability to build complete, end-to-end data-driven applications—from raw, noisy data extraction to a polished, user-facing prediction dashboard.

---
### Project Structure
- `src/ingestion`: Data collection scripts (MBTA API, Open-Meteo).
- `src/modeling`: Feature engineering and XGBoost model training.
- `frontend`: Streamlit dashboard (Includes Native ML Inference).
- `data/static`: GTFS static schedule data.
