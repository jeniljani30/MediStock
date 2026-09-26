# -*- coding: utf-8 -*-
"""
MediStock Tier 3 Comprehensive End-to-End Verification Suite.
Validates all 16 items specified in Tier 3:
A. Dashboard loading
B. Inventory loading
C. Medicine search
D. Medicine detail
E. Demand prediction
F. Demand chart trend
G. Expiry intelligence
H. FEFO queue
I. Simulated sale
J. Database update after sale
K. Risk recalculation
L. Reorder recalculation
M. What-If simulation
N. Reorder history & status
O. Model comparison API
P. Error handling

Run with:  python -m pytest backend/tests/test_tier3.py -v
Requires:  Flask backend running on port 5000
"""
import urllib.request
import urllib.error
import json
import sqlite3
import os
import pytest

API_BASE = 'http://127.0.0.1:5000/api'
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(ROOT_DIR, 'backend', 'database', 'medistock.db')
TEST_MED = 'MED003'  # Amoxicillin


def fetch_api(endpoint, method='GET', payload=None):
    """Helper to call the MediStock REST API."""
    url = f"{API_BASE}{endpoint}"
    req = urllib.request.Request(url, method=method)
    req.add_header('Content-Type', 'application/json')
    req.add_header('Accept', 'application/json')
    data = json.dumps(payload).encode('utf-8') if payload else None
    try:
        with urllib.request.urlopen(req, data=data) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {'message': body}


# ──────────────────────────────────────────────────────
# A. Dashboard Loading
# ──────────────────────────────────────────────────────
class TestA_DashboardLoading:
    def test_dashboard_summary_returns_200(self):
        status, data = fetch_api('/dashboard/summary')
        assert status == 200

    def test_total_medicines_is_60(self):
        _, data = fetch_api('/dashboard/summary')
        assert data['data']['total_medicines'] == 60

    def test_inventory_health_score_exists_and_valid(self):
        _, data = fetch_api('/dashboard/summary')
        score = data['data']['inventory_health_score']
        assert 0 <= score <= 100

    def test_dashboard_table_returns_60_records(self):
        status, data = fetch_api('/dashboard/table?filter=all')
        assert status == 200
        assert len(data['data']) == 60


# ──────────────────────────────────────────────────────
# B. Inventory Loading
# ──────────────────────────────────────────────────────
class TestB_InventoryLoading:
    def test_inventory_returns_200(self):
        status, _ = fetch_api('/inventory')
        assert status == 200

    def test_inventory_returns_60_medicine_cards(self):
        _, data = fetch_api('/inventory')
        assert len(data['data']) == 60


# ──────────────────────────────────────────────────────
# C. Medicine Search & Filter
# ──────────────────────────────────────────────────────
class TestC_MedicineSearch:
    def test_search_paracetamol_returns_200(self):
        status, _ = fetch_api('/search?q=Paracetamol')
        assert status == 200

    def test_search_paracetamol_finds_matches(self):
        _, data = fetch_api('/search?q=Paracetamol')
        assert data['count'] >= 2

    def test_category_filter_antihypertensive(self):
        _, data = fetch_api('/search?category=Antihypertensive')
        assert data['count'] >= 1

    def test_risk_filter_critical(self):
        _, data = fetch_api('/search?risk_level=Critical')
        assert data['count'] >= 1


# ──────────────────────────────────────────────────────
# D. Medicine Detail Profile
# ──────────────────────────────────────────────────────
class TestD_MedicineDetail:
    def test_medicine_detail_returns_200(self):
        status, _ = fetch_api(f'/inventory/medicines/{TEST_MED}/detail')
        assert status == 200

    def test_medicine_id_matches(self):
        _, data = fetch_api(f'/inventory/medicines/{TEST_MED}/detail')
        assert data['data']['medicine_id'] == TEST_MED

    def test_batch_records_present(self):
        _, data = fetch_api(f'/inventory/medicines/{TEST_MED}/detail')
        assert len(data['data']['batches_detail']) > 0

    def test_explainability_factors_present(self):
        _, data = fetch_api(f'/inventory/medicines/{TEST_MED}/detail')
        assert len(data['data']['explainability_factors']) >= 2


# ──────────────────────────────────────────────────────
# E. Demand Prediction
# ──────────────────────────────────────────────────────
class TestE_DemandPrediction:
    def test_predicted_daily_demand_positive(self):
        _, data = fetch_api(f'/inventory/medicines/{TEST_MED}/detail')
        assert data['data']['predicted_daily_demand'] > 0

    def test_predicted_30d_demand_positive(self):
        _, data = fetch_api(f'/inventory/medicines/{TEST_MED}/detail')
        assert data['data']['predicted_30d_demand'] > 0


