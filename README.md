# GreenLine Oracle - Real-Time MBTA Delay Predictor

GreenLine Oracle is an end-to-end machine learning pipeline that forecasts MBTA train delays using live vehicle positions, static schedules, and weather data. It aims to provide more accurate predictions than the official MBTA API by accounting for complex variables like weather shifts and line-specific congestion.

## Project Structure
- `src/ingestion`: Data collection scripts (MBTA API, Open-Meteo).
- `src/modeling`: Feature engineering and XGBoost model training.
- `src/api`: FastAPI backend for serving predictions.
- `frontend`: Streamlit dashboard for user interaction.
- `data/static`: GTFS static schedule data.

## Documentation
- [PRD.md](PRD.md): Detailed product requirements and system architecture.
