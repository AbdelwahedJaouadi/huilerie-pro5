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

## Selected reference-integrity checks (read-only, 17 Nov 2026)

Aggregation checks on the observed records returned no dangling references for these relationships:

- Stock movement `lot_id` → `commercial_lots.id` (16 movements checked).
- Production output lot and each production input olive lot → `commercial_lots.id` (4 runs and their input/output references checked).
- Production `stock_movement_ids` → `commercial_stock_movements.id`.
- Olive purchase `lot_ids` → `commercial_lots.id`.
- Olive purchase `receipt_movement_ids` → `commercial_stock_movements.id`.
- Sales invoice `sale_id` → `commercial_sales.id`.
- Sales invoice dispatch allocation lot IDs → `commercial_lots.id`.
- Commercial lot `source_load_id` → traditional `loads.id`.
- Traditional load `ownership_transfer_lot_id` → `commercial_lots.id`.

These checks establish that the sampled/current documents do not contain dangling references along the listed paths. They do **not** prove quantity reconciliation, FIFO correctness, historical completeness, uniqueness of every business code, or correctness of every possible relationship. Inventory reconciliation remains a separate Stage 1 gate.

## Next database inspection

1. Reconcile all 49 observed collections with source-code collection references.
2. Inspect the three numeric-policy snapshot collections and `admin_reset_audit` purpose.
3. Validate references among loads, invoices, GS purchases, lots, production runs, stock movements and audit events.
4. Compare actual index options with source-declared index requirements.
5. Do not rename, drop, merge or bulk-rewrite collections during this audit.
## Weighbridge / load-weight contract (verified against current source)

### Verified scope across the three intake paths

1. **Traditional customer load** — `POST /loads` currently accepts one `olive_kg: float`. The UI has no gross/tare inputs and the request contains no idempotency key. The backend generates a new load ID/code for each call. A network retry can therefore create a second load; the existing MongoDB transaction protects the client-registry/load/audit write set, but it does not make the HTTP command idempotent.
2. **Supplier physical reception in GS** — `POST /commercial/v1/olive-receptions` accepts one or more variety lines with `quantity_kg`, plus supplier, purchase date, receiving location and request key. It currently has no vehicle gross/tare fields. The idempotency key is required, but the inner purchase fingerprint does not cover the entire outer command (notably new-supplier contact/tax metadata and receiving location); concurrent duplicate-key recovery is also incomplete.
3. **Purchase of an existing customer load into GS** — `POST /commercial/v1/customer-purchases/loads` consumes the existing load quantity. It must inherit the source load's validated net value and must never calculate a second net weight or use gross weight as stock quantity.

The weighing contract should therefore be a shared **weighing snapshot** that can be attached to the relevant physical reception/load document, not a replacement for the business documents themselves. It should record the vehicle identity when available, gross and tare readings, unit, source, separate timestamps and operator identities, and an immutable correction trail. A truck tare must not be silently reused for a different vehicle or a later trip.

For a supplier delivery with multiple variety lines, the reception-level net weight is the physical total. The sum of the accepted line quantities must reconcile exactly to that net weight before posting stock. If the delivery is physically weighed as one vehicle load but the operator does not yet know the variety split, do not post speculative line quantities; retain a controlled unposted/incomplete state or capture the verified split before atomic posting. The traditional single-variety customer load maps its net weight directly to `olive_kg`.

**Canonical compatibility rule:** `net_weight` is the canonical measured quantity for new weighing-enabled records; `olive_kg` remains the legacy API/downstream compatibility field and must equal that validated net quantity. Existing historical records with only `olive_kg` remain legacy records with unknown gross/tare—not records with inferred measurements. Use Decimal-safe calculations at input, validation and persistence boundaries; do not use client-submitted net as authoritative. The current traditional schema's float type is a migration gap that must be removed or safely isolated before enabling gross/tare capture.

