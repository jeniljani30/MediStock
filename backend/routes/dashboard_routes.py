# -*- coding: utf-8 -*-
"""
Dashboard REST API endpoints for MediStock.
"""
from flask import Blueprint, jsonify, request
from backend.services.inventory_service import InventoryService

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/summary', methods=['GET'])
def get_summary():
    """Returns high-level KPI metrics for the Command Center Dashboard."""
    try:
        summary = InventoryService.get_dashboard_summary()
        return jsonify({
            'status': 'success',
            'data': summary
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@dashboard_bp.route('/table', methods=['GET'])
def get_table():
    """Returns dynamic medicine records for the Master Inventory Table."""
    try:
        status_filter = request.args.get('filter', 'all')
        query = request.args.get('q', '').lower().strip()

        all_meds = InventoryService.get_all_medicines_summary()
        filtered = []

        for m in all_meds:
            # Status filtering
            if status_filter == 'high-risk' and m['risk_class'] != 'crit':
                continue
            if status_filter == 'low' and (m['usable_stock'] >= m['reorder_point'] or m['usable_stock'] == 0):
                continue
            if status_filter == 'expiring' and m['near_expiry_stock'] == 0:
                continue
            if status_filter == 'expired' and m['expired_stock'] == 0:
                continue
            if status_filter == 'healthy' and m['risk_class'] != 'healthy':
                continue

            # Query search
            if query:
                search_target = f"{m['medicine_name']} {m['medicine_id']} {m['category']} {m['manufacturer']}".lower()
                if query not in search_target:
                    continue

            filtered.append(m)

        return jsonify({
            'status': 'success',
            'count': len(filtered),
            'data': filtered
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
