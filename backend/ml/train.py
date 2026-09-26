# -*- coding: utf-8 -*-
"""
ML Demand Prediction Pipeline for MediStock.
Trains a regression model on historical daily sales transactions using chronological train/test split.
"""
import os
import json
import pickle
import sqlite3
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import LabelEncoder
from backend.database.db import DB_PATH

ML_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_FILE = os.path.join(ML_DIR, 'demand_model.pkl')
META_FILE = os.path.join(ML_DIR, 'model_meta.json')

def load_and_preprocess_data():
    """Loads historical sales from SQLite and builds time-series lag features."""
    conn = sqlite3.connect(DB_PATH)
    
    # Aggregate daily sales per medicine
    query = """
        SELECT 
            s.date,
            s.medicine_id,
            SUM(s.quantity_sold) as daily_demand,
            AVG(s.selling_price_inr) as avg_price,
            m.unit_price_inr,
            m.category,
            m.dosage_form,
            m.shelf_life_days
        FROM sales_transactions s
        JOIN medicines m ON s.medicine_id = m.medicine_id
        GROUP BY s.date, s.medicine_id
        ORDER BY s.medicine_id, s.date ASC;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    df['date'] = pd.to_datetime(df['date'])

    # Time-based calendar features
    df['day_of_week'] = df['date'].dt.dayofweek
    df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
    df['month'] = df['date'].dt.month
    df['day'] = df['date'].dt.day

    # Medicine label encoding
    le_med = LabelEncoder()
    df['med_code'] = le_med.fit_transform(df['medicine_id'])

    le_cat = LabelEncoder()
    df['cat_code'] = le_cat.fit_transform(df['category'])

    # Grouped rolling and lag features per medicine
    grouped = df.groupby('medicine_id')
    df['lag_1'] = grouped['daily_demand'].shift(1)
    df['lag_7'] = grouped['daily_demand'].shift(7)
    df['rolling_mean_7'] = grouped['daily_demand'].shift(1).rolling(window=7, min_periods=1).mean()
    df['rolling_mean_14'] = grouped['daily_demand'].shift(1).rolling(window=14, min_periods=1).mean()
    df['rolling_std_7'] = grouped['daily_demand'].shift(1).rolling(window=7, min_periods=1).std().fillna(0)

    # Fill initial lag NaN values with medicine median
    med_medians = df.groupby('medicine_id')['daily_demand'].transform('median')
    df['lag_1'] = df['lag_1'].fillna(med_medians)
    df['lag_7'] = df['lag_7'].fillna(med_medians)
    df['rolling_mean_7'] = df['rolling_mean_7'].fillna(med_medians)
    df['rolling_mean_14'] = df['rolling_mean_14'].fillna(med_medians)

    return df, le_med, le_cat

def train_demand_model():
    """Trains regression model on chronological split and saves artifacts."""
    print("=" * 70)
    print("TRAINING MEDISTOCK ML DEMAND PREDICTION MODEL")
    print("=" * 70)

    df, le_med, le_cat = load_and_preprocess_data()
    print(f"[DATA] Prepared {len(df):,} daily records across {df['medicine_id'].nunique()} medicines.")

    feature_cols = [
        'med_code', 'cat_code', 'unit_price_inr', 'day_of_week', 'is_weekend',
        'month', 'day', 'lag_1', 'lag_7', 'rolling_mean_7', 'rolling_mean_14', 'rolling_std_7'
    ]
    target_col = 'daily_demand'

    # Chronological Split (No data leakage into the future!)
    split_date = pd.to_datetime('2026-06-01')
    train_mask = df['date'] < split_date
    test_mask = df['date'] >= split_date

    X_train = df.loc[train_mask, feature_cols]
    y_train = df.loc[train_mask, target_col]
    X_test = df.loc[test_mask, feature_cols]
    y_test = df.loc[test_mask, target_col]

    print(f"[SPLIT] Chronological boundary: {split_date.strftime('%Y-%m-%d')}")
    print(f" - Train set: {len(X_train):,} samples ({df.loc[train_mask, 'date'].min().strftime('%Y-%m-%d')} to {df.loc[train_mask, 'date'].max().strftime('%Y-%m-%d')})")
    print(f" - Test set:  {len(X_test):,} samples ({df.loc[test_mask, 'date'].min().strftime('%Y-%m-%d')} to {df.loc[test_mask, 'date'].max().strftime('%Y-%m-%d')})")

    # Train explainable Gradient Boosting Regressor
    model = GradientBoostingRegressor(
        n_estimators=120,
        learning_rate=0.08,
        max_depth=4,
        random_state=42
    )
    model.fit(X_train, y_train)

    # Evaluate model
    y_pred = model.predict(X_test)
    y_pred = np.maximum(y_pred, 0) # Non-negative demand

    mae = float(mean_absolute_error(y_test, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    r2 = float(r2_score(y_test, y_pred))

    print("-" * 70)
    print("MODEL EVALUATION METRICS (ON UNSEEN TEST HORIZON):")
    print(f" - MAE  (Mean Absolute Error):     {mae:.3f} units/day")
    print(f" - RMSE (Root Mean Squared Error): {rmse:.3f} units/day")
    print(f" - R²   (Coefficient of Determ.):   {r2:.4f}")
    print("-" * 70)

    # Save model artifact
    with open(MODEL_FILE, 'wb') as f:
        pickle.dump(model, f)

    # Save metadata & encoders
    meta = {
        'model_name': 'GradientBoostingRegressor',
        'feature_cols': feature_cols,
        'mae': mae,
        'rmse': rmse,
        'r2': r2,
        'train_samples': int(len(X_train)),
        'test_samples': int(len(X_test)),
        'split_date': '2026-06-01',
        'medicine_mapping': {str(k): int(v) for k, v in zip(le_med.classes_, le_med.transform(le_med.classes_))},
        'category_mapping': {str(k): int(v) for k, v in zip(le_cat.classes_, le_cat.transform(le_cat.classes_))}
    }

    with open(META_FILE, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)

    print(f"[SAVE] Model artifact saved to: {MODEL_FILE}")
    print(f"[SAVE] Model metadata saved to: {META_FILE}")
    print("=" * 70)

    return model, meta

if __name__ == '__main__':
    train_demand_model()
