# Read-Only Financial Source Adapter and Reconciliation Contract

Project: Oro Verde / huilerie-pro5  
Target: one Tunisian SUARL, régime réel  
Status: design specification only; no adapter, API, collection or GL posting code implemented  
Date: 17 Nov 2026

## 1. Objective and strict scope

Define the first executable accounting-foundation component: read-only adapters that inspect authoritative operational records and emit normalized **candidate source events** for reconciliation.

This phase must not:
- write to operational collections;
- create or update a journal, posting source, receivable/payable balance, inventory value or treasury balance;
- change invoices, payments, stock, custody, permissions or source lifecycle;
- infer missing amounts, dates, tax, cash/bank accounts, ownership, cost or fiscal periods;
- treat the current accounting dashboard as an accounting ledger.

The adapter is a read model over source documents. It is not a posting engine. It must be possible to run it repeatedly with identical inputs and obtain identical normalized candidate events and reconciliation results.

## 2. Required output envelope

Every candidate event must use a versioned, deterministic envelope. The following is a logical contract, not a MongoDB schema:

| Field | Requirement |
|---|---|
| `adapter_version` | Required semantic version of the adapter mapping |
| `source_type` | Stable enum, independent of collection or route name |
| `source_id` | Immutable source document ID; never a display code |
| `child_event_id` | Immutable child payment/event ID where the source is a child event; null only when the source truly has no child identity |
| `event_type` | Stable economic event enum |
| `event_version` | Positive integer; not a retry counter |
| `candidate_key` | Deterministic key from source type, source ID, child event ID where applicable, event type and event version |
| `source_document_number` | Optional display-only reference |
| `business_date` | Source date only when its meaning is known and supported by policy |
| `recorded_at` | Original source creation/recording timestamp, without substituting it for business date |
| `actor_id` | Source actor where present; null plus warning where absent |
| `party_ref` | Legacy party type and ID; do not merge parties |
| `currency` | Explicit ISO currency for money; TND only where source supports it |
| `amount` | Exact Decimal string; null for quantity-only events |
| `quantity` / `unit` | Exact Decimal string and explicit unit; no kg/L aggregation |
| `ownership` | Explicit owner identity/type when present; unknown is not mill-owned |
| `dimensions` | Source-supported season, location, tank, lot and cost-centre references |
| `source_fingerprint` | Hash of canonical immutable source facts used by the adapter |
| `eligibility` | One of `ELIGIBLE_FOR_REVIEW`, `BLOCKED`, `INFORMATIONAL_ONLY`, `LEGACY_UNRESOLVED` |
| `blocking_reasons[]` | Stable machine-readable reason codes; empty only when no blocker exists |
| `source_links[]` | Exact references to related invoice, payment, reversal, lot, movement, return or original event |
| `warnings[]` | Non-blocking data-quality warnings, never silently discarded |

A candidate event is not yet an accounting journal. `ELIGIBLE_FOR_REVIEW` means only that source facts are sufficiently complete for an accountant-approved mapping review; it does not authorize posting.

## 3. Source adapters and event identities

### 3.1 Traditional pressing invoices and receipts

Authoritative sources:
- invoice: `invoices`, linked to `loads`;
- load quantity: `loads.olive_kg` and pressing output `oil_kg`;
- itemized receipt: embedded `invoices.payments[]`;
- invoice update history: `invoices.history[]`, audit evidence only.

Candidate events:
- `TRADITIONAL_INVOICE / INVOICE_RECOGNIZED`: one per issued invoice, subject to invoice lifecycle and tariff-basis gate;
- `TRADITIONAL_RECEIPT / PAYMENT_RECEIVED`: one per actual itemized receipt, only after a stable payment child ID exists;
- invoice cancellation/repricing: no automatic candidate journal from a changed snapshot; require a future explicit linked adjustment/reversal source event.

Hard rules:
1. Never derive revenue from a client statement, daily-situation total or load alone.
2. Never create a receipt from cumulative `paid_amount`.
3. The same incremental payment may appear in both `payments[]` and `history[]`. The payment array is the current canonical itemized evidence; history is not another receipt.
4. If an invoice has no itemized payments, emit a `LEGACY_UNRESOLVED` reconciliation item for the unexplained paid aggregate. Do not invent payment IDs, receipt dates, method or cash account.
5. A payment object with no stable immutable ID is not ready for authoritative posting. A deterministic fingerprint can support read-only comparison but must not be misrepresented as a durable payment identity.
6. Current invoice total uses `oil_kg × tariff`, while other statistics use `olive_kg × tariff`. The adapter reports both source quantities and stored invoice total but must not recalculate/replace the invoice total until the contractual tariff basis is decided.
7. Preserve the difference between invoice business date, payment date and recorded timestamp.