# ──────────────────────────────────────────────────────
# F. Demand Chart Trend
# ──────────────────────────────────────────────────────
class TestF_DemandTrend:
    def test_demand_trend_returns_200(self):
        status, _ = fetch_api(f'/inventory/medicines/{TEST_MED}/demand-trend?horizon=30')
        assert status == 200

    def test_historical_series_present(self):
        _, data = fetch_api(f'/inventory/medicines/{TEST_MED}/demand-trend?horizon=30')
        assert data['data']['historical_days_count'] > 0

    def test_forecast_series_is_30_days(self):
        _, data = fetch_api(f'/inventory/medicines/{TEST_MED}/demand-trend?horizon=30')
        assert data['data']['forecast_days_count'] == 30


# ──────────────────────────────────────────────────────
# G. Expiry Intelligence
# ──────────────────────────────────────────────────────
class TestG_ExpiryIntelligence:
    def test_total_physical_stock_positive(self):
        _, data = fetch_api(f'/inventory/medicines/{TEST_MED}/detail')
        assert data['data']['total_physical_stock'] > 0

    def test_stock_separation_consistency(self):
        _, data = fetch_api(f'/inventory/medicines/{TEST_MED}/detail')
        d = data['data']
        assert d['total_physical_stock'] == d['usable_stock'] + d['expired_stock']


# ──────────────────────────────────────────────────────
# H. FEFO Priority Queue
# ──────────────────────────────────────────────────────
class TestH_FEFOQueue:
    def test_fefo_queue_returns_200(self):
        status, _ = fetch_api(f'/inventory/fefo/{TEST_MED}')
        assert status == 200

    def test_fefo_priority_batch_assigned(self):
        _, data = fetch_api(f'/inventory/fefo/{TEST_MED}')
        assert data['fefo_priority_batch'] is not None


# ──────────────────────────────────────────────────────
# I & J. Simulated Sale & Database Persistence
# ──────────────────────────────────────────────────────
class TestIJ_SaleAndPersistence:
    def test_sale_dispense_and_db_persistence(self):
        """Full sale cycle: dispense → verify API response → verify SQLite."""
        # Get initial stock
        _, detail = fetch_api(f'/inventory/medicines/{TEST_MED}/detail')
        initial_stock = detail['data']['usable_stock']
        sale_qty = 10

        # Perform sale
        status, sale_res = fetch_api('/sales/dispense', method='POST', payload={
            "medicine_id": TEST_MED,
            "quantity": sale_qty,
            "sales_channel": "Automated Test Suite"
        })
        assert status == 200
        assert sale_res['data']['updated_usable_stock'] == initial_stock - sale_qty

        # Verify in SQLite
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT SUM(current_stock) FROM inventory_batches "
            "WHERE medicine_id = ? AND expiry_date >= '2026-09-26';",
            (TEST_MED,)
        )
        db_stock = c.fetchone()[0]
        assert db_stock == initial_stock - sale_qty

        c.execute(
            "SELECT transaction_id, quantity_sold FROM sales_transactions "
            "WHERE medicine_id = ? ORDER BY date DESC, transaction_id DESC LIMIT 1;",
            (TEST_MED,)
        )
        latest_tx = c.fetchone()
        assert latest_tx[1] == sale_qty
        conn.close()


# ──────────────────────────────────────────────────────
# K & L. Post-Sale Risk & Reorder Recalculation
# ──────────────────────────────────────────────────────
class TestKL_PostSaleRecalculation:
    def test_days_until_stockout_recomputed(self):
        _, data = fetch_api(f'/inventory/medicines/{TEST_MED}/detail')
        assert data['data']['days_until_stockout'] >= 0

    def test_risk_level_evaluated(self):
        _, data = fetch_api(f'/inventory/medicines/{TEST_MED}/detail')
        assert data['data']['risk_level'] is not None

    def test_reorder_recommendation_evaluated(self):
        _, data = fetch_api(f'/inventory/medicines/{TEST_MED}/detail')
        assert data['data']['recommended_reorder_qty'] >= 0


