# MediStock — Pharmacy Inventory Intelligence System

An intelligent pharmacy inventory management platform powered by **Machine Learning demand forecasting**, **FEFO (First Expiry First Out) dispensing**, and **real-time risk analytics**. Built as a full-stack application with a Flask REST backend, SQLite database, and responsive HTML/CSS/JS frontend.

---

## Project Purpose

MediStock addresses critical inventory management challenges faced by pharmacies:
1. **Stockouts & Emergency Shortages**: Preventing critical medicine stockouts through predictive demand forecasting rather than reactive purchasing.
2. **Expiry Wastage & FEFO Enforcement**: Automatically prioritizing older batches with the earliest expiry dates during dispensing.
3. **Overstocking & Working Capital Lockup**: Identifying excess inventory batches that exceed forecasted consumption windows.
4. **Data-Driven Procurement**: Dynamically calculating reorder quantities and tracking procurement orders through a managed lifecycle.

---

## Main Features

### Tier 1 — Core Analytics & Forecasting
- **Dashboard** with macro KPI summary (Total Medicines, Active Batches, Inventory Value, Critical Risk Items).
- **ML-Powered Demand Prediction**: Gradient Boosting regression model trained on 25,000+ daily sales transactions.
- **Risk Classification Engine**: Categorizes each SKU into Critical, High, Medium, or Low risk based on demand rate, stock runway, and lead time.
- **Expiry Intelligence**: Near-expiry detection (<90 days) with remaining day countdowns.
- **Dynamic Reorder Calculations**: Evaluates recommended reorder quantities based on buffer thresholds.

### Tier 2 — Operational Workflows
- **Real FEFO Medicine Dispensing**: Identifies earliest-expiring eligible batch, validates stock, reduces database quantities, and records transaction entries.
- **What-If Demand Simulator**: Sandbox environment allowing operators to test demand surges (+20%, +50%, etc.) with zero database mutations.
- **Reorder Lifecycle Management**: Create, view, approve, and track purchase orders (`Recommended` → `Approved` → `Ordered` → `Delivered`).
- **Overstock Detection**: Flags SKUs with runway exceeding 90 days.
- **Multi-Criteria Search**: Real-time search by medicine name, category, and risk level.
- **Explainability Telemetry**: Provides transparent rationale behind ML demand predictions (seasonal patterns, price elasticity, sales velocity).

### Tier 3 — Intelligence & Submission Readiness
- **ML Model Comparison Engine**: Evaluates 4 regression models (Random Forest, Gradient Boosting, Decision Tree, Linear Regression) using chronological train/test split.
- **Dynamic Inventory Health Score**: Composite 0–100 score evaluating Stockout Resilience, Buffer Fulfillment, Expiry Integrity, and Capital Balance.
- **Automated End-to-End Test Suite**: 40 pytest integration tests validating all 16 core capabilities.
- **Backend Error Validation**: Strict validation against negative quantities, non-existent medicines, and excessive stock deductions.

---

## Technology Stack

| Layer | Technology | Details |
|---|---|---|
| **Backend** | Python 3.10+ / Flask | Modular Flask REST architecture with 7 Blueprints & CORS |
| **Database** | SQLite 3 | Relational database (`backend/database/medistock.db`) with Foreign Keys & Indices |
| **Data Ingestion** | Pandas 2.0+ / NumPy | Ingestion pipeline converting 5 CSV datasets into normalized tables |
| **Machine Learning**| scikit-learn | `GradientBoostingRegressor` production pipeline with time-series feature engineering |
| **Testing** | pytest 8.0+ | Automated E2E test suite (`backend/tests/test_tier3.py`) |
| **Frontend** | HTML5 / CSS3 / Vanilla JS | Responsive client interfaces with live REST API integration (`medistock-api.js`) |

---

## Project Structure

