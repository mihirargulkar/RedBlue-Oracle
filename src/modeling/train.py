import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib
import os

def train_model(
    input_path='data/processed/model_features.csv', 
    model_output_path='src/modeling/xgboost_model.joblib',
    train_split_ratio=0.7 # 10 days / 14 days ~= 0.71
):
    print(f"Loading features from {input_path}...")
    try:
        df = pd.read_csv(input_path)
    except FileNotFoundError:
        print("Model features not found. Run src/features/build_features.py first.")
        return

    # Ensure actual timestamp is datetime and sort chronologically for temporal split
    df['actual_timestamp'] = pd.to_datetime(df['actual_timestamp'])
    df = df.sort_values(by='actual_timestamp')

    print(f"Total dataset size: {len(df)} rows.")

    # Select feature columns (exclude identifiers and timestamp)
    target_col = 'delay_minutes'
    drop_cols = ['trip_id', 'stop_id', 'actual_timestamp', target_col]
    
    # We drop any NaNs created by rolling features or other processes
    df = df.dropna()

    X = df.drop(columns=drop_cols)
    y = df[target_col]

    # Temporal Split: first N% rows are train, remaining are test
    split_index = int(len(df) * train_split_ratio)
    
    X_train, X_test = X.iloc[:split_index], X.iloc[split_index:]
    y_train, y_test = y.iloc[:split_index], y.iloc[split_index:]
    
    # Also save the timestamps for the test set evaluation context
    eval_timestamps = df['actual_timestamp'].iloc[split_index:]

    print(f"Training set: {len(X_train)} rows")
    print(f"Validation set: {len(X_test)} rows")

    # Initialize XGBoost Regressor
    base_model = xgb.XGBRegressor(
        random_state=42, 
        objective='reg:squarederror'
    )
    
    # Define Hyperparameter Grid for Tuning
    param_grid = {
        'n_estimators': [50, 100, 200],
        'max_depth': [3, 5, 7],
        'learning_rate': [0.01, 0.05, 0.1],
        'subsample': [0.8, 1.0],
        'colsample_bytree': [0.8, 1.0]
    }
    
    from sklearn.model_selection import GridSearchCV
    print("Performing Hyperparameter Tuning with GridSearchCV...")
    grid_search = GridSearchCV(
        estimator=base_model,
        param_grid=param_grid,
        scoring='neg_mean_absolute_error',
        cv=3, # 3-fold cross validation due to small dataset size
        verbose=1,
        n_jobs=-1 # Use all available CPU cores
    )
    
    # Train the Grid Search
    grid_search.fit(X_train, y_train)

    print(f"Best Hyperparameters Found: {grid_search.best_params_}")
    
    # Extract the best model from the grid search
    model = grid_search.best_estimator_

    print("Evaluating best model against validation set...")
    predictions = model.predict(X_test)

    mae = mean_absolute_error(y_test, predictions)
    rmse = np.sqrt(mean_squared_error(y_test, predictions))
    r2 = r2_score(y_test, predictions)

    print("-" * 30)
    print("Model Performance on Validation Set:")
    print(f"Mean Absolute Error (MAE): {mae:.2f} minutes")
    print(f"Root Mean Squared Error (RMSE): {rmse:.2f} minutes")
    print(f"R-squared Score (R2): {r2:.2f}")
    print("-" * 30)

    # Save the model
    os.makedirs(os.path.dirname(model_output_path), exist_ok=True)
    joblib.dump(model, model_output_path)
    print(f"Trained model saved to: {model_output_path}")

    # Save X columns for reference
    feature_names_path = model_output_path.replace('.joblib', '_features.txt')
    with open(feature_names_path, 'w') as f:
        f.write("\n".join(X.columns))

if __name__ == "__main__":
    train_model()
