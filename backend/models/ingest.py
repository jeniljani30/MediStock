# -*- coding: utf-8 -*-
"""
Data Ingestion Pipeline for MediStock Real Datasets.
Loads medicines, suppliers, locations, inventory batches, and sales transactions into SQLite.
"""
import os
import sqlite3
import pandas as pd
from backend.database.db import get_db_connection, init_db, DB_PATH

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')

def ingest_all():
    """Ingests all 5 real datasets into SQLite."""
    print("=" * 70)
    print("STARTING MEDISTOCK DATA INGESTION")
    print("=" * 70)

    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Ingest Medicines
    med_path = os.path.join(DATA_DIR, 'medicines.csv')
    df_med = pd.read_csv(med_path)
    df_med.columns = [c.strip() for c in df_med.columns]
    med_records = []
    for _, row in df_med.iterrows():
        med_records.append((
            str(row['Medicine_ID']).strip(),
            str(row['Medicine_Name']).strip(),
            str(row['Category']).strip(),
            str(row['Dosage_Form']).strip(),
            str(row['Manufacturer']).strip(),
            float(row['Unit_Price_INR']),
            int(row['Shelf_Life_Days'])
        ))
    cursor.executemany("""
    INSERT OR REPLACE INTO medicines (
        medicine_id, medicine_name, category, dosage_form, manufacturer, unit_price_inr, shelf_life_days
    ) VALUES (?, ?, ?, ?, ?, ?, ?);
    """, med_records)
    print(f" [OK] Ingested {len(med_records)} medicines from medicines.csv")

    # 2. Ingest Suppliers
    sup_path = os.path.join(DATA_DIR, 'suppliers.csv')
    df_sup = pd.read_csv(sup_path)
    df_sup.columns = [c.strip() for c in df_sup.columns]
    sup_records = []
    for _, row in df_sup.iterrows():
        sup_records.append((
            str(row['Supplier_ID']).strip(),
            str(row['Supplier_Name']).strip(),
            str(row.get('City', '')).strip(),
            str(row.get('State', '')).strip()
        ))
    cursor.executemany("""
    INSERT OR REPLACE INTO suppliers (supplier_id, supplier_name, city, state)
    VALUES (?, ?, ?, ?);
    """, sup_records)
    print(f" [OK] Ingested {len(sup_records)} suppliers from suppliers.csv")

    # 3. Ingest Locations
    loc_path = os.path.join(DATA_DIR, 'locations.csv')
    df_loc = pd.read_csv(loc_path)
    df_loc.columns = [c.strip() for c in df_loc.columns]
    loc_records = []
    for _, row in df_loc.iterrows():
        loc_records.append((
            str(row['Location_ID']).strip(),
            str(row['Location_Name']).strip(),
            str(row.get('City', '')).strip(),
            str(row.get('State', '')).strip(),
            str(row.get('Storage_Location', '')).strip()
        ))
    cursor.executemany("""
    INSERT OR REPLACE INTO locations (location_id, location_name, city, state, storage_location)
    VALUES (?, ?, ?, ?, ?);
    """, loc_records)
    print(f" [OK] Ingested {len(loc_records)} locations from locations.csv")

    # 4. Ingest Inventory Batches
    batch_path = os.path.join(DATA_DIR, 'inventory_batches.csv')
    df_batch = pd.read_csv(batch_path)
    df_batch.columns = [c.strip() for c in df_batch.columns]
    batch_records = []
    for _, row in df_batch.iterrows():
        batch_records.append((
            str(row['Batch_ID']).strip(),
            str(row['Medicine_ID']).strip(),
            str(row['Batch_Date']).strip(),
            str(row['Expiry_Date']).strip(),
            int(row['Quantity_Received']),
            int(row['Current_Stock']),
            str(row.get('Supplier_ID', '')).strip(),
            str(row.get('Location_ID', '')).strip()
        ))
    cursor.executemany("""
    INSERT OR REPLACE INTO inventory_batches (
        batch_id, medicine_id, batch_date, expiry_date, quantity_received, current_stock, supplier_id, location_id
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, batch_records)
    print(f" [OK] Ingested {len(batch_records)} inventory batches from inventory_batches.csv")

    # 5. Ingest Sales Transactions
    sales_path = os.path.join(DATA_DIR, 'sales_transactions.csv')
    df_sales = pd.read_csv(sales_path)
    df_sales.columns = [c.strip() for c in df_sales.columns]
    sales_records = []
    for _, row in df_sales.iterrows():
        sales_records.append((
            str(row['Transaction_ID']).strip(),
            str(row['Date']).strip(),
            str(row['Medicine_ID']).strip(),
            str(row['Batch_ID']).strip(),
            int(row['Quantity_Sold']),
            float(row['Selling_Price_INR']),
            str(row['Location_ID']).strip(),
            str(row['Sales_Channel']).strip()
        ))
    cursor.executemany("""
    INSERT OR REPLACE INTO sales_transactions (
        transaction_id, date, medicine_id, batch_id, quantity_sold, selling_price_inr, location_id, sales_channel
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, sales_records)
    print(f" [OK] Ingested {len(sales_records)} sales transactions from sales_transactions.csv")

    conn.commit()

    # Integrity verification
    cursor.execute("SELECT COUNT(*) FROM medicines;")
    count_med = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM inventory_batches;")
    count_batch = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM sales_transactions;")
    count_sales = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(current_stock) FROM inventory_batches;")
    total_stock = cursor.fetchone()[0]

    conn.close()

    print("=" * 70)
    print(f"INGESTION COMPLETE & VERIFIED:")
    print(f" - Medicines:          {count_med} records")
    print(f" - Inventory Batches:  {count_batch} records (Total Stock: {total_stock:,} units)")
    print(f" - Sales Transactions: {count_sales:,} records")
    print("=" * 70)

if __name__ == '__main__':
    ingest_all()
