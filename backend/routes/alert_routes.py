# -*- coding: utf-8 -*-
"""
Dynamic Alerts REST API endpoints for MediStock.
"""
from flask import Blueprint, jsonify
from backend.services.inventory_service import InventoryService

alert_bp = Blueprint('alerts', __name__)

@alert_bp.route('', methods=['GET'])
def get_alerts():
    """Returns real-time dynamic inventory risk and compliance alerts."""
    try:
        alerts = InventoryService.get_dynamic_alerts()
        return jsonify({
            'status': 'success',
            'count': len(alerts),
            'data': alerts
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
