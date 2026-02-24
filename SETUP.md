# RedBlue Oracle Setup Guide

Follow these steps to set up your development environment and get your MBTA API key.

## 1. Get an MBTA API Key
1. Go to the [MBTA V3 Portal](https://api-v3.mbta.com/).
2. Click on **"Request API Key"** or sign in.
3. Once you have your key, copy it.
4. Duplicate `.env.example` to `.env`.
5. Paste your key into the `MBTA_API_KEY` field.

## 2. Environment Setup
1. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies (we will populate requirements.txt as we go):
   ```bash
   pip install requests pandas psycopg2-binary python-dotenv xgboost sqlalchemy fastapi uvicorn streamlit
   ```

## 3. Database
We recommend using **Supabase** (Postgres free tier) or a local Postgres instance.
1. Create a database named `greenline_oracle`.
2. Update the connection details in your `.env` file.