### 3.2 GS supplier olive purchases and supplier settlements

Authoritative sources:
- purchase and lines: `commercial_olive_purchases`;
- lots and stock receipt: `commercial_lots` and `commercial_stock_movements`;
- supplier payment: `commercial_supplier_olive_purchase_payments`.

Candidate events:
- `GS_OLIVE_PURCHASE / PURCHASE_RECOGNIZED`: approved direct reception or approved purchase, once;
- `GS_SUPPLIER_PAYMENT / PAYMENT_MADE`: one per supplier payment document;
- explicit reversal only from a separately persisted reversal event.

Hard rules:
1. Draft purchase is informational only; it has no recognized purchase/stock event.
2. Direct `/olive-receptions` creates purchase, lot and stock receipt in one transaction and internally transitions purchase state; it is not a human approval queue.
3. Preserve the owner's no-review rule for designated purchase employees. This adapter must not add a review state or change permissions.
4. Reconcile approved purchase line quantity, reception net quantity, lot receipt and stock movement by product/owner/location. A mismatch blocks valuation eligibility.
5. Supplier payment settles payable; it is not a second purchase expense.
6. No cost-layer value is inferred merely from quantity. Use only source-supported purchase line price and approved valuation policy; production conversion and by-product allocation remain separate unresolved policies.
7. For vehicle weights, use server-authoritative gross, tare and net only after those fields exist. Until then, record legacy net-only source as such. Never synthesize gross/tare.

### 3.3 Traditional customer load purchased into mill ownership

Authoritative sources:
- traditional source load in `loads`;
- GS ownership acquisition/direct purchase document;
- custody/ownership ledger and paired stock movements.

Candidate event:
- `CUSTOMER_LOAD_ACQUISITION / OWNERSHIP_TRANSFERRED`.

Hard rules:
1. Quantity is the source load's recorded `olive_kg` (legacy net quantity); do not weigh again.
2. Source load closure, ownership ledger and stock debit/credit must reconcile.
3. Customer-owned custody before title transfer is not mill inventory.
4. A purchase agreement/payment and the ownership-transfer event are related but distinct; recognize payable/inventory only at the approved title-transfer point.
5. Repeated source IDs or an unpaired owner movement block the candidate.

### 3.4 GS wholesale sales, buyer payments, credits and returns

Authoritative sources:
- sale and invoice: `commercial_sales`, `commercial_sales_invoices`;
- dispatch: `commercial_stock_movements` with sale source;
- buyer payment: `commercial_sale_payments`;
- reversal: `commercial_payment_reversals`;
- credit: `commercial_credit_notes`, credit applications and buyer credit ledger;
- return: `commercial_sale_returns`, accepted/rejected return records and return stock movements.

Candidate events:
- `GS_SALE / SALE_RECOGNIZED`;
- `GS_BUYER_PAYMENT / PAYMENT_RECEIVED`;
- `GS_PAYMENT_REVERSAL / PAYMENT_REVERSED`;
- `GS_CREDIT_NOTE / CREDIT_RECOGNIZED`;
- `GS_SALE_RETURN / RETURN_ACCEPTED`.

Hard rules:
1. Draft sale is informational only.
2. Sale recognition, physical dispatch, payment receipt, payment reversal, credit application and accepted goods return are separate event types.
3. `NOT_CONFIGURED` tax treatment blocks statutory invoice posting.
4. A payment reversal reverses settlement only. It is not a revenue reversal.
5. Credit application is non-cash and not new revenue.
6. Rejected return produces no accepted-return revenue or inventory event.
7. Accepted quantity, credited amount and returned-stock movement must reconcile independently.
8. Existing physical FIFO allocation is not an accounting cost formula. COGS stays blocked until approved cost layers and valuation policy exist.

### 3.5 Customer custody and processing

Authoritative sources: custody receipt/release/processing events, owner-tagged lots and stock movements.