**Idempotency gap to close before rollout:** add a stable request key to traditional load intake and persist a canonical fingerprint plus unique scoped key; the same key/same payload returns the original load, and same key/different payload conflicts. For GS supplier reception, fingerprint the complete normalized command (including supplier identity/contact/tax values, date, every line, location and notes) rather than only the inner purchase draft, and recover a concurrent unique-key collision by reading and returning the winning committed result. Keep request-idempotency identity distinct from the eventual GL posting identity.



The current traditional reception form (`frontend/src/components/IntakePanel.tsx`) submits a single `olive_kg` value. The `LoadCreate` schema currently validates only `olive_kg` (plus bags, variety, notes and initial status), and `backend/routers/loads.py` persists that value as the load's olive quantity. The current code therefore does **not yet** persist separate gross and tare readings.

The required target model is:

- `gross_weight`: gross vehicle/trailer weight while loaded.
- `tare_weight`: same vehicle/trailer empty weight.
- `net_weight`: gross minus tare; this is the authoritative olive quantity used by the existing production, invoice and stock workflows after validation.
- `weight_unit`: explicit unit (initially kg; support conversion at the boundary only).
- `weighing_source`: `manual` or `scale`.
- `weighbridge_id` / `scale_id`: nullable until a device is installed.
- `gross_weighed_at`, `tare_weighed_at`, `weighed_by`: timestamp and operator per reading.
- immutable reading/audit history for corrections, including old value, new value, actor, timestamp and reason.

Gross and tare must belong to the same vehicle/load and a coherent weighing event. Reject tare greater than or equal to gross unless an explicitly documented exceptional workflow applies. Calculate net server-side using decimal-safe arithmetic; do not trust a client-submitted net that disagrees with gross minus tare. Preserve the existing `olive_kg` API contract during migration or map it consistently to validated `net_weight` so downstream workflows do not silently change.

**Important distinction:** the future scale integration is not implemented today. First support and validate manual gross/tare/net capture; later connect a selected scale using its actual protocol/API, device identity, stable-reading logic and idempotent submission. Never fabricate scale readings or label manual values as scale-certified.
## Quantitative stock-ledger reconciliation (read-only, 17 Nov 2026)

A full pass over the 16 currently observed `commercial_stock_movements` and all 11 `commercial_stock_balances` was reconciled by lot, product, location and owner. For the current snapshot, every balance matched the signed movement history:

- Olive lots: 2627A0001 = 0 kg; 2627A0002 = 0 kg; 2627A0003 = 0 kg; 2627A0004 = 300 kg; 2627A0005 = 750 kg mill-owned (customer-owned balance = 0 kg).
- Oil lots: 2627A0001 = 400 kg after 900 kg production receipt and 500 kg dispatch; 2627A0002 = 800 kg; 2627A0003 = 3,000 kg; the additional output lot from production 2627PROD0004 = 2,000 kg.
- Total balances in this snapshot: 1,050 kg olives and 6,200 kg oil.

This is a point-in-time reconciliation of the available records, not proof of historical completeness or of every uninspected movement type. Ownership-transfer movements must be evaluated as paired owner debits/credits at the same location, not treated as physical receipt/consumption.

**Critical production-data exception:** all four stored completed production runs report actual oil output exactly equal to olive input (900/900, 800/800, 3,000/3,000 and 2,000/2,000 kg), i.e. a 100% extraction rate. The movement ledger and balances are internally consistent with these recorded values, but the yields are not credible for ordinary olive-oil extraction. These may be synthetic/test records; until confirmed, treat them as a data-quality exception and add server-side plausibility validation/warnings. Do not silently rewrite these existing production records.
## Production-yield validation in source

Source inspection confirms the production schema rejects oil output greater than total olive input, but it does not impose a realistic extraction-yield range or flag an unusually high yield. The current unit test demonstrates a representative calculation at 18.05%, while the four inspected stored runs are all exactly 100%. Therefore the database anomaly is permitted by the present schema, not evidence by itself of a stock-ledger arithmetic defect. Add a configurable plausibility warning (initially non-blocking) and retain the actual measured output; only introduce a hard business limit after the mill's process, varieties and measurement units are confirmed. Never auto-calculate or replace actual oil output from an assumed yield percentage.
## Traditional load, invoice and GS linkage review (source inspection)