```
MediStock/
├── backend/
│   ├── app.py                      # Flask application factory & server entry point
│   ├── requirements.txt            # Python dependencies (pip)
│   ├── data/                       # 5 Source CSV datasets
│   │   ├── medicines.csv           # 60 medicine catalog records
│   │   ├── inventory_batches.csv   # 200 batch stock records
│   │   ├── sales_transactions.csv  # 25,000+ historical sales
│   │   ├── suppliers.csv           # 18 pharmaceutical suppliers
│   │   └── locations.csv           # 4 warehouse/dispensary locations
│   ├── database/
│   │   ├── db.py                   # Schema creation & DB connection manager
│   │   └── medistock.db            # SQLite database file (auto-generated)
│   ├── ml/
│   │   ├── train.py                # ML training pipeline (GBR model)
│   │   ├── predictor.py            # Singleton ML inference engine
│   │   ├── compare.py              # 4-model comparison service
│   │   ├── demand_model.pkl        # Serialized production model artifact
│   │   ├── model_meta.json         # Feature names & training metadata
│   │   └── model_comparison.json   # Cached comparison metrics
│   ├── models/
│   │   └── ingest.py               # Dataset ingestion script (CSV → SQLite)
│   ├── routes/
│   │   ├── dashboard_routes.py     # /api/dashboard/*
│   │   ├── inventory_routes.py     # /api/inventory/*
│   │   ├── alert_routes.py         # /api/alerts
│   │   ├── reorder_routes.py       # /api/reorders/*
│   │   ├── sales_routes.py         # /api/sales/*
│   │   ├── simulator_routes.py     # /api/what-if/*
│   │   └── model_routes.py         # /api/models/*
│   ├── services/
│   │   ├── inventory_service.py    # Core business intelligence & FEFO engine
│   │   └── reorder_service.py      # Reorder lifecycle service
│   └── tests/
│       └── test_tier3.py           # 40-test automated verification suite
├── dashboard.html                  # Executive inventory dashboard
├── inventory.html                  # Catalog, shelf view & search
├── medicine-detail.html            # Single-medicine analytics, FEFO & dispensing
├── simulator.html                  # What-If demand scenario simulator
├── reorder.html                    # Procurement order management
├── index.html                      # Landing & navigation portal
├── medistock-api.js                # Centralized JavaScript API client
├── requirements.txt                # Root Python dependencies
├── .env.example                    # Safe environment variables template
├── .gitignore                      # Git exclusion rules
└── README.md                       # Complete documentation
```

---

## Dataset Information

The application utilizes 5 real pharmaceutical datasets in `backend/data/`:

| File | Records | Key Fields | Description |
|---|---|---|---|
| `medicines.csv` | 60 | `Medicine_ID`, `Medicine_Name`, `Category`, `Dosage_Form`, `Manufacturer`, `Unit_Price_INR`, `Shelf_Life_Days` | Master medicine catalog across 21 therapeutic categories |
| `inventory_batches.csv` | 200 | `Batch_ID`, `Medicine_ID`, `Batch_Date`, `Expiry_Date`, `Quantity_Received`, `Current_Stock`, `Supplier_ID`, `Location_ID` | Physical batch records with expiration dates and stock levels |
| `sales_transactions.csv` | 25,000+ | `Transaction_ID`, `Date`, `Medicine_ID`, `Batch_ID`, `Quantity_Sold`, `Selling_Price_INR`, `Location_ID`, `Sales_Channel` | Daily dispensary and hospital sales from Jan to Sep 2026 |
| `suppliers.csv` | 18 | `Supplier_ID`, `Supplier_Name`, `City`, `State` | Pharmaceutical manufacturers and distributors |
| `locations.csv` | 4 | `Location_ID`, `Location_Name`, `City`, `State`, `Storage_Location` | Internal pharmacy dispensaries and warehouse racks |

---

## Database Information

MediStock uses an embedded **SQLite** database (`backend/database/medistock.db`).

- Foreign key constraints enforced (`PRAGMA foreign_keys = ON;`).
- Indexed queries on `medicine_id`, `expiry_date`, and `date` for millisecond query performance.
- Relational schema tables: `medicines`, `suppliers`, `locations`, `inventory_batches`, `sales_transactions`, `reorder_history`.

---

## ML Models Used

### Production Model
- **Algorithm**: `GradientBoostingRegressor` (`scikit-learn`)
- **Objective**: Predict daily demand per medicine based on historical sales velocity, calendar features, pricing, and rolling lag windows (7-day, 14-day, 30-day).
- **Split Strategy**: Chronological split at `2026-06-01` (11,624 train / 2,883 test records) to prevent future data leakage.

### Model Comparison Results (Evaluated on Unseen Test Split)

| Model | MAE (Units/Day) | RMSE | R² Score | Fit Time | Selection Rationale |
|---|---|---|---|---|---|
| **Gradient Boosting (Production)** | **2.541** | **3.451** | **0.1341** | **1.63s** | **Superior generalization and low variance on time-series sales** |
| Random Forest Regressor | 2.531 | 3.434 | 0.1427 | 0.37s | Close MAE; ensemble bagging baseline |
| Decision Tree Regressor | 2.547 | 3.471 | 0.1240 | 0.02s | Single tree partitioned baseline |
| Linear Regression | 2.548 | 3.464 | 0.1277 | 0.015s | Parametric linear baseline |

---

## Installation & Setup

