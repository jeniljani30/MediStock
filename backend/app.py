# -*- coding: utf-8 -*-
"""
MediStock Flask Application Factory & Server Entry Point.
Serves Tier 1 & Tier 2 REST APIs for the MediStock frontend platform.
"""
import os
import sys
from flask import Flask, jsonify, request
from flask_cors import CORS

# Add root directory to python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.routes.dashboard_routes import dashboard_bp
from backend.routes.inventory_routes import inventory_bp
from backend.routes.alert_routes import alert_bp
from backend.routes.reorder_routes import reorder_bp
from backend.routes.sales_routes import sales_bp
from backend.routes.simulator_routes import simulator_bp
from backend.routes.model_routes import model_bp
from backend.services.inventory_service import InventoryService
from backend.ml.compare import ModelComparisonService
from backend.ml.predictor import predictor

def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Register Blueprints
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
    app.register_blueprint(inventory_bp, url_prefix='/api/inventory')
    app.register_blueprint(alert_bp, url_prefix='/api/alerts')
    app.register_blueprint(reorder_bp, url_prefix='/api/reorders')
    app.register_blueprint(sales_bp, url_prefix='/api/sales')
    app.register_blueprint(simulator_bp, url_prefix='/api/what-if')
    app.register_blueprint(model_bp, url_prefix='/api/models')

    # Direct top-level aliases requested by API specification
    @app.route('/api/search', methods=['GET'])
    def direct_search():
        q = request.args.get('q') or request.args.get('query') or ''
        cat = request.args.get('category')
        risk = request.args.get('risk_level')
        results = InventoryService.search_medicines(query=q, category=cat, risk_level=risk)
        return jsonify({
            'status': 'success',
            'count': len(results),
            'data': results
        }), 200

    @app.route('/api/ml/compare', methods=['GET'])
    def direct_ml_compare():
        data = ModelComparisonService.get_comparison()
        return jsonify({
            'status': 'success',
            'data': data
        }), 200

    @app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({
            'status': 'healthy',
            'version': '3.0.0-tier3',
            'service': 'MediStock Inventory Intelligence Engine (Tier 3 Demo Ready)',
            'database': 'SQLite connected & synchronized',
            'ml_model': 'GradientBoostingRegressor (Production Baseline)',
            'features': [
                'FEFO Real Dispensing',
                'What-If Simulation Engine',
                'Explainability Telemetry',
                'Overstock & Buffer Controls',
                'Reorder History & Procurement',
                'Model Comparison (Linear, Tree, Forest, GBR)',
                'Dynamic Inventory Health Score'
            ]
        }), 200

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({
            'status': 'error',
            'code': 404,
            'message': 'Requested API endpoint not found.'
        }), 404

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({
            'status': 'error',
            'code': 500,
            'message': 'Internal inventory calculation error.'
        }), 500

    # Pre-warm ML predictions cache for instantaneous inventory and reorder response
    predictor.prewarm()

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("=" * 70)
    print(f"MEDISTOCK TIER 3 BACKEND RUNNING ON http://127.0.0.1:{port}")
    print(f"Health check endpoint: http://127.0.0.1:{port}/api/health")
    print("=" * 70)
    app.run(host='0.0.0.0', port=port, debug=False)
