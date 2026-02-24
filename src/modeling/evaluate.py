import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import mean_absolute_error, mean_squared_error
import os

def evaluate_baseline_vs_model(
    features_path='data/processed/model_features.csv',
    model_path='src/modeling/xgboost_model.joblib',
    train_split_ratio=0.7
):
    print(f"Loading features from {features_path}...")
    try:
        df = pd.read_csv(features_path)
    except FileNotFoundError:
        print("Model features not found.")
        return

    if not os.path.exists(model_path):
        print(f"Model not found at {model_path}. Run train.py first.")
        return

    # Sort chronologically for temporal split (same as training)
    df['actual_timestamp'] = pd.to_datetime(df['actual_timestamp'])
    df = df.sort_values(by='actual_timestamp')
    df = df.dropna()

    target_col = 'delay_minutes'
    y = df[target_col]

    split_index = int(len(df) * train_split_ratio)
    
    # Validation targets
    y_test = y.iloc[split_index:]
    
    # Load Model
    print(f"Loading trained XGBoost model from {model_path}...")
    model = joblib.load(model_path)

    # 1. XGBoost Model Predictions
    drop_cols = ['trip_id', 'stop_id', 'actual_timestamp', target_col]
    X_test = df.drop(columns=drop_cols).iloc[split_index:]
    xgb_predictions = model.predict(X_test)
    
    xgb_mae = mean_absolute_error(y_test, xgb_predictions)

    # 2. Baseline Predictions
    # The naive schedule baseline assumes trains are perfectly on time -> predicted delay is 0.
    baseline_predictions = np.zeros(len(y_test))
    baseline_mae = mean_absolute_error(y_test, baseline_predictions)

    print("-" * 50)
    print("🌟 Evaluation: XGBoost Model vs Scheduled Baseline")
    print("-" * 50)
    print(f"Total Validation Samples: {len(y_test)}")
    print(f"Baseline (Predicting 0 Delay) MAE  : {baseline_mae:.2f} minutes")
    print(f"RedBlue Oracle (XGBoost) MAE     : {xgb_mae:.2f} minutes")
    print("-" * 50)
    
    if xgb_mae < baseline_mae:
        improvement = ((baseline_mae - xgb_mae) / baseline_mae) * 100
        print(f"✅ Model beats the baseline by {improvement:.1f}%!")
    else:
        print("❌ Model did not beat the baseline. Needs more data or better features.")

if __name__ == "__main__":
    evaluate_baseline_vs_model()
