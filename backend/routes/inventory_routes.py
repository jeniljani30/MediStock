# -*- coding: utf-8 -*-
"""
Inventory, Medicines, FEFO and Demand Trend REST API endpoints for MediStock.
"""
from flask import Blueprint, jsonify, request
from backend.services.inventory_service import InventoryService

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route('', methods=['GET'])
def get_inventory():
    """Returns all medicine cards with shelf classification and dynamic metrics."""
    try:
        meds = InventoryService.get_all_medicines_summary()
        return jsonify({
            'status': 'success',
            'count': len(meds),
            'data': meds
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@inventory_bp.route('/medicines', methods=['GET'])
def list_medicines():
    """Returns catalog list of all medicines for selectors and quick lookups."""
    try:
        meds = InventoryService.get_all_medicines_summary()
        catalog = [{
            'medicine_id': m['medicine_id'],
            'medicine_name': m['medicine_name'],
            'category': m['category'],
            'dosage_form': m['dosage_form'],
            'usable_stock': m['usable_stock'],
            'risk_level': m['risk_level']
        } for m in meds]
        return jsonify({
            'status': 'success',
            'count': len(catalog),
            'data': catalog
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@inventory_bp.route('/medicines/<medicine_id>/detail', methods=['GET'])
def get_medicine_detail(medicine_id):
    """Returns deep analytical intelligence profile for a single medicine."""
    try:
        # Normalize med id
        clean_id = medicine_id.strip()
        if clean_id.lower().startswith('med-'):
            # Convert 'med-amx' to 'MED001' or match uppercase
            clean_id = clean_id.upper()
        
        detail = InventoryService.get_medicine_detail(clean_id)
        if not detail:
            # Fallback search by prefix or lowercase
            all_meds = InventoryService.get_all_medicines_summary()
            match = next((m for m in all_meds if m['medicine_id'].lower() == clean_id.lower() or clean_id.lower() in m['medicine_name'].lower()), None)
            if match:
                detail = InventoryService.get_medicine_detail(match['medicine_id'])

        if not detail:
            return jsonify({
                'status': 'error',
                'message': f"Medicine with identifier '{medicine_id}' not found."
            }), 404

        return jsonify({
            'status': 'success',
            'data': detail
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@inventory_bp.route('/medicines/<medicine_id>/demand-trend', methods=['GET'])
def get_demand_trend(medicine_id):
    """Returns historical daily demand series combined with future ML forecast."""
    try:
        horizon = request.args.get('horizon', 30, type=int)
        clean_id = medicine_id.strip().upper()
        trend = InventoryService.get_demand_trend(clean_id, horizon_days=horizon)
        return jsonify({
            'status': 'success',
            'data': trend
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@inventory_bp.route('/fefo/<medicine_id>', methods=['GET'])
def get_fefo_queue(medicine_id):
    """Returns active batches sorted strictly by FEFO (First Expiry, First Out)."""
    try:
        clean_id = medicine_id.strip().upper()
        detail = InventoryService.get_medicine_detail(clean_id)
        if not detail:
            return jsonify({
                'status': 'error',
                'message': f"Medicine '{medicine_id}' not found."
            }), 404

        usable_batches = [b for b in detail.get('batches_detail', []) if b.get('is_usable')]
        return jsonify({
            'status': 'success',
            'medicine_id': clean_id,
            'fefo_priority_batch': detail.get('fefo_priority_batch'),
            'batches': usable_batches
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@inventory_bp.route('/search', methods=['GET'])
def search_inventory():
    """Searches medicines catalog from SQLite with dynamic stock & risk filtering."""
    try:
        q = request.args.get('q') or request.args.get('query') or ''
        cat = request.args.get('category')
        risk = request.args.get('risk_level')
        results = InventoryService.search_medicines(query=q, category=cat, risk_level=risk)
        return jsonify({
            'status': 'success',
            'count': len(results),
            'data': results
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@inventory_bp.route('/sale', methods=['POST'])
def inventory_sale_alias():
    """Direct alias to simulate_medicine_sale for inventory interactions."""
    try:
        data = request.get_json() or {}
        med_id = data.get('medicine_id')
        qty = int(data.get('quantity', 0))
        channel = data.get('sales_channel', 'Digital Shelf Dispensing')
        loc = data.get('location_id')

        if not med_id or qty <= 0:
            return jsonify({'status': 'error', 'message': 'Valid medicine_id and positive quantity required.'}), 400

        result = InventoryService.simulate_medicine_sale(med_id, qty, channel, loc)
        return jsonify({'status': 'success', 'data': result}), 200
    except ValueError as ve:
        return jsonify({'status': 'error', 'message': str(ve)}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

