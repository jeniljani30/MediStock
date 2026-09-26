# -*- coding: utf-8 -*-
"""
Reorder History & Procurement REST API endpoints for MediStock (Tier 1 & Tier 2).
"""
from flask import Blueprint, jsonify, request
from backend.services.reorder_service import ReorderService
from backend.services.inventory_service import InventoryService

reorder_bp = Blueprint('reorders', __name__)

@reorder_bp.route('', methods=['GET'])
def get_reorders():
    """Returns reorder recommendations and historical procurement records with status and search filtering."""
    try:
        status_filter = request.args.get('status', 'all')
        query = request.args.get('q') or request.args.get('search') or ''
        records = ReorderService.get_reorder_history(status_filter=status_filter, query=query)
        return jsonify({
            'status': 'success',
            'count': len(records),
            'data': records
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@reorder_bp.route('/summary', methods=['GET'])
def get_reorder_summary():
    """Returns aggregate dynamic procurement metrics across all reorder events."""
    try:
        summary = ReorderService.get_reorder_summary()
        return jsonify({
            'status': 'success',
            'data': summary
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@reorder_bp.route('/create', methods=['POST'])
def create_manual_reorder():
    """Creates a manual procurement order action from the dashboard."""
    try:
        payload = request.get_json() or {}
        medicine_id = payload.get('medicine_id')
        quantity = payload.get('quantity')
        reason = payload.get('reason', 'Manual Procurement Order')

        if not medicine_id:
            return jsonify({'status': 'error', 'message': "Missing 'medicine_id'."}), 400

        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return jsonify({'status': 'error', 'message': "Invalid 'quantity'. Must be an integer."}), 400

        if quantity <= 0:
            return jsonify({'status': 'error', 'message': "Quantity must be greater than zero."}), 400

        result = ReorderService.create_manual_reorder(medicine_id, quantity, reason)
        return jsonify({
            'status': 'success',
            'message': f"Reorder action logged for {result['medicine_name']} ({quantity:,} units).",
            'data': result
        }), 201
    except ValueError as ve:
        return jsonify({'status': 'error', 'message': str(ve)}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@reorder_bp.route('/<reorder_id>/status', methods=['POST'])
def update_reorder_status(reorder_id):
    """Updates the status of a reorder record."""
    try:
        payload = request.get_json() or {}
        new_status = payload.get('status')
        if not new_status:
            return jsonify({
                'status': 'error',
                'message': "Missing 'status' field in request body."
            }), 400

        updated = ReorderService.update_status(reorder_id, new_status)
        if not updated:
            return jsonify({
                'status': 'error',
                'message': f"Reorder record '{reorder_id}' not found."
            }), 404

        return jsonify({
            'status': 'success',
            'message': f"Reorder '{reorder_id}' status updated to '{new_status}'."
        }), 200
    except ValueError as ve:
        return jsonify({
            'status': 'error',
            'message': str(ve)
        }), 400
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@reorder_bp.route('/<reorder_id>/purchase', methods=['POST'])
def issue_purchase_order(reorder_id):
    """
    Confirms a purchase order: adds user-entered stock quantity as a new inventory batch in SQLite.
    Marks the reorder record as Completed.
    All values come from the actual database and user input — no hardcoded quantities.
    """
    try:
        payload = request.get_json() or {}
        medicine_id = payload.get('medicine_id')
        quantity = payload.get('quantity')

        if not medicine_id:
            return jsonify({'status': 'error', 'message': "Missing 'medicine_id' in request."}), 400

        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return jsonify({'status': 'error', 'message': "Invalid 'quantity'. Must be a positive integer."}), 400

        if quantity <= 0:
            return jsonify({'status': 'error', 'message': "Purchase quantity must be greater than zero."}), 400

        result = InventoryService.add_purchase_stock(medicine_id, quantity, reorder_id=reorder_id)
        return jsonify({
            'status': 'success',
            'message': result['message'],
            'data': result
        }), 200
    except ValueError as ve:
        return jsonify({'status': 'error', 'message': str(ve)}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
