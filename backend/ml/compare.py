# -*- coding: utf-8 -*-
"""
ML Model Comparison Service for MediStock (Tier 3).
Evaluates multiple regression algorithms on real historical sales data
using the same chronological train/test split.
"""
import os
import json
import time
import sqlite3
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from backend.ml.train import load_and_preprocess_data

COMPARISON_CACHE_FILE = os.path.join(os.path.dirname(__file__), 'model_comparison.json')

class ModelComparisonService:
    _cached_results = None

    @classmethod
    def get_comparison(cls, force_retrain=False):
        """Returns comparison metrics across multiple regressors trained on real data."""
        if cls._cached_results and not force_retrain:
            return cls._cached_results

        # Check if saved artifact exists
        if os.path.exists(COMPARISON_CACHE_FILE) and not force_retrain:
            try:
                with open(COMPARISON_CACHE_FILE, 'r', encoding='utf-8') as f:
                    cls._cached_results = json.load(f)
                    return cls._cached_results
            except Exception:
                pass

        return cls.run_model_comparison()

    @classmethod
    def run_model_comparison(cls):
        """Trains and compares LinearRegression, DecisionTree, RandomForest, and GradientBoosting."""
        df, le_med, le_cat = load_and_preprocess_data()

        feature_cols = [
            'med_code', 'cat_code', 'unit_price_inr', 'day_of_week', 'is_weekend',
            'month', 'day', 'lag_1', 'lag_7', 'rolling_mean_7', 'rolling_mean_14', 'rolling_std_7'
        ]
        target_col = 'daily_demand'

        # Chronological Split (No future data leakage)
        split_date = pd.to_datetime('2026-06-01')
        train_mask = df['date'] < split_date
        test_mask = df['date'] >= split_date

        X_train = df.loc[train_mask, feature_cols]
        y_train = df.loc[train_mask, target_col]
        X_test = df.loc[test_mask, feature_cols]
        y_test = df.loc[test_mask, target_col]

        models_to_evaluate = [
            {
                'name': 'Linear Regression',
                'model_class': LinearRegression,
                'params': {},
                'description': 'Parametric linear baseline modeling global feature weights.',
                'is_production': False
            },
            {
                'name': 'Decision Tree Regressor',
                'model_class': DecisionTreeRegressor,
                'params': {'max_depth': 6, 'random_state': 42},
                'description': 'Non-linear single tree partitioning feature space into piecewise intervals.',
                'is_production': False
            },
            {
                'name': 'Random Forest Regressor',
                'model_class': RandomForestRegressor,
                'params': {'n_estimators': 80, 'max_depth': 8, 'random_state': 42, 'n_jobs': -1},
                'description': 'Ensemble bagging algorithm averaging predictions across de-correlated decision trees.',
                'is_production': False
            },
            {
                'name': 'Gradient Boosting Regressor',
                'model_class': GradientBoostingRegressor,
                'params': {'n_estimators': 120, 'learning_rate': 0.08, 'max_depth': 4, 'random_state': 42},
                'description': 'Sequential ensemble minimizing residual loss gradients; superior variance control on time-series.',
                'is_production': True
            }
        ]

        evaluated = []
        for item in models_to_evaluate:
            m_name = item['name']
            m_inst = item['model_class'](**item['params'])

            t0 = time.time()
            m_inst.fit(X_train, y_train)
            train_duration = round(time.time() - t0, 3)

            y_pred = m_inst.predict(X_test)
            y_pred = np.maximum(y_pred, 0) # Non-negative constraints

            mae = float(round(mean_absolute_error(y_test, y_pred), 3))
            rmse = float(round(np.sqrt(mean_squared_error(y_test, y_pred)), 3))
            r2 = float(round(r2_score(y_test, y_pred), 4))

            evaluated.append({
                'model_name': m_name,
                'description': item['description'],
                'is_production': item['is_production'],
                'metrics': {
                    'mae': mae,
                    'rmse': rmse,
                    'r2': r2
                },
                'fit_time_seconds': train_duration,
                'status': 'Evaluated on Unseen Test Split'
            })

        # Rank models by MAE (lowest is best)
        evaluated_sorted = sorted(evaluated, key=lambda x: x['metrics']['mae'])

        result = {
            'evaluation_methodology': 'Chronological Train/Test Split (Unseen Future Horizon)',
            'split_date': '2026-06-01',
            'train_samples': int(len(X_train)),
            'test_samples': int(len(X_test)),
            'target_variable': 'daily_demand (units/day)',
            'selected_production_model': 'Gradient Boosting Regressor',
            'models': evaluated_sorted
        }

        cls._cached_results = result

        try:
            with open(COMPARISON_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2)
        except Exception:
            pass

        return result
