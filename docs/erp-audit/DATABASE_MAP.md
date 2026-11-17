# MongoDB Data Map (Initial Audit)

## Connection model

`backend/lib/db.py` creates one `AsyncIOMotorClient` from `MONGO_URL` and selects `client[DB_NAME]`. The main API and commercial API import the same `db` object. Therefore the source code currently implements one configured MongoDB database for Oro Verde and GS, not two independent databases.

The actual production values of `MONGO_URL` and `DB_NAME` were not read during this audit.

## Collections observed in inspected source

### Traditional mill / shared application

- `users`
- `settings`
- `counters`
- `loads`
- `lab`
- `sms_log`
- `invoices`
- `clients`
- `accounting_passive_incomes`
- `accounting_expenses`
- `tv_state`

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
- `commercial_pump_runtime`
- `commercial_audit_events)

This list is based on files inspected so far; it is not asserted to be the complete set of collections in the live database.

## Existing integrity mechanisms

- Core indexes are declared in `backend/lib/db.py` for users, loads, lab, settings and traditional invoices.
- GS declares extensive unique and lookup indexes in `backend/commercial/inventory_bootstrap.py`.
- Several GS workflows use `run_transaction`, which starts a MongoDB session and transaction.
- Purchase, sales, production and custody commands commonly include idempotency keys and unique indexes.
- GS stock changes are routed through stock-ledger services; the direct stock-movement endpoint explicitly rejects direct ledger writes.

## Important design risks / decisions

1. **Shared database, separated collections:** preserve the existing shared database initially; use clear collection ownership and service boundaries.
2. **Conflicting documentation:** `backend/commercial/__init__.py` claims a dedicated database; implementation contradicts it.
3. **Cross-domain transactions:** before posting accounting entries from GS and traditional workflows, confirm that the live MongoDB deployment supports transactions and that all writes participating in one transaction use the same session.
4. **No runtime inventory yet:** actual collection counts, indexes installed in production, orphaned references and duplicate business identifiers remain unverified.
5. **No destructive migration:** do not rename, drop, merge or bulk-rewrite collections as part of the first accounting increment.

## Next database inspection

- Read actual Render `DB_NAME` and confirm it matches the expected database (without exposing secrets).
- Inspect live collection names, counts and indexes read-only.
- Validate references among loads, invoices, GS purchases, lots, stock movements and audit events.
- Produce a migration map before introducing any accounting journal collections.
