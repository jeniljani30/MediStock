# -*- coding: utf-8 -*-
"""
Inventory Intelligence & Business Logic Service for MediStock (Tier 1 & Tier 2).
Performs dynamic calculations for stock, coverage, risk, reorders, expiry, FEFO, alerts,
real simulated medicine sales, What-If simulation, explainability, and search.

ABSOLUTE RULE: NO HARDCODED CHANGING VALUES.
All outputs are computed dynamically from SQLite and the trained scikit-learn model.
"""
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from backend.database.db import DB_PATH, get_db_connection
from backend.ml.predictor import predictor

# Reference current operational date matching the dataset window
CURRENT_DATE_STR = '2026-09-26'
CURRENT_DATE = datetime.strptime(CURRENT_DATE_STR, '%Y-%m-%d')
NEAR_EXPIRY_THRESHOLD_DAYS = 90
DEFAULT_LEAD_TIME_DAYS = 14
TARGET_BUFFER_DAYS = 45
OVERSTOCK_THRESHOLD_DAYS = 90

class InventoryService:

    @staticmethod
    def get_all_medicines_summary():
        """Calculates dynamic inventory intelligence across all medicines in catalog."""
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT medicine_id, medicine_name, category, dosage_form, manufacturer, unit_price_inr, shelf_life_days
            FROM medicines
            ORDER BY medicine_id ASC;
        """)
        med_rows = cursor.fetchall()

        cursor.execute("""
            SELECT batch_id, medicine_id, batch_date, expiry_date, quantity_received, current_stock, supplier_id, location_id
            FROM inventory_batches;
        """)
        batch_rows = cursor.fetchall()
        conn.close()

        batches_by_med = {}
        for b in batch_rows:
            med_id = b['medicine_id']
            if med_id not in batches_by_med:
                batches_by_med[med_id] = []
            batches_by_med[med_id].append(dict(b))

        results = []
        for med in med_rows:
            med_id = med['medicine_id']
            batches = batches_by_med.get(med_id, [])
            med_dict = dict(med)
            intelligence = InventoryService._calculate_medicine_intelligence(med_dict, batches)
            results.append(intelligence)

        return results

    @staticmethod
    def get_medicine_detail(medicine_id):
        """Calculates deep intelligence profile for a single medicine."""
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT medicine_id, medicine_name, category, dosage_form, manufacturer, unit_price_inr, shelf_life_days
            FROM medicines
            WHERE medicine_id = ?;
        """, (medicine_id,))
        med_row = cursor.fetchone()

        if not med_row:
            # Fallback search by case-insensitive matching
            cursor.execute("""
                SELECT medicine_id, medicine_name, category, dosage_form, manufacturer, unit_price_inr, shelf_life_days
                FROM medicines
                WHERE LOWER(medicine_id) = LOWER(?) OR LOWER(medicine_name) LIKE ?;
            """, (medicine_id, f"%{medicine_id.lower()}%"))
            med_row = cursor.fetchone()

        if not med_row:
            conn.close()
            return None

        actual_id = med_row['medicine_id']

        cursor.execute("""
            SELECT batch_id, medicine_id, batch_date, expiry_date, quantity_received, current_stock, supplier_id, location_id
            FROM inventory_batches
            WHERE medicine_id = ?
            ORDER BY expiry_date ASC;
        """, (actual_id,))
        batch_rows = [dict(r) for r in cursor.fetchall()]

        # Query recent sales transactions for this medicine
        cursor.execute("""
            SELECT transaction_id, date, batch_id, quantity_sold, selling_price_inr, location_id, sales_channel
            FROM sales_transactions
            WHERE medicine_id = ?
            ORDER BY date DESC, transaction_id DESC
            LIMIT 50;
        """, (actual_id,))
        tx_rows = [dict(r) for r in cursor.fetchall()]

        conn.close()

        med_dict = dict(med_row)
        intelligence = InventoryService._calculate_medicine_intelligence(med_dict, batch_rows)
        intelligence['recent_transactions'] = tx_rows
        intelligence['batches_detail'] = batch_rows
        intelligence['explainability_factors'] = InventoryService.get_explainability_factors(actual_id, intelligence)

        return intelligence

    @staticmethod
    def _calculate_medicine_intelligence(med_dict, batches):
        """Pure dynamic calculation of all operational metrics from real records."""
        med_id = med_dict['medicine_id']
        total_physical_stock = 0
        usable_stock = 0
        expired_stock = 0
        near_expiry_stock = 0

        earliest_expiry_date = None
        earliest_expiry_days = float('inf')
        fefo_eligible_batch = None

        processed_batches = []
        for b in batches:
            b_exp = datetime.strptime(b['expiry_date'], '%Y-%m-%d')
            days_until_exp = (b_exp - CURRENT_DATE).days
            b['days_until_expiry'] = days_until_exp

            stock = b['current_stock']
            total_physical_stock += stock

            if days_until_exp <= 0:
                b['expiry_status'] = 'Expired'
                b['is_usable'] = False
                expired_stock += stock
            else:
                b['is_usable'] = True
                usable_stock += stock
                if days_until_exp <= NEAR_EXPIRY_THRESHOLD_DAYS:
                    b['expiry_status'] = 'Expiring Soon'
                    near_expiry_stock += stock
                else:
                    b['expiry_status'] = 'Safe'

                if days_until_exp < earliest_expiry_days and stock > 0:
                    earliest_expiry_days = days_until_exp
                    earliest_expiry_date = b['expiry_date']

            processed_batches.append(b)

        # FEFO Sorting: usable batches sorted by earliest expiry
        usable_batches = [b for b in processed_batches if b['is_usable'] and b['current_stock'] > 0]
        usable_batches.sort(key=lambda x: x['days_until_expiry'])

        for idx, b in enumerate(usable_batches):
            b['fefo_priority'] = idx + 1
            b['fefo_label'] = f"Priority {idx + 1}" if idx > 0 else "FEFO Priority 1 (Next Out)"

        if usable_batches:
            fefo_eligible_batch = usable_batches[0]

        # ML Demand Forecast
        pred_res = predictor.predict_horizon(med_id, horizon_days=30, start_date=CURRENT_DATE_STR)
        daily_demand = pred_res['predicted_daily_demand']
        predicted_30d_demand = pred_res['total_predicted_demand']

        # Days Until Stock-out (Usable Stock / Daily Burn)
        lead_time = DEFAULT_LEAD_TIME_DAYS
        if daily_demand > 0.01:
            days_to_stockout = int(np.floor(usable_stock / daily_demand))
        else:
            days_to_stockout = 999 if usable_stock > 0 else 0

        # Stock-out & Overstock Risk Classification
        if usable_stock == 0:
            risk_level = 'Critical (Out of Stock)'
            risk_class = 'crit'
        elif days_to_stockout <= lead_time:
            risk_level = 'Critical'
            risk_class = 'crit'
        elif days_to_stockout <= 20:
            risk_level = 'High Risk'
            risk_class = 'crit'
        elif days_to_stockout <= 35:
            risk_level = 'Moderate'
            risk_class = 'warn'
        elif days_to_stockout > OVERSTOCK_THRESHOLD_DAYS:
            risk_level = 'Overstock'
            risk_class = 'overstock'
        else:
            risk_level = 'Healthy'
            risk_class = 'healthy'

        # Dynamic Reorder Recommendation
        target_buffer_units = int(np.ceil(daily_demand * TARGET_BUFFER_DAYS))
        lead_time_demand = int(np.ceil(daily_demand * lead_time))
        reorder_point = target_buffer_units + lead_time_demand

        if risk_level == 'Overstock':
            recommended_reorder_qty = 0
            reorder_required = False
            reorder_reason = f"Inventory coverage ({days_to_stockout} days) exceeds 90-day horizon; holding costs elevated. Halt replenishment."
        elif usable_stock < reorder_point:
            deficit = reorder_point - usable_stock
            # Round up to convenient lot of 50
            recommended_reorder_qty = int(np.ceil(deficit / 50.0) * 50)
            reorder_required = True
            reorder_reason = f"Usable inventory ({usable_stock:,} units) is below safe buffer ({reorder_point:,} units) given {lead_time}-day lead time."
        else:
            recommended_reorder_qty = 0
            reorder_required = False
            reorder_reason = "Current stock satisfies safety buffer and lead time demand."

        return {
            'medicine_id': med_id,
            'medicine_name': med_dict['medicine_name'],
            'category': med_dict['category'],
            'dosage_form': med_dict['dosage_form'],
            'manufacturer': med_dict['manufacturer'],
            'unit_price_inr': med_dict['unit_price_inr'],
            'shelf_life_days': med_dict['shelf_life_days'],
            # Stock Metrics
            'total_physical_stock': total_physical_stock,
            'usable_stock': usable_stock,
            'expired_stock': expired_stock,
            'near_expiry_stock': near_expiry_stock,
            'active_batches_count': len(usable_batches),
            'total_batches_count': len(processed_batches),
            # Demand & Horizon Metrics
            'predicted_daily_demand': daily_demand,
            'predicted_30d_demand': predicted_30d_demand,
            'days_until_stockout': days_to_stockout,
            # Risk & Reorder Metrics
            'lead_time_days': lead_time,
            'reorder_point': reorder_point,
            'risk_level': risk_level,
            'risk_class': risk_class,
            'recommended_reorder_qty': recommended_reorder_qty,
            'reorder_required': reorder_required,
            'reorder_reason': reorder_reason,
            # Expiry & FEFO Intelligence
            'earliest_expiry_date': earliest_expiry_date,
            'earliest_expiry_days': earliest_expiry_days if earliest_expiry_days < float('inf') else None,
            'fefo_priority_batch': fefo_eligible_batch['batch_id'] if fefo_eligible_batch else None,
            'fefo_available_units': fefo_eligible_batch['current_stock'] if fefo_eligible_batch else 0
        }

    # ══════════════════════════════════════════════════════════
    # TIER 2: REAL SIMULATED MEDICINE SALE WORKFLOW
    # ══════════════════════════════════════════════════════════
    @staticmethod
    def simulate_medicine_sale(medicine_id, quantity, sales_channel='Retail Pharmacy', location_id=None):
        """
        Executes a real database-driven medicine sale:
        1. Validates requested quantity is positive and eligible stock exists.
        2. Selects active, unexpired batches strictly by FEFO (earliest expiry first).
        3. Deducts stock from batches in SQLite.
        4. Inserts new transaction record(s) into sales_transactions table.
        5. Immediately recalculates inventory metrics and returns updated state.
        """
        if quantity <= 0:
            raise ValueError("Requested sale quantity must be greater than zero.")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify medicine exists
        cursor.execute("SELECT medicine_id, medicine_name, unit_price_inr FROM medicines WHERE medicine_id = ?;", (medicine_id,))
        med_row = cursor.fetchone()
        if not med_row:
            # Try case-insensitive lookup
            cursor.execute("SELECT medicine_id, medicine_name, unit_price_inr FROM medicines WHERE LOWER(medicine_id) = LOWER(?);", (medicine_id,))
            med_row = cursor.fetchone()

        if not med_row:
            conn.close()
            raise ValueError(f"Medicine '{medicine_id}' not found in active catalog.")

        actual_med_id = med_row['medicine_id']
        unit_price = med_row['unit_price_inr']

        # Fetch eligible usable batches (expiry_date >= CURRENT_DATE_STR and current_stock > 0) ordered by FEFO
        cursor.execute("""
            SELECT batch_id, expiry_date, current_stock, location_id
            FROM inventory_batches
            WHERE medicine_id = ? AND expiry_date >= ? AND current_stock > 0
            ORDER BY expiry_date ASC, batch_id ASC;
        """, (actual_med_id, CURRENT_DATE_STR))
        eligible_batches = [dict(r) for r in cursor.fetchall()]

        total_usable_stock = sum(b['current_stock'] for b in eligible_batches)
        if total_usable_stock < quantity:
            conn.close()
            raise ValueError(
                f"Requested quantity ({quantity:,} units) exceeds total available usable stock "
                f"({total_usable_stock:,} units) for {med_row['medicine_name']}. Transaction aborted to prevent negative stock."
            )

        # Deduct quantities across batches via FEFO
        remaining_to_deduct = quantity
        allocated_deductions = []

        try:
            for b in eligible_batches:
                if remaining_to_deduct <= 0:
                    break

                batch_stock = b['current_stock']
                deduct_from_batch = min(remaining_to_deduct, batch_stock)
                new_stock = batch_stock - deduct_from_batch

                # Update batch current_stock in SQLite
                cursor.execute(
                    "UPDATE inventory_batches SET current_stock = ? WHERE batch_id = ?;",
                    (new_stock, b['batch_id'])
                )

                # Generate transaction ID
                cursor.execute("SELECT COUNT(*) FROM sales_transactions;")
                txn_seq = cursor.fetchone()[0] + 1
                txn_id = f"TXN{txn_seq:06d}"

                loc = location_id or b['location_id'] or 'LOC001'

                # Record transaction in SQLite
                cursor.execute("""
                    INSERT INTO sales_transactions (
                        transaction_id, date, medicine_id, batch_id, quantity_sold, selling_price_inr, location_id, sales_channel
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """, (txn_id, CURRENT_DATE_STR, actual_med_id, b['batch_id'], deduct_from_batch, unit_price, loc, sales_channel))

                allocated_deductions.append({
                    'transaction_id': txn_id,
                    'batch_id': b['batch_id'],
                    'expiry_date': b['expiry_date'],
                    'units_deducted': deduct_from_batch,
                    'remaining_batch_stock': new_stock,
                    'selling_price_inr': unit_price,
                    'total_revenue_inr': round(deduct_from_batch * unit_price, 2)
                })

                remaining_to_deduct -= deduct_from_batch

            conn.commit()
            predictor.invalidate_cache(actual_med_id)
        except Exception as e:
            conn.rollback()
            conn.close()
            raise e
        finally:
            conn.close()

        # Recalculate medicine intelligence and global dashboard state
        updated_detail = InventoryService.get_medicine_detail(actual_med_id)
        dashboard_summary = InventoryService.get_dashboard_summary()

        return {
            'status': 'success',
            'message': f"Successfully dispensed {quantity:,} units of {med_row['medicine_name']} across {len(allocated_deductions)} FEFO batch(es).",
            'medicine_id': actual_med_id,
            'medicine_name': med_row['medicine_name'],
            'units_dispensed': quantity,
            'allocated_batches': allocated_deductions,
            'updated_usable_stock': updated_detail['usable_stock'],
            'updated_days_until_stockout': updated_detail['days_until_stockout'],
            'updated_risk_level': updated_detail['risk_level'],
            'updated_reorder_qty': updated_detail['recommended_reorder_qty'],
            'updated_reorder_required': updated_detail['reorder_required'],
            'updated_fefo_priority_batch': updated_detail['fefo_priority_batch'],
            'dashboard_summary': dashboard_summary
        }

    # ══════════════════════════════════════════════════════════
    # PURCHASE ORDER STOCK INGESTION
    # ══════════════════════════════════════════════════════════
    @staticmethod
    def add_purchase_stock(medicine_id, quantity, reorder_id=None):
        """
        Records a purchase order receipt into inventory_batches (SQLite).
        - Creates a new batch entry with today as batch_date and 2 years from now as expiry.
        - Updates reorder_history record status to 'Completed' if reorder_id provided.
        - Invalidates the ML prediction cache for this medicine.
        - Returns updated medicine metrics.
        ABSOLUTE RULE: quantity must come from the user-entered value, never hardcoded.
        """
        if quantity <= 0:
            raise ValueError("Purchase quantity must be greater than zero.")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify medicine exists
        cursor.execute(
            "SELECT medicine_id, medicine_name, unit_price_inr FROM medicines WHERE medicine_id = ?;",
            (medicine_id,)
        )
        med_row = cursor.fetchone()
        if not med_row:
            cursor.execute(
                "SELECT medicine_id, medicine_name, unit_price_inr FROM medicines WHERE LOWER(medicine_id) = LOWER(?);",
                (medicine_id,)
            )
            med_row = cursor.fetchone()

        if not med_row:
            conn.close()
            raise ValueError(f"Medicine '{medicine_id}' not found in active catalog.")

        actual_med_id = med_row['medicine_id']

        # Prevent duplicate purchase if this reorder_id already has a Completed status
        if reorder_id:
            cursor.execute(
                "SELECT status FROM reorder_history WHERE reorder_id = ?;",
                (reorder_id,)
            )
            ro_row = cursor.fetchone()
            if ro_row and ro_row['status'] == 'Completed':
                conn.close()
                raise ValueError(
                    f"Reorder '{reorder_id}' is already Completed. Purchase already recorded. Refresh the page."
                )

        # Generate a unique batch_id for the new purchase batch
        cursor.execute("SELECT COUNT(*) FROM inventory_batches;")
        batch_count = cursor.fetchone()[0]
        new_batch_id = f"PO-{actual_med_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{batch_count + 1}"

        # Set batch_date = today, expiry_date = 2 years from now (standard pharma shelf life on purchase)
        batch_date_str = CURRENT_DATE_STR
        expiry_date = (CURRENT_DATE + timedelta(days=730)).strftime('%Y-%m-%d')

        # Get supplier and location from the medicine's existing batches if available
        cursor.execute(
            "SELECT supplier_id, location_id FROM inventory_batches WHERE medicine_id = ? LIMIT 1;",
            (actual_med_id,)
        )
        existing_batch = cursor.fetchone()
        supplier_id = existing_batch['supplier_id'] if existing_batch else 'SUP001'
        location_id = existing_batch['location_id'] if existing_batch else 'LOC001'

        # Insert new batch into inventory_batches
        cursor.execute("""
            INSERT INTO inventory_batches (
                batch_id, medicine_id, batch_date, expiry_date,
                quantity_received, current_stock, supplier_id, location_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            new_batch_id,
            actual_med_id,
            batch_date_str,
            expiry_date,
            quantity,
            quantity,
            supplier_id,
            location_id
        ))

        # Update reorder_history status to Completed and record purchased quantity
        if reorder_id:
            cursor.execute("""
                UPDATE reorder_history
                SET status = 'Completed', recommended_qty = ?
                WHERE reorder_id = ?;
            """, (quantity, reorder_id))

        conn.commit()
        conn.close()

        # Invalidate prediction cache so next request uses updated stock
        predictor.invalidate_cache(actual_med_id)

        # Recalculate updated intelligence
        updated_detail = InventoryService.get_medicine_detail(actual_med_id)
        dashboard_summary = InventoryService.get_dashboard_summary()

        return {
            'status': 'success',
            'message': f"Purchase of {quantity:,} units of {med_row['medicine_name']} recorded. New batch: {new_batch_id}.",
            'medicine_id': actual_med_id,
            'medicine_name': med_row['medicine_name'],
            'units_purchased': quantity,
            'new_batch_id': new_batch_id,
            'updated_usable_stock': updated_detail['usable_stock'],
            'updated_days_until_stockout': updated_detail['days_until_stockout'],
            'updated_risk_level': updated_detail['risk_level'],
            'updated_reorder_required': updated_detail['reorder_required'],
            'dashboard_summary': dashboard_summary
        }

    # ══════════════════════════════════════════════════════════
    # TIER 2: WHAT-IF DEMAND SIMULATOR ENGINE
    # ══════════════════════════════════════════════════════════
    @staticmethod
    def run_what_if_simulation(medicine_id, demand_adjustment_pct):
        """
        Runs a What-If Demand Simulation:
        - Retrieves actual baseline metrics for the medicine.
        - Applies demand adjustment percentage (-50% to +100%).
        - Recalculates simulated runway, days to stockout, risk, and reorder point.
        - Computes deltas against baseline.
        - PURE CALCULATION: Does NOT modify the SQLite database.
        """
        baseline = InventoryService.get_medicine_detail(medicine_id)
        if not baseline:
            raise ValueError(f"Medicine '{medicine_id}' not found.")

        current_stock = baseline['usable_stock']
        baseline_daily = baseline['predicted_daily_demand']
        baseline_30d = baseline['predicted_30d_demand']
        lead_time = baseline['lead_time_days']

        # Multiplier
        mult = max(0.1, 1.0 + (demand_adjustment_pct / 100.0))
        sim_daily = round(baseline_daily * mult, 2)
        sim_30d = int(round(baseline_30d * mult))

        # Simulated Days Until Stockout
        if sim_daily > 0.01:
            sim_days_to_stockout = int(np.floor(current_stock / sim_daily))
        else:
            sim_days_to_stockout = 999 if current_stock > 0 else 0

        # Simulated Risk Level
        if current_stock == 0:
            sim_risk = 'Critical (Out of Stock)'
            sim_risk_class = 'crit'
        elif sim_days_to_stockout <= lead_time:
            sim_risk = 'Critical'
            sim_risk_class = 'crit'
        elif sim_days_to_stockout <= 20:
            sim_risk = 'High Risk'
            sim_risk_class = 'crit'
        elif sim_days_to_stockout <= 35:
            sim_risk = 'Moderate'
            sim_risk_class = 'warn'
        elif sim_days_to_stockout > OVERSTOCK_THRESHOLD_DAYS:
            sim_risk = 'Overstock'
            sim_risk_class = 'overstock'
        else:
            sim_risk = 'Healthy'
            sim_risk_class = 'healthy'

        # Simulated Reorder Point & Quantity
        sim_target_buffer = int(np.ceil(sim_daily * TARGET_BUFFER_DAYS))
        sim_lead_time_demand = int(np.ceil(sim_daily * lead_time))
        sim_reorder_point = sim_target_buffer + sim_lead_time_demand

        if sim_risk == 'Overstock':
            sim_reorder_qty = 0
            sim_reorder_required = False
            sim_reorder_reason = "Simulated demand maintains runway above 90-day overstock threshold."
        elif current_stock < sim_reorder_point:
            deficit = sim_reorder_point - current_stock
            sim_reorder_qty = int(np.ceil(deficit / 50.0) * 50)
            sim_reorder_required = True
            sim_reorder_reason = f"Simulated demand surge creates a {deficit:,} unit deficit against buffer ({sim_reorder_point:,} U)."
        else:
            sim_reorder_qty = 0
            sim_reorder_required = False
            sim_reorder_reason = "Current inventory remains adequate under simulated demand adjustment."

        # Deltas
        delta_demand_30d = sim_30d - baseline_30d
        delta_days_stockout = sim_days_to_stockout - baseline['days_until_stockout']
        delta_reorder_qty = sim_reorder_qty - baseline['recommended_reorder_qty']

        return {
            'medicine_id': baseline['medicine_id'],
            'medicine_name': baseline['medicine_name'],
            'demand_adjustment_pct': demand_adjustment_pct,
            'baseline': {
                'usable_stock': current_stock,
                'predicted_daily_demand': baseline_daily,
                'predicted_30d_demand': baseline_30d,
                'days_until_stockout': baseline['days_until_stockout'],
                'risk_level': baseline['risk_level'],
                'risk_class': baseline['risk_class'],
                'reorder_point': baseline['reorder_point'],
                'recommended_reorder_qty': baseline['recommended_reorder_qty'],
                'reorder_required': baseline['reorder_required']
            },
            'simulation': {
                'usable_stock': current_stock,
                'simulated_daily_demand': sim_daily,
                'simulated_30d_demand': sim_30d,
                'simulated_days_until_stockout': sim_days_to_stockout,
                'simulated_risk_level': sim_risk,
                'simulated_risk_class': sim_risk_class,
                'simulated_reorder_point': sim_reorder_point,
                'simulated_recommended_reorder_qty': sim_reorder_qty,
                'simulated_reorder_required': sim_reorder_required,
                'simulated_reorder_reason': sim_reorder_reason
            },
            'difference': {
                'delta_demand_30d': delta_demand_30d,
                'delta_days_until_stockout': delta_days_stockout,
                'delta_recommended_reorder_qty': delta_reorder_qty,
                'risk_changed': (sim_risk != baseline['risk_level']),
                'reorder_status_changed': (sim_reorder_required != baseline['reorder_required'])
            }
        }

    # ══════════════════════════════════════════════════════════
    # TIER 2: EXPLAINABILITY FACTORS GENERATOR
    # ══════════════════════════════════════════════════════════
    @staticmethod
    def get_explainability_factors(medicine_id, intel=None):
        """Generates factual, data-driven explainability factors from real metrics."""
        if not intel:
            intel = InventoryService.get_medicine_detail(medicine_id)
            if not intel:
                return []

        factors = []
        stock = intel['usable_stock']
        daily = intel['predicted_daily_demand']
        days = intel['days_until_stockout']
        lead = intel['lead_time_days']
        reorder_pt = intel['reorder_point']
        expired = intel['expired_stock']
        near_exp = intel['near_expiry_stock']

        # 1. Lead Time Runway Factor
        if stock == 0:
            factors.append({
                'title': 'Complete Inventory Exhaustion',
                'impact': 'CRITICAL',
                'type': 'factor-crit',
                'tagColor': 'var(--red)',
                'desc': f"Available usable stock is 0 units. Critical stock-out condition active. Immediate restocking required."
            })
        elif days <= lead:
            factors.append({
                'title': 'Lead Time Compression Hazard',
                'impact': 'CRITICAL',
                'type': 'factor-crit',
                'tagColor': 'var(--red)',
                'desc': f"Current inventory coverage ({days} days) has breached supplier replenishment lead time ({lead} days). High stock-out probability before next delivery."
            })
        elif days <= 25:
            factors.append({
                'title': 'Approaching Supplier Lead Time Window',
                'impact': 'ELEVATED RISK',
                'type': 'factor-warn',
                'tagColor': 'var(--orange)',
                'desc': f"Inventory runway ({days} days) is approaching the {lead}-day procurement lead time boundary."
            })
        elif days > OVERSTOCK_THRESHOLD_DAYS:
            factors.append({
                'title': 'Capital Inefficiency & Overstocking',
                'impact': 'HOLDING COST',
                'type': 'factor-info',
                'tagColor': 'var(--blue)',
                'desc': f"Inventory runway ({days} days) substantially exceeds 90-day buffer. Working capital tied up in slow-moving stock."
            })
        else:
            factors.append({
                'title': 'Sufficient Lead Time Buffer',
                'impact': 'OPTIMAL RUNWAY',
                'type': 'factor-info',
                'tagColor': 'var(--green)',
                'desc': f"Current runway ({days} days) comfortably accommodates distributor fulfillment lead time ({lead} days)."
            })

        # 2. Reorder Threshold Factor
        if intel['reorder_required']:
            factors.append({
                'title': 'Buffer Boundary Deficit',
                'impact': 'REORDER REQUIRED',
                'type': 'factor-warn',
                'tagColor': 'var(--orange)',
                'desc': f"Usable inventory ({stock:,} units) is below reorder boundary ({reorder_pt:,} units). System recommends {intel['recommended_reorder_qty']:,} unit replenishment."
            })
        else:
            factors.append({
                'title': 'Adequate Safety Buffer Position',
                'impact': 'BUFFER SATISFIED',
                'type': 'factor-info',
                'tagColor': 'var(--green)',
                'desc': f"Available inventory satisfies 45-day target safety buffer ({reorder_pt:,} units) at {daily} U/day velocity."
            })

        # 3. Expiry & FEFO Constraints
        if expired > 0:
            factors.append({
                'title': 'Regulatory Expiry Quarantine',
                'impact': 'LOCKED STOCK',
                'type': 'factor-crit',
                'tagColor': 'var(--red)',
                'desc': f"{expired:,} units across batch records exceeded expiration date and are quarantined from patient dispensing."
            })
        if near_exp > 0:
            factors.append({
                'title': 'Accelerated FEFO Draw Pressure',
                'impact': 'EXPIRING SOON',
                'type': 'factor-warn',
                'tagColor': 'var(--orange)',
                'desc': f"{near_exp:,} units face expiry within 90 days (Earliest: {intel['earliest_expiry_date']}). Prioritized for immediate FEFO dispensing."
            })

        return factors

    # ══════════════════════════════════════════════════════════
    # TIER 2: MEDICINE SEARCH & FILTERING
    # ══════════════════════════════════════════════════════════
    @staticmethod
    def search_medicines(query='', category=None, risk_level=None):
        """Searches medicines catalog from SQLite with dynamic stock & risk filtering."""
        all_meds = InventoryService.get_all_medicines_summary()
        filtered = []

        q = (query or '').strip().lower()

        for m in all_meds:
            if category and category.lower() != 'all' and category.lower() not in m['category'].lower():
                continue
            if risk_level and risk_level.lower() != 'all' and risk_level.lower() not in m['risk_level'].lower():
                continue
            if q:
                search_target = f"{m['medicine_id']} {m['medicine_name']} {m['category']} {m['manufacturer']} {m['dosage_form']}".lower()
                if q not in search_target:
                    continue

            filtered.append(m)

        return filtered

    @staticmethod
    def get_dashboard_summary():
        """Calculates global macro KPIs for the Command Center Dashboard."""
        all_meds = InventoryService.get_all_medicines_summary()

        total_medicines = len(all_meds)
        low_stock_count = sum(1 for m in all_meds if m['usable_stock'] < m['reorder_point'] and m['usable_stock'] > 0)
        high_risk_count = sum(1 for m in all_meds if m['risk_class'] == 'crit')
        reorder_required_count = sum(1 for m in all_meds if m['reorder_required'])
        near_expiry_count = sum(1 for m in all_meds if m['near_expiry_stock'] > 0)
        expired_meds_count = sum(1 for m in all_meds if m['expired_stock'] > 0)
        overstock_count = sum(1 for m in all_meds if m['risk_class'] == 'overstock')

        total_usable_stock = sum(m['usable_stock'] for m in all_meds)
        total_predicted_demand = sum(m['predicted_30d_demand'] for m in all_meds)
        total_expired_stock = sum(m['expired_stock'] for m in all_meds)

        # Tier 3: Dynamic Inventory Health Score (0 - 100)
        # Component 1: Stockout Resilience (25 pts max)
        score_resilience = 25.0 * (1.0 - (high_risk_count / max(1, total_medicines)))
        # Component 2: Safety Buffer Fulfillment (25 pts max)
        score_buffer = 25.0 * (1.0 - (reorder_required_count / max(1, total_medicines)))
        # Component 3: Regulatory & Expiry Integrity (25 pts max)
        score_expiry = 25.0 * (1.0 - (expired_meds_count / max(1, total_medicines)))
        # Component 4: Capital & Allocation Balance (25 pts max)
        score_capital = 25.0 * (1.0 - (overstock_count / max(1, total_medicines)))

        health_score = round(max(0.0, min(100.0, score_resilience + score_buffer + score_expiry + score_capital)), 1)
        if health_score >= 85:
            health_rating = 'Optimal (Grade A)'
            health_color = 'var(--green)'
        elif health_score >= 70:
            health_rating = 'Stable (Grade B)'
            health_color = 'var(--teal)'
        elif health_score >= 50:
            health_rating = 'Action Required (Grade C)'
            health_color = 'var(--orange)'
        else:
            health_rating = 'Critical Warning (Grade D)'
            health_color = 'var(--red)'

        health_breakdown = {
            'stockout_resilience': round(score_resilience, 1),
            'buffer_fulfillment': round(score_buffer, 1),
            'expiry_integrity': round(score_expiry, 1),
            'capital_balance': round(score_capital, 1)
        }

        return {
            'total_medicines': total_medicines,
            'low_stock_count': low_stock_count,
            'high_risk_count': high_risk_count,
            'overstock_count': overstock_count,
            'reorder_required_count': reorder_required_count,
            'near_expiry_count': near_expiry_count,
            'expired_meds_count': expired_meds_count,
            'total_usable_stock': total_usable_stock,
            'total_predicted_30d_demand': total_predicted_demand,
            'total_expired_stock': total_expired_stock,
            # Health Score Telemetry
            'inventory_health_score': health_score,
            'health_rating': health_rating,
            'health_color': health_color,
            'health_breakdown': health_breakdown
        }

    @staticmethod
    def get_dynamic_alerts():
        """Evaluates database and model to generate real operational alerts."""
        all_meds = InventoryService.get_all_medicines_summary()
        alerts = []

        for m in all_meds:
            if m['risk_class'] == 'crit':
                alerts.append({
                    'type': 'critical',
                    'category': 'crit',
                    'medicine_id': m['medicine_id'],
                    'medicine_name': m['medicine_name'],
                    'title': f"Stock-out Risk: {m['medicine_name']}",
                    'description': f"Coverage is {m['days_until_stockout']} days at {m['predicted_daily_demand']} U/day burn. Distributor replenishment requires {m['lead_time_days']} days.",
                    'timestamp': 'Real-time Telemetry',
                    'tag': 'Stock-out Risk'
                })
            elif m['risk_class'] == 'overstock':
                alerts.append({
                    'type': 'info',
                    'category': 'warn',
                    'medicine_id': m['medicine_id'],
                    'medicine_name': m['medicine_name'],
                    'title': f"Overstock Detected: {m['medicine_name']}",
                    'description': f"Current usable stock ({m['usable_stock']:,} U) provides {m['days_until_stockout']} days coverage. Reorders halted.",
                    'timestamp': 'Working Capital Audit',
                    'tag': 'Overstock'
                })
            elif m['reorder_required']:
                alerts.append({
                    'type': 'warning',
                    'category': 'warn',
                    'medicine_id': m['medicine_id'],
                    'medicine_name': m['medicine_name'],
                    'title': f"Reorder Required: {m['medicine_name']}",
                    'description': f"Available stock ({m['usable_stock']:,} U) breached reorder boundary ({m['reorder_point']:,} U). Recommended order: {m['recommended_reorder_qty']:,} units.",
                    'timestamp': 'Model Evaluation',
                    'tag': 'Reorder Required'
                })

            if m['expired_stock'] > 0:
                alerts.append({
                    'type': 'critical',
                    'category': 'fefo',
                    'medicine_id': m['medicine_id'],
                    'medicine_name': m['medicine_name'],
                    'title': f"Expired Stock Detected: {m['medicine_name']}",
                    'description': f"{m['expired_stock']:,} units across batch records exceeded regulatory expiry date. Excluded by FEFO from dispensing.",
                    'timestamp': 'FEFO Audit',
                    'tag': 'Expired Quarantined'
                })
            elif m['near_expiry_stock'] > 0:
                alerts.append({
                    'type': 'warning',
                    'category': 'fefo',
                    'medicine_id': m['medicine_id'],
                    'medicine_name': m['medicine_name'],
                    'title': f"Near-Expiry Watch: {m['medicine_name']}",
                    'description': f"{m['near_expiry_stock']:,} units expire within 90 days (Earliest: {m['earliest_expiry_date']}). Prioritize FEFO allocation.",
                    'timestamp': 'Expiry Monitor',
                    'tag': 'FEFO Expiring Soon'
                })

        return alerts

    @staticmethod
    def get_demand_trend(medicine_id, horizon_days=30):
        """Provides real historical daily sales series plus future ML prediction curve."""
        conn = get_db_connection()
        query = """
            SELECT date, SUM(quantity_sold) as units_sold
            FROM sales_transactions
            WHERE medicine_id = ?
            GROUP BY date
            ORDER BY date ASC;
        """
        df_hist = pd.read_sql_query(query, conn, params=(medicine_id,))
        conn.close()

        hist_points = []
        for _, row in df_hist.tail(60).iterrows():
            hist_points.append({
                'date': row['date'],
                'units': int(row['units_sold']),
                'type': 'actual'
            })

        pred_res = predictor.predict_horizon(medicine_id, horizon_days=horizon_days, start_date=CURRENT_DATE_STR)
        forecast_points = []
        for p in pred_res['horizon_predictions']:
            forecast_points.append({
                'date': p['date'],
                'units': p['predicted_units'],
                'type': 'predicted'
            })

        return {
            'medicine_id': medicine_id,
            'historical_days_count': len(hist_points),
            'forecast_days_count': len(forecast_points),
            'historical_series': hist_points,
            'forecast_series': forecast_points,
            'predicted_daily_average': pred_res['predicted_daily_demand'],
            'total_forecast_units': pred_res['total_predicted_demand']
        }
