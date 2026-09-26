# -*- coding: utf-8 -*-
"""
Reorder History & Procurement Lifecycle Service for MediStock (Tier 1 & Tier 2).
Manages dynamic replenishment recommendations, status transitions, and procurement audits.
"""
import sqlite3
from datetime import datetime
from backend.database.db import get_db_connection
from backend.services.inventory_service import InventoryService, CURRENT_DATE_STR

class ReorderService:

    @staticmethod
    def sync_recommendations_from_inventory():
        """Generates dynamic reorder records strictly from medicines requiring restock."""
        all_meds = InventoryService.get_all_medicines_summary()
        reorder_candidates = [m for m in all_meds if m['reorder_required']]

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT medicine_id, status FROM reorder_history WHERE status IN ('Recommended', 'Pending', 'Approved', 'Ordered');")
        existing = {r['medicine_id']: r['status'] for r in cursor.fetchall()}

        synced_count = 0
        for m in reorder_candidates:
            med_id = m['medicine_id']
            if med_id not in existing:
                reorder_id = f"RO-{med_id}-{CURRENT_DATE_STR.replace('-', '')}"
                cursor.execute("""
                    INSERT OR REPLACE INTO reorder_history (
                        reorder_id, medicine_id, created_date, current_stock, predicted_demand,
                        recommended_qty, lead_time_days, risk_level, reason, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    reorder_id,
                    med_id,
                    CURRENT_DATE_STR,
                    m['usable_stock'],
                    m['predicted_30d_demand'],
                    m['recommended_reorder_qty'],
                    m['lead_time_days'],
                    m['risk_level'],
                    m['reorder_reason'],
                    'Recommended'
                ))
                synced_count += 1

        conn.commit()
        conn.close()
        return synced_count

    @staticmethod
    def get_reorder_history(status_filter=None, query=None):
        """Returns list of reorder records joined with medicine details."""
        ReorderService.sync_recommendations_from_inventory()

        conn = get_db_connection()
        cursor = conn.cursor()

        sql = """
            SELECT 
                r.reorder_id,
                r.medicine_id,
                m.medicine_name,
                m.category,
                m.unit_price_inr,
                r.created_date,
                r.current_stock,
                r.predicted_demand,
                r.recommended_qty,
                r.lead_time_days,
                r.risk_level,
                r.reason,
                r.status,
                (r.recommended_qty * m.unit_price_inr) as estimated_cost_inr
            FROM reorder_history r
            JOIN medicines m ON r.medicine_id = m.medicine_id
        """
        conditions = []
        params = []

        if status_filter and status_filter.lower() != 'all':
            conditions.append("LOWER(r.status) = LOWER(?)")
            params.append(status_filter)

        if query:
            q = f"%{query.strip().lower()}%"
            conditions.append("(LOWER(r.reorder_id) LIKE ? OR LOWER(m.medicine_name) LIKE ? OR LOWER(m.category) LIKE ?)")
            params.extend([q, q, q])

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += " ORDER BY r.created_date DESC, r.recommended_qty DESC;"

        cursor.execute(sql, tuple(params))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def get_reorder_summary():
        """Calculates dynamic KPI summary across all reorder events."""
        ReorderService.sync_recommendations_from_inventory()

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                COUNT(*) as total_events,
                SUM(CASE WHEN status = 'Recommended' THEN 1 ELSE 0 END) as recommended_count,
                SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) as pending_count,
                SUM(CASE WHEN status = 'Ordered' THEN 1 ELSE 0 END) as ordered_count,
                SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as completed_count,
                COALESCE(SUM(r.recommended_qty), 0) as total_units_reordered,
                COALESCE(SUM(r.recommended_qty * m.unit_price_inr), 0.0) as total_procurement_cost_inr
            FROM reorder_history r
            JOIN medicines m ON r.medicine_id = m.medicine_id;
        """)
        row = dict(cursor.fetchone())
        conn.close()
        return row

    @staticmethod
    def update_status(reorder_id, new_status):
        """Updates procurement status of a reorder record (e.g. Approved, Ordered, Completed, Cancelled)."""
        valid_statuses = ['Recommended', 'Pending', 'Approved', 'Ordered', 'Completed', 'Cancelled']
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status '{new_status}'. Allowed: {valid_statuses}")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE reorder_history SET status = ? WHERE reorder_id = ?;", (new_status, reorder_id))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

    @staticmethod
    def create_manual_reorder(medicine_id, quantity, reason='Manual Procurement Override'):
        """Creates an explicit reorder action from the operations dashboard."""
        # Calculate current telemetry first (avoids holding an open db connection)
        detail = InventoryService.get_medicine_detail(medicine_id)
        if not detail:
            raise ValueError(f"Medicine '{medicine_id}' not found.")

        conn = get_db_connection()
        cursor = conn.cursor()

        reorder_id = f"RO-{detail['medicine_id']}-{datetime.now().strftime('%Y%m%d%H%M%S%f')[:17]}"
        cursor.execute("""
            INSERT OR REPLACE INTO reorder_history (
                reorder_id, medicine_id, created_date, current_stock, predicted_demand,
                recommended_qty, lead_time_days, risk_level, reason, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            reorder_id,
            detail['medicine_id'],
            CURRENT_DATE_STR,
            detail['usable_stock'],
            detail['predicted_30d_demand'],
            quantity,
            detail['lead_time_days'],
            detail['risk_level'],
            reason,
            'Pending'
        ))
        conn.commit()
        conn.close()

        return {
            'reorder_id': reorder_id,
            'medicine_id': detail['medicine_id'],
            'medicine_name': detail['medicine_name'],
            'quantity': quantity,
            'status': 'Pending'
        }
