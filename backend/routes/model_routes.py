# -*- coding: utf-8 -*-
"""
ML Model Comparison REST API endpoints for MediStock (Tier 3).
Exposes real empirical performance metrics across multiple regression models.
"""
from flask import Blueprint, jsonify, request
from backend.ml.compare import ModelComparisonService

model_bp = Blueprint('models', __name__)

@model_bp.route('/comparison', methods=['GET'])
@model_bp.route('/compare', methods=['GET'])
def get_model_comparison():
    """
    Returns empirical evaluation metrics (MAE, RMSE, R²) for regression models
    trained on historical transaction data.
    """
    try:
        force_retrain = request.args.get('retrain', 'false').lower() == 'true'
        comparison_data = ModelComparisonService.get_comparison(force_retrain=force_retrain)
        return jsonify({
            'status': 'success',
            'data': comparison_data
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f"Model comparison failed: {str(e)}"
        }), 500
