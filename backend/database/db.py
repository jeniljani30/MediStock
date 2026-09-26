# -*- coding: utf-8 -*-
"""
Database Connection and Schema Manager for MediStock SQLite Database.
"""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'database', 'medistock.db')

def get_db_connection():
    """Returns a SQLite connection with Row factory enabled."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Initializes the database schema using actual dataset structures."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Medicines Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS medicines (
        medicine_id TEXT PRIMARY KEY,
        medicine_name TEXT NOT NULL,
        category TEXT NOT NULL,
        dosage_form TEXT NOT NULL,
        manufacturer TEXT NOT NULL,
        unit_price_inr REAL NOT NULL,
        shelf_life_days INTEGER NOT NULL
    );
    """)

    # 2. Suppliers Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS suppliers (
        supplier_id TEXT PRIMARY KEY,
        supplier_name TEXT NOT NULL,
        city TEXT,
        state TEXT
    );
    """)

    # 3. Locations Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS locations (
        location_id TEXT PRIMARY KEY,
        location_name TEXT NOT NULL,
        city TEXT,
        state TEXT,
        storage_location TEXT
    );
    """)

    # 4. Inventory Batches Table (Source of truth for stock & batches)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory_batches (
        batch_id TEXT PRIMARY KEY,
        medicine_id TEXT NOT NULL,
        batch_date TEXT NOT NULL,
        expiry_date TEXT NOT NULL,
        quantity_received INTEGER NOT NULL,
        current_stock INTEGER NOT NULL,
        supplier_id TEXT,
        location_id TEXT,
        FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id),
        FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
        FOREIGN KEY (location_id) REFERENCES locations(location_id)
    );
    """)

    # 5. Sales Transactions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sales_transactions (
        transaction_id TEXT PRIMARY KEY,
        date TEXT NOT NULL,
        medicine_id TEXT NOT NULL,
        batch_id TEXT NOT NULL,
        quantity_sold INTEGER NOT NULL,
        selling_price_inr REAL NOT NULL,
        location_id TEXT NOT NULL,
        sales_channel TEXT NOT NULL,
        FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id),
        FOREIGN KEY (batch_id) REFERENCES inventory_batches(batch_id),
        FOREIGN KEY (location_id) REFERENCES locations(location_id)
    );
    """)

    # 6. Reorder History Table (Foundation for procurement lifecycle)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reorder_history (
        reorder_id TEXT PRIMARY KEY,
        medicine_id TEXT NOT NULL,
        created_date TEXT NOT NULL,
        current_stock INTEGER NOT NULL,
        predicted_demand REAL NOT NULL,
        recommended_qty INTEGER NOT NULL,
        lead_time_days INTEGER NOT NULL DEFAULT 14,
        risk_level TEXT NOT NULL,
        reason TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Recommended',
        FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id)
    );
    """)

    # Indices for high performance queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_batches_med ON inventory_batches(medicine_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_batches_exp ON inventory_batches(expiry_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_med_date ON sales_transactions(medicine_id, date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reorder_med ON reorder_history(medicine_id);")

    conn.commit()
    conn.close()
    print("[DB] SQLite database initialized successfully at:", DB_PATH)

if __name__ == '__main__':
    init_db()
    from backend.models.ingest import ingest_all
    ingest_all()