- Traditional intake currently accepts only `olive_kg` (float) and does not capture gross/tare, vehicle identity, weighing source or individual weighing timestamps. Load creation stores this single value and emits `LOAD_CREATED` audit metadata with `olive_kg`.
- Traditional invoices are linked to a source load by `load_id`, copy the load's olive/oil quantities, and use a transactional source-load guard to prevent a concurrent load deletion race during invoice creation. A unique invoice-per-load index is documented elsewhere in this audit.
- The current traditional invoice endpoint still performs a hard `delete_one` on an invoice and emits `INVOICE_DELETED`; this preserves an audit event but removes the financial document itself. This is not acceptable as the final full-accounting behavior. Replace with a void/reversal workflow that preserves the original invoice and references its corrective document. Keep deletion only for unposted drafts if explicitly permitted by policy.
- Traditional load deletion is blocked when an invoice exists, but otherwise hard-deletes the load and its lab records, then records a deletion event. This is also a traceability risk: once a load has downstream operational, quality, custody or production references, deletion must be blocked and an audited cancellation/reversal used instead. Before deletion, verify all referencing collections, not only `invoices`.
- GS direct-load purchase workflow references the traditional load using `source_load_id` and reads `olive_kg` as its source quantity. This makes preserving the canonical net-weight field critical: after gross/tare are introduced, GS must consume the validated `net_weight` through the compatibility mapping (`olive_kg` during migration), never gross weight.
- GS olive purchase schemas already use Decimal quantities, while traditional `LoadCreate.olive_kg` is a float. The weighbridge/manual weighing upgrade should use decimal-safe parsing and server-side subtraction, and avoid silently propagating binary-float rounding into GS or accounting.

## Required acceptance tests for load weighing migration

1. Gross 12,450 kg and tare 4,250 kg yields exactly 8,200 kg net; downstream load list, GS source-load purchase, production eligibility and invoice all use 8,200 kg.
2. Reject missing gross or tare when the new weighing mode is enabled; retain a controlled legacy path for pre-existing records only.
3. Reject tare equal to or greater than gross, negative values, invalid precision and unsupported units.
4. Manual capture is explicitly labeled `manual`; future scale capture requires device identity and scale-origin metadata.
5. Correcting a recorded gross/tare reading creates an immutable correction event with actor, time, reason and before/after values.
6. Retrying the same intake request cannot create a duplicate load or duplicate audit/stock effects.
7. Existing records containing only `olive_kg` remain readable and are not retroactively assigned invented gross/tare values.


## Client registry and safe deletion update (17 Nov 2026)

The traditional `clients` collection now acts as the canonical client activation registry:

- `phone` is the unique client key for string-valued phone numbers.
- `active` defaults to true for existing records without the field; deactivation writes `active=false`.
- `deactivated_at`, `deactivated_by`, `reactivated_at`, `reactivated_by` retain lifecycle metadata.
- `intake_guard_version` is incremented during new-load creation so the activation check participates in the same transaction as the new load.
- Application startup index configuration now includes a unique partial index on `clients.phone` for string-valued phone numbers. A read-only duplicate scan of existing string phone values returned zero duplicates before this change.

A client with any traditional load history or a verified GS buyer/custody identity is deactivated, not deleted. The source loads, analyses, invoices, SMS records and GS references remain intact. Inactive clients are excluded from the new-load client selector, and the API rejects new traditional loads until reactivation.

### Load deletion references now guarded

The shared traditional-load deletion eligibility check verifies:
- `invoices.load_id`
- `commercial_direct_load_purchases.source_load_id`
- `commercial_customer_custody_receipts.source_load_id`
- `commercial_lots.source_load_id`
- `lab.load_id`
- `sms_log.load_id`
- ownership/custody transfer and load processing state in the source `loads` document.

The GS source-reference fields were verified from the current Atlas collection schemas. This is an explicit reference list; it should be expanded whenever a new collection begins storing a traditional load ID.
