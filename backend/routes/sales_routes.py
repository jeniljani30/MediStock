# -*- coding: utf-8 -*-
"""
Sales & Dispensing REST API endpoints for MediStock (Tier 2).
Handles real FEFO-driven medicine sales, batch deductions, and transaction logging.
"""
from flask import Blueprint, jsonify, request
from backend.services.inventory_service import InventoryService
from backend.database.db import get_db_connection

sales_bp = Blueprint('sales', __name__)

@sales_bp.route('/dispense', methods=['POST'])
def dispense_sale():
    """
    Executes a real database-driven medicine sale:
    Expects JSON: { "medicine_id": str, "quantity": int, "sales_channel": str (optional), "location_id": str (optional) }
    """
    try:
        data = request.get_json() or {}
        medicine_id = data.get('medicine_id')
        quantity = data.get('quantity')
        sales_channel = data.get('sales_channel', 'Counter / Hospital Dispensing')
        location_id = data.get('location_id')

        if not medicine_id:
            return jsonify({'status': 'error', 'message': 'Missing medicine_id.'}), 400
        
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return jsonify({'status': 'error', 'message': 'Invalid quantity. Must be an integer.'}), 400

        if quantity <= 0:
            return jsonify({'status': 'error', 'message': 'Quantity must be greater than zero.'}), 400

        result = InventoryService.simulate_medicine_sale(
            medicine_id=medicine_id,
            quantity=quantity,
            sales_channel=sales_channel,
            location_id=location_id
        )

        return jsonify({
            'status': 'success',
            'data': result
        }), 200
    except ValueError as ve:
        return jsonify({'status': 'error', 'message': str(ve)}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@sales_bp.route('/history', methods=['GET'])
def get_sales_history():
    """Returns recent sales transactions directly from SQLite."""
    try:
        limit = request.args.get('limit', 50, type=int)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.transaction_id, s.date, s.medicine_id, m.medicine_name, s.batch_id, 
                   s.quantity_sold, s.selling_price_inr, (s.quantity_sold * s.selling_price_inr) as total_amount,
                   s.location_id, s.sales_channel
            FROM sales_transactions s
            JOIN medicines m ON s.medicine_id = m.medicine_id
            ORDER BY s.date DESC, s.transaction_id DESC
            LIMIT ?;
        """, (limit,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify({
            'status': 'success',
            'count': len(rows),
            'data': rows
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
