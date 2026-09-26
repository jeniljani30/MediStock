# -*- coding: utf-8 -*-
"""
ML Predictor Service for MediStock Demand Forecasting.
Provides real model inference for medicine daily demand and future horizon projections.
"""
import os
import json
import pickle
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from backend.database.db import DB_PATH

ML_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_FILE = os.path.join(ML_DIR, 'demand_model.pkl')
META_FILE = os.path.join(ML_DIR, 'model_meta.json')

class DemandPredictor:
    _instance = None

    def __init__(self):
        self.model = None
        self.meta = {}
        self._cache = {}
        self.load_model()

    def invalidate_cache(self, medicine_id=None):
        """Invalidates cached predictions when data changes (e.g. after a sale)."""
        if medicine_id:
            keys_to_del = [k for k in list(self._cache.keys()) if k[0] == medicine_id]
            for k in keys_to_del:
                self._cache.pop(k, None)
        else:
            self._cache.clear()

    def prewarm(self):
        """Pre-computes and caches baseline demand predictions across all medicines."""
        if not self.model or not self.meta:
            self.load_model()
        try:
            conn = sqlite3.connect(DB_PATH, timeout=30.0)
            conn.execute("PRAGMA busy_timeout = 30000;")
            c = conn.cursor()
            c.execute("SELECT medicine_id FROM medicines;")
            med_ids = [r[0] for r in c.fetchall()]
            conn.close()
            for mid in med_ids:
                self.predict_horizon(mid, horizon_days=30, start_date='2026-09-26')
        except Exception:
            pass

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_model(self):
        if os.path.exists(MODEL_FILE) and os.path.exists(META_FILE):
            with open(MODEL_FILE, 'rb') as f:
                self.model = pickle.load(f)
            with open(META_FILE, 'r', encoding='utf-8') as f:
                self.meta = json.load(f)
            print("[ML] Loaded trained GradientBoosting demand model into memory.")
        else:
            print("[ML WARNING] Model artifact not found. Please run backend.ml.train first.")

    def get_recent_stats(self, medicine_id):
        """Retrieves recent 14-day sales telemetry for feature construction."""
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        conn.execute("PRAGMA busy_timeout = 30000;")
        query = """
            SELECT date, SUM(quantity_sold) as daily_demand
            FROM sales_transactions
            WHERE medicine_id = ?
            GROUP BY date
            ORDER BY date DESC
            LIMIT 30;
        """
        df_hist = pd.read_sql_query(query, conn, params=(medicine_id,))
        
        # Get medicine metadata
        query_med = "SELECT unit_price_inr, category FROM medicines WHERE medicine_id = ?;"
        cursor = conn.cursor()
        cursor.execute(query_med, (medicine_id,))
        med_row = cursor.fetchone()
        conn.close()

        if not med_row:
            return None

        unit_price, category = med_row[0], med_row[1]

        if df_hist.empty:
            return {
                'lag_1': 0.0,
                'lag_7': 0.0,
                'rolling_mean_7': 0.0,
                'rolling_mean_14': 0.0,
                'rolling_std_7': 0.0,
                'unit_price': unit_price,
                'category': category,
                'has_history': False
            }

        demands = df_hist['daily_demand'].tolist()
        lag_1 = demands[0] if len(demands) > 0 else 0.0
        lag_7 = demands[6] if len(demands) > 6 else lag_1
        rolling_7 = float(np.mean(demands[:7])) if len(demands) >= 1 else 0.0
        rolling_14 = float(np.mean(demands[:14])) if len(demands) >= 1 else rolling_7
        std_7 = float(np.std(demands[:7])) if len(demands) >= 2 else 0.0

        return {
            'lag_1': lag_1,
            'lag_7': lag_7,
            'rolling_mean_7': rolling_7,
            'rolling_mean_14': rolling_14,
            'rolling_std_7': std_7,
            'unit_price': unit_price,
            'category': category,
            'has_history': True
        }

    def predict_horizon(self, medicine_id, horizon_days=30, start_date=None):
        """Generates future day-by-day demand predictions using trained ML model."""
        cache_key = (medicine_id, horizon_days, start_date or '2026-09-26')
        if cache_key in self._cache:
            return self._cache[cache_key]

        if not self.model or not self.meta:
            self.load_model()

        stats = self.get_recent_stats(medicine_id)
        if not stats or not stats['has_history']:
            return {
                'medicine_id': medicine_id,
                'status': 'insufficient_data',
                'predicted_daily_demand': 0.0,
                'total_predicted_demand': 0,
                'horizon_predictions': []
            }

        med_mapping = self.meta.get('medicine_mapping', {})
        cat_mapping = self.meta.get('category_mapping', {})

        med_code = med_mapping.get(medicine_id, 0)
        cat_code = cat_mapping.get(stats['category'], 0)

        if start_date is None:
            curr_date = datetime.strptime('2026-09-26', '%Y-%m-%d')
        else:
            curr_date = datetime.strptime(start_date, '%Y-%m-%d')

        horizon_preds = []
        cur_lag1 = stats['lag_1']
        cur_lag7 = stats['lag_7']
        cur_rm7 = stats['rolling_mean_7']
        cur_rm14 = stats['rolling_mean_14']
        cur_std7 = stats['rolling_std_7']

        recent_window = [cur_lag1] * 7

        for day_offset in range(1, horizon_days + 1):
            target_date = curr_date + timedelta(days=day_offset)
            dow = target_date.weekday()
            is_weekend = 1 if dow in [5, 6] else 0
            month = target_date.month
            day = target_date.day

            feature_dict = {
                'med_code': [med_code],
                'cat_code': [cat_code],
                'unit_price_inr': [stats['unit_price']],
                'day_of_week': [dow],
                'is_weekend': [is_weekend],
                'month': [month],
                'day': [day],
                'lag_1': [cur_lag1],
                'lag_7': [cur_lag7],
                'rolling_mean_7': [cur_rm7],
                'rolling_mean_14': [cur_rm14],
                'rolling_std_7': [cur_std7]
            }

            feat_df = pd.DataFrame(feature_dict, columns=self.meta['feature_cols'])
            pred_val = float(self.model.predict(feat_df)[0])
            pred_val = max(0.1, round(pred_val, 2))

            horizon_preds.append({
                'date': target_date.strftime('%Y-%m-%d'),
                'predicted_units': pred_val
            })

            # Update rolling features autoregressively for multi-step forecast
            cur_lag1 = pred_val
            recent_window.append(pred_val)
            recent_window.pop(0)
            cur_rm7 = float(np.mean(recent_window))

        total_predicted = int(round(sum(p['predicted_units'] for p in horizon_preds)))
        avg_daily = round(total_predicted / horizon_days, 2)

        result = {
            'medicine_id': medicine_id,
            'status': 'success',
            'horizon_days': horizon_days,
            'predicted_daily_demand': avg_daily,
            'total_predicted_demand': total_predicted,
            'horizon_predictions': horizon_preds
        }
        self._cache[cache_key] = result
        return result

predictor = DemandPredictor.get_instance()
