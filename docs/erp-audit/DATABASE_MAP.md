# MongoDB Data Map (Initial Audit)

## Connection model from source

`backend/lib/db.py` creates one `AsyncIOMotorClient` from `MONGO_URL` and selects `client[DB_NAME]`. The main API and commercial API import the same `db` object. Therefore the source code implements one configured MongoDB database for Oro Verde and GS, not two independent databases.

The commercial router imports `client`, `db` and `run_transaction` from the same `lib.db` module. The docstring in `backend/commercial/__init__.py` claiming a dedicated database is inconsistent with this implementation.

The user explicitly confirmed that the pro5 application intentionally uses the existing database named `huilerie-pro3`. Treat this as the intended application/database pairing. The names identify different things: pro5 is the active codebase; huilerie-pro3 is the chosen MongoDB database name.

## Read-only Atlas snapshot

Atlas project: `Project 0`  
Cluster: `Dadu` (Free tier, AWS US_EAST_1, MongoDB 8.0.37)  
Database inspected: `huilerie-pro3`

The connected cluster listed five databases: `huilerie-pro3`, `oroverde_cms`, `sample_mflix`, `admin`, and `local`. It did **not** list a database named `huilerie-pro5`.

The `huilerie-pro3` database reported:

- 49 collections
- 290 documents
- 185 indexes
- approximately 8.47 MB data size and 17.78 MB storage size

Render's service-details response did not expose the actual `MONGO_URL` and `DB_NAME` values. The user's confirmation establishes the intended configuration; the Atlas snapshot is a read-only observation of the named database, not an independent read-back of Render's secret environment variables.

## Selected document counts observed in Atlas

| Collection | Count |
|---|---:|
| `loads` | 5 |
| `invoices` | 3 |
| `clients` | 2 |
| `users` | 3 |
| `lab` | 3 |
| `commercial_olive_purchases` | 3 |
| `commercial_production_runs` | 4 |
| `commercial_lots` | 14 |
| `commercial_stock_balances` | 11 |
| `commercial_stock_movements` | 16 |
| `commercial_sales` | 1 |
| `commercial_sales_invoices` | 1 |
| `commercial_sale_payments` | 1 |
| `commercial_suppliers` | 2 |
| `commercial_buyers` | 1 |
| `commercial_tanks` | 9 |
| `commercial_locations` | 4 |
| `commercial_preproduction_samples` | 5 |
| `commercial_audit_events` | 75 |

## Collections observed

### Traditional mill / shared application

- `users`
- `settings`
- `counters`
- `loads`
- `lab`
- `sms_log`
- `invoices`
- `clients`
- `tv_state`
- `tv_music_files.files`
- `tv_music_files.chunks`

### Commercial / GS

- `commercial_counters`
- `commercial_suppliers`
- `commercial_varieties`
- `commercial_custody_owners`
- `commercial_customer_custody_receipts`
- `commercial_customer_custody_releases`
- `commercial_olive_purchases`
- `commercial_production_runs`
- `commercial_buyers`
- `commercial_sales`
- `commercial_sale_returns`
- `commercial_sale_return_rejections`
- `commercial_sales_invoices`
- `commercial_credit_notes`
- `commercial_buyer_return_rejections`
- `commercial_payment_reversals`
- `commercial_buyer_credit_applications`
- `commercial_buyer_credit_ledger`
- `commercial_sale_payments`
- `commercial_locations`
- `commercial_tanks`
- `commercial_lots`
- `commercial_stock_balances`
- `commercial_stock_movements`
- `commercial_internal_movements`
- `commercial_oil_purchase_documents`
- `commercial_oil_purchase_payments`
- `commercial_supplier_olive_purchase_payments`
- `commercial_preproduction_samples`
- `commercial_quality_assessments`
- `commercial_quality_releases`
- `commercial_pump_runtime`
- `commercial_audit_events`
- `commercial_direct_load_purchases`

### Unclassified / migration-related collections

- `admin_reset_audit`
- `backup_numeric_policy_20261110_settings`
- `backup_numeric_policy_20261110_loads`
- `backup_numeric_policy_20261110_invoices`

The three `backup_numeric_policy_20261110_*` collections contain 1, 14 and 9 documents respectively. Their exact creation purpose and retention policy have not yet been verified. Do not delete or repurpose them during this audit.

The accounting backend references `accounting_expenses` and `accounting_passive_incomes`, but neither appeared in the collection listing at the time of inspection. MongoDB creates these collections on first insert; verify their use before assuming historical records exist.

## Existing indexes and integrity mechanisms

Live index inspection confirmed indexes on core collections including `loads`, `invoices`, `commercial_olive_purchases`, `commercial_lots`, `commercial_stock_movements`, `commercial_sales_invoices`, `commercial_audit_events`, `commercial_counters`, `users` and `settings`.

Source code declares core indexes in `backend/lib/db.py` and extensive commercial indexes in `backend/commercial/inventory_bootstrap.py`. The Atlas index-inspection response exposed index names and key patterns, but not every index option; uniqueness settings were therefore not independently re-verified from Atlas in this pass.

Several GS workflows use `run_transaction`; purchase, sales, production and custody commands commonly use idempotency keys. GS stock changes are routed through stock-ledger services.

## Next database inspection

1. Reconcile all 49 observed collections with source-code collection references.
2. Inspect the three numeric-policy snapshot collections and `admin_reset_audit` purpose.
3. Validate references among loads, invoices, GS purchases, lots, production runs, stock movements and audit events.
4. Compare actual index options with source-declared index requirements.
5. Do not rename, drop, merge or bulk-rewrite collections during this audit.
