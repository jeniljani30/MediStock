/**
 * ══════════════════════════════════════════════════════════════
 * MEDISTOCK CENTRALIZED API CLIENT SERVICE LAYER
 * ══════════════════════════════════════════════════════════════
 *
 * Connected directly to the MediStock Flask Tier 1 Backend.
 * All inventory, batch, risk, demand, FEFO, alert, and reorder
 * values are fetched in real-time from SQLite and the ML Model.
 *
 * ABSOLUTE RULE: NO HARDCODED CHANGING VALUES.
 * ══════════════════════════════════════════════════════════════
 */

window.MediStockAPI = (function () {
    'use strict';

    // ── Configuration ──────────────────────────────────────────
    // Base URL for the MediStock Flask REST API
    const API_BASE = 'http://127.0.0.1:5000/api';

    // Helper for robust fetch with JSON parsing and error handling
    async function _fetchJson(endpoint, options = {}) {
        try {
            const url = `${API_BASE}${endpoint}`;
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                ...options
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                const msg = errorData.message || `HTTP ${response.status}: ${response.statusText}`;
                throw new Error(msg);
            }

            const json = await response.json();
            return json.data !== undefined ? json.data : json;
        } catch (err) {
            console.error(`[MediStockAPI Error] Request to ${endpoint} failed:`, err);
            throw err;
        }
    }

    // ── 1. Dashboard Endpoints ─────────────────────────────────
    /**
     * Fetches high-level macro KPIs computed dynamically from SQLite & ML.
     */
    function getDashboardSummary() {
        return _fetchJson('/dashboard/summary');
    }

    /**
     * Fetches master medicine inventory table with status filtering & search.
     */
    function getDashboardTable(filter = 'all', query = '') {
        const params = new URLSearchParams();
        if (filter) params.append('filter', filter);
        if (query) params.append('q', query);
        return _fetchJson(`/dashboard/table?${params.toString()}`);
    }

    // ── 2. Inventory & Medicine Catalog Endpoints ──────────────
    /**
     * Fetches full inventory with shelf groupings, stock, and batch counts.
     */
    function getInventory() {
        return _fetchJson('/inventory');
    }

    /**
     * Fetches concise medicine list for selectors and quick lookups.
     */
    function getMedicines() {
        return _fetchJson('/inventory/medicines');
    }

    /**
     * Fetches deep analytical intelligence profile for a single medicine.
     * @param {string} medicineId - e.g. 'MED001', 'MED007'
     */
    function getMedicineDetail(medicineId) {
        return _fetchJson(`/inventory/medicines/${encodeURIComponent(medicineId)}/detail`);
    }

    /**
     * Fetches historical daily sales curve + 30-day ML prediction horizon.
     * @param {string} medicineId
     * @param {number} horizonDays
     */
    function getDemandTrend(medicineId, horizonDays = 30) {
        return _fetchJson(`/inventory/medicines/${encodeURIComponent(medicineId)}/demand-trend?horizon=${horizonDays}`);
    }

    /**
     * Fetches active batches for a medicine strictly ordered by FEFO priority.
     * @param {string} medicineId
     */
    function getFefoQueue(medicineId) {
        return _fetchJson(`/inventory/fefo/${encodeURIComponent(medicineId)}`);
    }

    // ── 3. Real-Time Dynamic Alerts ────────────────────────────
    /**
     * Fetches dynamically generated inventory, stock-out, and expiry alerts.
     */
    function getAlerts() {
        return _fetchJson('/alerts');
    }

    // ── 4. Reorder History & Procurement ───────────────────────
    /**
     * Fetches reorder recommendations and lifecycle records.
     * @param {string} statusFilter - 'all', 'Recommended', 'Approved', 'Ordered', 'Completed'
     * @param {string} query - Optional search query
     */
    function getReorderHistory(statusFilter = 'all', query = '') {
        const params = new URLSearchParams();
        if (statusFilter) params.append('status', statusFilter);
        if (query) params.append('q', query);
        return _fetchJson(`/reorders?${params.toString()}`);
    }

    /**
     * Fetches aggregate dynamic procurement metrics across all reorder events.
     */
    function getReorderSummary() {
        return _fetchJson('/reorders/summary');
    }

    /**
     * Creates a manual procurement order action from the operations dashboard.
     * @param {string} medicineId
     * @param {number} quantity
     * @param {string} reason
     */
    function createReorder(medicineId, quantity, reason) {
        return _fetchJson('/reorders/create', {
            method: 'POST',
            body: JSON.stringify({ medicine_id: medicineId, quantity: quantity, reason: reason })
        });
    }

    /**
     * Updates the status of an existing reorder record.
     * @param {string} reorderId
     * @param {string} newStatus
     */
    function updateReorderStatus(reorderId, newStatus) {
        return _fetchJson(`/reorders/${encodeURIComponent(reorderId)}/status`, {
            method: 'POST',
            body: JSON.stringify({ status: newStatus })
        });
    }

    /**
     * Issues a purchase order: adds user-entered quantity as new stock batch in SQLite.
     * medicine_id and quantity come from the actual database record and user input.
     * @param {string} reorderId - Reorder record to mark Completed
     * @param {string} medicineId - Medicine to restock
     * @param {number} quantity - User-entered purchase quantity (must be > 0)
     */
    function issuePurchaseOrder(reorderId, medicineId, quantity) {
        return _fetchJson(`/reorders/${encodeURIComponent(reorderId)}/purchase`, {
            method: 'POST',
            body: JSON.stringify({ medicine_id: medicineId, quantity: quantity })
        });
    }

    // ── 5. Real Simulated Medicine Sales & FEFO Dispensing (Tier 2) ─
    /**
     * Dispenses a medicine sale against real database batches using FEFO allocation.
     * @param {string} medicineId
     * @param {number} quantity
     * @param {string} salesChannel
     * @param {string} locationId
     */
    function dispenseSale(medicineId, quantity, salesChannel = 'Counter / Hospital Dispensing', locationId = null) {
        return _fetchJson('/sales/dispense', {
            method: 'POST',
            body: JSON.stringify({
                medicine_id: medicineId,
                quantity: quantity,
                sales_channel: salesChannel,
                location_id: locationId
            })
        });
    }

    // ── 6. What-If Simulator (Tier 2) ──────────────────────────
    /**
     * Runs pure-calculation What-If demand sensitivity simulation.
     * Does NOT modify the SQLite database.
     * @param {string} medicineId
     * @param {number} demandAdjustmentPct (-50 to +100)
     */
    function runWhatIf(medicineId, demandAdjustmentPct = 0) {
        return _fetchJson('/what-if', {
            method: 'POST',
            body: JSON.stringify({
                medicine_id: medicineId,
                demand_adjustment_pct: demandAdjustmentPct
            })
        });
    }

    // ── 7. Real-Time Medicine Search (Tier 2) ──────────────────
    /**
     * Searches medicines catalog from SQLite with dynamic stock & risk filtering.
     * @param {string} query
     * @param {string} category
     * @param {string} riskLevel
     */
    function searchMedicines(query = '', category = 'all', riskLevel = 'all') {
        const params = new URLSearchParams();
        if (query) params.append('q', query);
        if (category && category !== 'all') params.append('category', category);
        if (riskLevel && riskLevel !== 'all') params.append('risk_level', riskLevel);
        return _fetchJson(`/search?${params.toString()}`);
    }

    // ── 8. ML Model Comparison (Tier 3) ───────────────────────
    /**
     * Fetches empirical evaluation metrics (MAE, RMSE, R²) comparing
     * Linear Regression, Decision Tree, Random Forest, and Gradient Boosting.
     */
    function getModelComparison() {
        return _fetchJson('/models/comparison');
    }

    // ── 9. System Health Check ─────────────────────────────────
    function checkHealth() {
        return _fetchJson('/health');
    }

    // ── Public API Boundary ────────────────────────────────────
    return {
        API_BASE: API_BASE,
        getDashboardSummary: getDashboardSummary,
        getDashboardTable: getDashboardTable,
        getInventory: getInventory,
        getMedicines: getMedicines,
        getMedicineDetail: getMedicineDetail,
        getDemandTrend: getDemandTrend,
        getFefoQueue: getFefoQueue,
        getAlerts: getAlerts,
        getReorderHistory: getReorderHistory,
        getReorderSummary: getReorderSummary,
        createReorder: createReorder,
        updateReorderStatus: updateReorderStatus,
        issuePurchaseOrder: issuePurchaseOrder,
        dispenseSale: dispenseSale,
        runWhatIf: runWhatIf,
        searchMedicines: searchMedicines,
        getModelComparison: getModelComparison,
        checkHealth: checkHealth
    };

})();