# ──────────────────────────────────────────────────────
# M. What-If Simulation Isolation
# ──────────────────────────────────────────────────────
class TestM_WhatIfSimulation:
    def test_whatif_simulation_returns_200(self):
        status, _ = fetch_api('/what-if', method='POST', payload={
            "medicine_id": TEST_MED,
            "demand_adjustment_pct": 50
        })
        assert status == 200

    def test_simulated_demand_increases_with_positive_adjustment(self):
        _, data = fetch_api('/what-if', method='POST', payload={
            "medicine_id": TEST_MED,
            "demand_adjustment_pct": 50
        })
        sim = data['data']
        assert sim['simulation']['simulated_30d_demand'] > sim['baseline']['predicted_30d_demand']

    def test_whatif_zero_database_mutation(self):
        """Verify What-If does not alter the database."""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT SUM(current_stock) FROM inventory_batches;")
        stock_pre = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM sales_transactions;")
        txn_pre = c.fetchone()[0]
        conn.close()

        fetch_api('/what-if', method='POST', payload={
            "medicine_id": TEST_MED,
            "demand_adjustment_pct": 50
        })

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT SUM(current_stock) FROM inventory_batches;")
        stock_post = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM sales_transactions;")
        txn_post = c.fetchone()[0]
        conn.close()

        assert stock_pre == stock_post
        assert txn_pre == txn_post


# ──────────────────────────────────────────────────────
# N. Reorder History & Status Lifecycle
# ──────────────────────────────────────────────────────
class TestN_ReorderLifecycle:
    def test_reorder_summary_returns_200(self):
        status, _ = fetch_api('/reorders/summary')
        assert status == 200

    def test_reorder_create_approve_order_lifecycle(self):
        """Full reorder lifecycle: create → approve → order."""
        status, ro_new = fetch_api('/reorders/create', method='POST', payload={
            "medicine_id": TEST_MED,
            "quantity": 200,
            "reason": "Test Restock Order"
        })
        assert status == 201
        ro_id = ro_new['data']['reorder_id']

        status, _ = fetch_api(f'/reorders/{ro_id}/status', method='POST',
                              payload={"status": "Approved"})
        assert status == 200

        status, _ = fetch_api(f'/reorders/{ro_id}/status', method='POST',
                              payload={"status": "Ordered"})
        assert status == 200


# ──────────────────────────────────────────────────────
# O. Model Comparison API
# ──────────────────────────────────────────────────────
class TestO_ModelComparison:
    def test_model_comparison_returns_200(self):
        status, _ = fetch_api('/models/comparison')
        assert status == 200

    def test_contains_4_evaluated_models(self):
        _, data = fetch_api('/models/comparison')
        assert len(data['data']['models']) == 4

    def test_all_models_have_valid_metrics(self):
        _, data = fetch_api('/models/comparison')
        for m in data['data']['models']:
            assert m['metrics']['mae'] > 0, f"{m['model_name']} MAE <= 0"
            assert m['metrics']['rmse'] > 0, f"{m['model_name']} RMSE <= 0"
            assert 'r2' in m['metrics'], f"{m['model_name']} missing R²"


# ──────────────────────────────────────────────────────
# P. Error Handling & Input Validation
# ──────────────────────────────────────────────────────
class TestP_ErrorHandling:
    def test_negative_sale_quantity_rejected(self):
        status, _ = fetch_api('/sales/dispense', method='POST',
                              payload={"medicine_id": TEST_MED, "quantity": -5})
        assert status == 400

    def test_nonexistent_medicine_sale_rejected(self):
        status, _ = fetch_api('/sales/dispense', method='POST',
                              payload={"medicine_id": "NON_EXISTENT_SKU", "quantity": 10})
        assert status in (400, 404)

    def test_excessive_stock_sale_rejected(self):
        status, _ = fetch_api('/sales/dispense', method='POST',
                              payload={"medicine_id": TEST_MED, "quantity": 9999999})
        assert status == 400

    def test_nonexistent_medicine_detail_returns_404(self):
        status, _ = fetch_api('/inventory/medicines/NON_EXISTENT_SKU/detail')
        assert status == 404

    def test_invalid_reorder_status_rejected(self):
        # Create a reorder first, then try invalid status
        _, ro = fetch_api('/reorders/create', method='POST', payload={
            "medicine_id": TEST_MED, "quantity": 100, "reason": "Error test"
        })
        ro_id = ro['data']['reorder_id']
        status, _ = fetch_api(f'/reorders/{ro_id}/status', method='POST',
                              payload={"status": "INVALID_STATUS"})
        assert status == 400
