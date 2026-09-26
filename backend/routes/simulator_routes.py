# -*- coding: utf-8 -*-
"""
What-If Simulator REST API endpoints for MediStock (Tier 2).
Pure calculation engine for scenario testing without modifying the real database.
"""
from flask import Blueprint, jsonify, request
from backend.services.inventory_service import InventoryService

simulator_bp = Blueprint('simulator', __name__)

@simulator_bp.route('', methods=['POST'])
@simulator_bp.route('/simulate', methods=['POST'])
def run_simulation():
    """
    Runs a What-If Demand Simulation:
    Expects JSON: { "medicine_id": str, "demand_adjustment_pct": float }
    """
    try:
        data = request.get_json() or {}
        medicine_id = data.get('medicine_id')
        adjustment_pct = data.get('demand_adjustment_pct', 0)

        if not medicine_id:
            return jsonify({'status': 'error', 'message': 'Missing medicine_id.'}), 400

        try:
            adjustment_pct = float(adjustment_pct)
        except (TypeError, ValueError):
            return jsonify({'status': 'error', 'message': 'Invalid demand_adjustment_pct. Must be numeric.'}), 400

        result = InventoryService.run_what_if_simulation(
            medicine_id=medicine_id,
            demand_adjustment_pct=adjustment_pct
        )

        return jsonify({
            'status': 'success',
            'data': result
        }), 200
    except ValueError as ve:
        return jsonify({'status': 'error', 'message': str(ve)}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