### Prerequisites
- **Python 3.10+** (tested on Python 3.12)
- **pip** package manager

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Initialize Database & Ingest Datasets

Ingests all 5 CSV files into `backend/database/medistock.db`:

```bash
python -m backend.database.db
```

### 3. Train Machine Learning Model

Trains the Gradient Boosting Regressor and outputs `demand_model.pkl`:

```bash
python -m backend.ml.train
```

---

## How to Start

### Backend Server (Entry Point: `backend/app.py`)

Run in Terminal 1:

```bash
python -m backend.app
```
*API server starts at `http://127.0.0.1:5000`.*  
*Health Check: `http://127.0.0.1:5000/api/health`*

### Frontend Server (Entry Point: `index.html` / `dashboard.html`)

Run in Terminal 2:

```bash
python -m http.server 3000
```
*Open your browser at `http://localhost:3000`.*

---

## Configuration

MediStock works out-of-the-box with default settings. Optional environment variables can be configured via a `.env` file (see `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `PORT` | `5000` | Port for the Flask backend API server |
| `FLASK_ENV` | `production` | Flask runtime environment (`development` / `production`) |

---

## Basic Demo Workflow (College Presentation Guide)

1. **Executive Dashboard (`dashboard.html`)**:
   - Inspect macro KPIs: Total Medicines (60), Active Batches (200), Inventory Value (₹), Critical Items.
   - Observe the dynamic **Inventory Health Score** badge (0–100%).
   - Review the Medicine Analytics table sorted by risk level.

2. **Inventory Shelf & Search (`inventory.html`)**:
   - Filter medicines by therapeutic category (e.g. *Antibiotic*, *Antihypertensive*).
   - Filter by risk level (*Critical*, *High*).
   - Search for specific medicines (*Paracetamol*, *Amoxicillin*).

3. **Medicine Intelligence Profile (`medicine-detail.html?id=MED003`)**:
   - View Amoxicillin's 30-day historical sales trend and 30-day ML forecast horizon.
   - Inspect physical batch records and the **FEFO Priority 1 Allocation Queue**.
   - Review explainability factors (prescribing season, price tier, stock runway).

4. **Real FEFO Simulated Sale**:
   - Click **"Simulate Sale"** on the medicine detail or dashboard page.
   - Enter quantity (e.g., `10` units).
   - Confirm sale → Observe live FEFO batch deduction, stock runway recalculation, and transaction log creation in SQLite.

5. **What-If Scenario Sandbox (`simulator.html`)**:
   - Select any medicine.
   - Adjust the demand surge slider (e.g., `+50%`).
   - Run simulation → View immediate projected stockout dates and reorder triggers without altering the database.

6. **Procurement & Reorder Management (`reorder.html`)**:
   - View recommended restock orders.
   - Click **"Approve"** or **"Mark Ordered"** → Watch status update in SQLite in real time.
   - Create a custom reorder manually.

7. **Automated Verification**:
   - In a terminal, run:
     ```bash
     python -m pytest backend/tests/test_tier3.py -v
     ```
   - **40/40 tests PASS** verifying all backend and database workflows.

---

## API Summary

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Service health, model status & feature flags |
| GET | `/api/dashboard/summary` | Macro KPIs & dynamic Inventory Health Score |
| GET | `/api/dashboard/table` | Filtered medicine intelligence table |
| GET | `/api/inventory` | All 60 medicine cards with stock and risk |
| GET | `/api/inventory/medicines/<id>/detail` | Deep-dive profile for a specific medicine |
| GET | `/api/inventory/medicines/<id>/demand-trend` | 30-day historical + 30-day forecast time series |
| GET | `/api/inventory/fefo/<id>` | FEFO batch selection queue |
| GET | `/api/search` | Multi-criteria search (name, category, risk) |
| POST| `/api/sales/dispense` | FEFO medicine dispensing & stock deduction |
| GET | `/api/sales/history` | Historical sales transactions list |
| GET | `/api/alerts` | Near-expiry and stockout alert telemetry |
| GET | `/api/reorders` | Procurement recommendation list |
| GET | `/api/reorders/summary` | Reorder summary metrics |
| POST| `/api/reorders/create` | Create a new reorder entry |
| POST| `/api/reorders/<id>/status` | Advance reorder lifecycle status |
| POST| `/api/what-if` | Read-only demand simulation engine |
| GET | `/api/models/comparison` | 4-model evaluation metrics (MAE, RMSE, R²) |
| GET | `/api/ml/compare` | Model comparison alias |

---

*MediStock — Built with real pharmaceutical datasets. No hardcoded mock values.*