Candidate events:
- custody receipt/release: `INFORMATIONAL_ONLY` for company GL by default;
- separately approved service fee, loss/claim or title-transfer: distinct event only when a real source document exists.

Hard rules:
1. Physical possession is not title.
2. Customer-owned product never enters company-owned inventory merely because it is stored, mixed or processed.
3. Ownership and product units must reconcile through every movement.
4. Do not infer service revenue from custody quantity or processing alone.

### 3.6 Manual expenses and passive income

Authoritative sources: `accounting_expenses`, `accounting_passive_incomes`.

Current limitations:
- each record has one date, amount and payment-method field;
- no independent obligation/recognition and settlement event;
- DELETE physically removes records;
- no stable cash drawer/bank account or external settlement evidence.

Adapter treatment:
- emit source records as `LEGACY_UNRESOLVED` or `INFORMATIONAL_ONLY`;
- do not emit both an expense/income recognition event and a same-day cash event from one record;
- do not infer paid status from `payment_method`;
- do not treat generic `WAGES` category as a payroll subledger;
- require future document evidence, recognition date, due date, stable settlement event, account identity and void/reversal lifecycle before authoritative posting.

## 4. Current daily-situation endpoint is not an adapter

The existing `GET /accounting/daily-situation` endpoint is a derived operational report. Source inspection identified these semantic issues that the new adapter must not copy:

| Current projection behavior | Why it is unsafe for GL | Adapter rule |
|---|---|---|
| Reads both `invoices.payments[]` and paid deltas from `invoices.history[]` | One receipt may be counted twice | Payment child event only; history is audit evidence |
| Adds invoice `paid_amount` remainder as unallocated receipt | Aggregate does not prove receipt date or cash/bank account | Unresolved legacy aggregate; no authoritative receipt event |
| Projects supplier olive purchases as `expense` | Inventory acquisition is not automatically period expense | Purchase/stock event; COGS only on approved consumption/valuation |
| Projects customer-to-mill olive/oil acquisitions as `expense` | Ownership acquisition may create inventory and payable | Ownership/title-transfer event; valuation policy required |
| Projects passive income as both revenue and receipt on one date | One source conflates earning and collection | Unresolved until recognition and settlement are separate |
| Projects expenses as both expense and disbursement on one date | One source conflates obligation and payment | Unresolved until recognition and settlement are separate |
| Uses active olive season as source scope | Season is not statutory fiscal year | Adapter scope must be explicit; fiscal period remains separate |

The endpoint may remain useful as a clearly labeled operational indicator. Do not silently repurpose it as GL input or statutory profit.

## 5. Reconciliation report contract

Each adapter run produces a deterministic report containing:

- `run_id` (execution identity only; never part of candidate event identity);
- adapter version and source snapshot watermark;
- run start/end timestamps and explicit source scope;
- counts by source type, event type and eligibility;
- sums by currency, unit, party, owner, lot, location and source document class where valid;
- missing/duplicate/invalid source identifiers;
- missing business dates and actor identities;
- source-to-child amount/quantity mismatches;
- unpaired ownership movements;
- payment-to-invoice/purchase allocation mismatches;
- return-to-credit-to-stock mismatches;
- unsupported or mixed units;
- legacy unresolved amounts and quantities;
- duplicate candidate keys and fingerprint conflicts;
- stable blocking reason codes and affected source references.

A reconciliation report must distinguish:
- **source facts** — directly read from persisted operational records;
- **derived checks** — sums, deltas and comparisons computed by the adapter;
- **unresolved differences** — no guessed adjustment or plug value.

### Required reconciliation equations

- Traditional invoice: stored invoice total versus source tariff and both candidate quantity bases; differences are reported, not corrected.
- Traditional receipt: sum of stable itemized receipt events versus invoice paid aggregate; history overlap is not added.
- Supplier purchase: sum of approved purchase lines = recorded net reception quantity = lot receipt quantity = stock receipt movement quantity, by product/owner/location.
- Supplier payable: recognized purchase amount − allocated supplier payments − approved credits = outstanding payable, subject to supported opening balance.
- GS sale: invoice quantity/amount and accepted credits reconcile to sale; dispatched quantity reconciles to stock movements; payments and credit applications reconcile separately to receivable settlement.
- Return: accepted return quantity = accepted return stock movement; credit amount reconciles to approved credit note, not to inventory carrying value.
- Customer custody: opening custody + receipts − releases − consumption/loss ± owner transfers = closing quantity, by owner/product/lot/location.
- Stock: opening quantity + receipts − consumption − dispatch − release ± transfers/adjustments = closing quantity, by owner/product/lot/location.
- Monetary inventory valuation is a separate reconciliation and must not be fabricated from quantity equations.

## 6. Determinism, fingerprint and privacy rules

1. Canonicalize field names, enum values, Decimal strings, dates, units and null semantics before hashing.
2. Exclude volatile UI labels, display formatting, query order, run ID and report timestamps from source fingerprints.
3. Include every immutable source fact that changes economic meaning: source IDs, child IDs, source status, business date, amount, currency, quantity, unit, owner, related source IDs and approved lifecycle version.
4. Same source identity and same fingerprint yields the same candidate; same identity with a changed economic payload is a conflict to investigate, not an overwrite.
5. Adapter version changes mapping semantics but does not mutate the original source or silently increment an economic event version.
6. Store only references needed for traceability. Do not copy unnecessary customer personal data, credentials, secrets or full identity documents into candidate reports.
7. Do not use a timestamp-generated ID as a substitute for a missing source payment ID.

## 7. Access, execution and audit boundaries

- Initial implementation should expose read-only backend service functions and an admin-only preview/report endpoint, with no write scope to source collections.
- If database-level read-only credentials are available, prefer them for the adapter process. If not, enforce a narrowly scoped repository/service interface and tests proving no writes.
- Every run records actor/service identity, adapter version, scope, start/end, result counts and report fingerprint.
- Reports must be reproducible and exportable for accountant review.
- No employee-facing permission or workflow changes are part of this phase.
- No source event becomes postable merely because the adapter can parse it.

## 8. Implementation sequence and release gates

### Step 1 — Pure normalization functions
- Parse Decimal and Decimal128 without float conversion.
- Normalize explicit units and dates without guessing.
- Build deterministic source fingerprints and candidate keys.
- Unit-test null, malformed, negative, over-precision and timezone cases.

### Step 2 — Read-only source adapters
Implement one adapter at a time, beginning with traditional invoices/receipts and GS supplier purchases/payments. Add sale/credit/return and custody/stock only after their source identity and lifecycle tests exist.

### Step 3 — Reconciliation preview
Expose report-only output, compare against existing subledgers and source totals, and retain unresolved differences. Do not add a "post" button.

### Step 4 — Read-only access proof
Tests must assert no insert/update/delete/replace/bulk-write calls occur against source or accounting collections during adapter execution. Use a fake/read-only repository in unit tests and a read-only database role where operationally supported.

### Step 5 — Accountant review and pilot selection
Choose a single event family only after its source identities, dates, amounts, taxes, ownership and opening balances reconcile. Accountant sign-off and all regression tests are prerequisites to any future posting implementation.

## 9. Acceptance tests before adapter release

- Same source snapshot and adapter version produce byte-equivalent normalized candidates and report totals.
- Reordering source query results does not change fingerprints or report totals.
- Same traditional receipt in `payments[]` and `history[]` emits at most one payment candidate.
- Invoice `paid_amount` without itemized receipt remains unresolved, not a fabricated dated receipt.
- Draft purchase and draft sale never produce recognized financial events.
- Supplier line/net/lot/stock quantity mismatch blocks the affected candidate.
- Customer custody never appears in company-owned inventory candidates.
- Payment reversal does not emit a revenue reversal.
- Credit application does not emit a cash receipt or new revenue.
- Rejected return emits no accepted-return or stock-restoration event.
- Manual income/expense does not generate both accrual and settlement from one record.
- Missing tax snapshot, fiscal period, account mapping or ownership evidence yields explicit blockers.
- Unsupported unit, missing source ID, duplicate key or changed fingerprint is reported and not silently dropped.
- Adapter run causes zero database writes.
- No candidate is posted to a GL during this phase.

## 10. Explicit non-goals

This contract does not choose the pressing tariff basis, NC 04 cost formula, by-product allocation, VAT suspension scope, tax rates, fiscal-year dates, opening balances, cash/bank accounts, party merges or employee permission assignments. Those decisions remain separately gated and must not be guessed.

No GL posting endpoint, journal collection, tax engine, valuation engine or operational workflow change is implemented by this document.
