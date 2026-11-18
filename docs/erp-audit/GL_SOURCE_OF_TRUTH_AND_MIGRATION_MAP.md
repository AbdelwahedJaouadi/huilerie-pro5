# General-Ledger Source-of-Truth and Migration Map

Project: Oro Verde / huilerie-pro5  
Target: one Tunisian SUARL, régime réel  
Status: architecture and migration design only; not implemented and not accountant-approved  
Date: 18 Nov 2026

## 1. Purpose and governing rules

This document defines which operational record is authoritative for each economic event, when that event may enter a future double-entry general ledger (GL), and how legacy records can be migrated without changing their historical meaning.

The GL must consume immutable business events. It must not calculate postings from dashboard totals, statements, balance snapshots, UI summaries, audit descriptions, or duplicated parent/child representations.

The existing operational application remains the source of truth for its existing documents until a controlled migration is approved. The future GL is the source of truth for posted accounting balances and statutory reports; it does not replace the operational source documents or physical stock ledger.

No GL collections, posting endpoints, account codes, journal templates, tax rates, opening balances or historical postings are created by this design.

## 2. Authority hierarchy

For every domain, apply this precedence:

1. **Original operational document/event** — immutable source facts and lifecycle.
2. **Domain subledger** — receivable, payable, custody, physical stock, valuation, or treasury detail derived from those source events.
3. **GL posting source + journal entry** — accounting representation of one eligible economic event.
4. **Read models/reports** — derived views only; never posting sources.

A later snapshot must not silently overwrite an earlier event. A correction is a new linked event, not a rewrite. If two representations describe the same economic event, designate exactly one canonical event identity and make all other representations references or legacy fallbacks.

## 3. Source-to-ledger matrix

| Domain / event | Authoritative operational source | Subledger authority | Future GL eligibility | Required gate / treatment |
|---|---|---|---|---|
| Traditional pressing service invoice | Issued traditional invoice linked to its load | Customer receivable derived from invoice and canonical receipts | Invoice recognition event, once | Confirm contractual tariff basis and revenue date; tax snapshot must be approved. Current invoice amount uses oil kg × tariff while statistics use olive kg × tariff; do not choose either by assumption. |
| Traditional initial/additional receipt | Immutable payment child event linked to invoice; current legacy source is embedded `invoices.payments[]` | Customer settlement ledger | One receipt event per payment ID | Introduce stable payment IDs. Do not post cumulative `paid_amount`; do not count matching `history[]` delta again. Legacy aggregate-only values remain estimated/unallocated until reconciled. |
| GS wholesale sale invoice | Approved/issued GS sales invoice | Buyer receivable and sales document lifecycle | Sale recognition event, once | Require approved ownership/title, dispatch/revenue-recognition rule, tax snapshot and cost-of-goods valuation. `NOT_CONFIGURED` tax state blocks statutory posting. |
| GS buyer payment / reversal | GS PAY and linked REV records | Buyer receivable settlement ledger | Payment and reversal are separate events | PAY settles receivable; REV reverses settlement only. A REV is not automatically a sales return or revenue reversal. Require named cash/bank account before treasury posting. |
| GS credit note / return | Approved credit/return document linked to original sale and, where applicable, returned stock movement | Buyer credit/receivable and stock-return subledgers | Credit/return event when approved and accepted | Must reference original sale; rejected return has no posting. Separate commercial credit from cash refund and physical goods receipt. |
| GS supplier olive purchase | Approved purchase/reception record and its immutable purchase lines | Supplier payable plus company-owned olive stock/lot subledger | Purchase recognition event when ownership and recognition criteria are met | Preserve user's direct-entry rule: designated authorized employee records purchase and gross/tare/net without sending it to a human approval queue. The server validates and calculates net, then atomically records purchase, lot, stock receipt and audit evidence. This is not a general removal of controls. |
| Supplier payment / reversal | Supplier payment and reversal event records | Supplier payable settlement | Payment and reversal separately | Require payment identity, actual treasury account, evidence and role control. Do not duplicate the purchase expense/inventory posting. |
| Customer-to-mill purchase of an existing load | GS customer-purchase transaction linked to the traditional load | Ownership/custody subledger and mill-owned stock movement | Ownership acquisition event only when title transfers | Source quantity is the existing load's canonical net; never weigh again. A customer-owned custody receipt alone is not a company purchase. |
| Customer-owned custody receipt/release | Custody receipt/release event | Owner-specific custody subledger | Normally no company inventory or purchase posting | Physical presence is not ownership. Recognize only separately approved service revenue, liability, loss or title-transfer events. |
| Physical stock movement | Append-only GS stock movement | Physical quantity by product, lot, location and owner | No automatic GL entry from quantity movement alone | Quantity ledger is authoritative for physical stock. Value entries come from valuation events linked to the movement; never post both movement and its source purchase/production as duplicate value. |
| Production run | Approved/posted GS production run and its input/output stock movements | Production/lot quantity subledger plus future valuation subledger | Cost transfer / conversion event when valuation policy is approved | Inputs must reconcile to consumed lots; outputs/by-products/process loss require NC 04 policy. Production quantities alone do not create invented costs or revenue. |
| Oil dispatch / sale fulfillment | Approved dispatch allocation linked to sale | Physical oil stock and lot allocation | Inventory relief / COGS event | Existing FIFO allocation is physical dispatch logic, not proof of statutory FIFO cost formula. Cost formula and cost layers must be approved. |
| Inventory adjustment / loss | Authorized stock-adjustment event with count, reason and actor | Physical stock; valuation adjustment subledger | Adjustment event only after authorization | Require evidence and separate approval; never edit balances directly. |
| Manual expense | Existing expense record is currently a simple operational record | Future expense obligation and settlement subledgers | Recognition event and settlement event separately | Current schema conflates recognition and payment date and permits hard delete. Replace with document/obligation lifecycle, due date, evidence, partial settlements and reversal. |
| Manual/passive income | Existing income record is currently a simple operational record | Future income receivable and settlement subledgers | Recognition and receipt separately | Current schema conflates earning and collection. Require evidence, recognition date, collection event and reversal lifecycle. |
| Payroll | No dedicated payroll source module identified | Future employee payroll subledger | Payroll accrual and payment events | Do not treat generic WAGES expenses as a payroll register. Requires Tunisian payroll specialist and accountant approval. |
| Fixed assets | No dedicated asset register/API identified | Future fixed-asset register | Acquisition, depreciation, impairment and disposal events | Capitalization threshold, useful life, method and tax treatment require accountant approval. |
| Cash / bank | Current payment records lack named drawer/account and bank reconciliation | Future cashbook, bank ledger and statement reconciliation | Treasury movement for each actual payment/reversal/transfer | Payment method alone does not identify an account. Legacy events remain `UNALLOCATED_LEGACY`; never infer the account. Internal transfers are paired balance-sheet movements, not income/expense. |
| Tax / withholding / stamp duty | No complete tax snapshot in traditional invoices; GS tax is `NOT_CONFIGURED` | Future tax subledger and immutable invoice tax snapshot | Only under effective-dated, approved tax rules | Reported VAT suspension is unverified. No blanket suspension, exemption, non-liability or rate may be inferred. |
| Party identity | Existing clients, suppliers, buyers and custody owners remain separate domain records | Separate customer, supplier, buyer and custody subledgers | Party dimension on postings | Introduce canonical party ID only through verified/manual identity resolution. Preserve legacy IDs; never auto-merge by name/phone or automatically offset receivable against payable. |
| Fiscal period | No configured legal fiscal-year calendar | Future fiscal-period ledger | Posting only into an explicitly open period | Fiscal year start/end remain unset. Olive season is not a fiscal year. No default calendar year. |

## 4. Critical event distinctions

### 4.1 Invoice is not payment

An invoice recognition event creates the relevant receivable/revenue representation once. Each receipt is a separate settlement event. A partial payment changes the receivable balance but must not create revenue again.

For traditional invoices, current code may represent one incremental receipt both in `payments[]` and in generic `history[]`. The canonical receipt must be the itemized payment event once stable IDs exist. The history delta is audit/history evidence, not a second payment. Only when itemized payments are absent may a controlled legacy fallback be considered, clearly marked as estimated and excluded from authoritative cash/bank reporting until reconciled.

### 4.2 Purchase is not automatically an expense

Company-owned olives/oil acquired for resale or processing are inventory acquisitions when recognition criteria are met. Their cost is recognized through consumption, COGS, approved write-off or another accountant-approved treatment—not automatically as a period expense on purchase date.

The current daily-situation report classifies some olive acquisitions as expenses. That operational report must not be represented as statutory profit.

### 4.3 Physical custody is not ownership

Customer-owned olives/oil physically held at the mill must remain owner-tagged custody stock. It is not mill-owned inventory solely because it is received, stored, mixed or processed. A documented title transfer is a distinct economic event and must be reflected in owner-level movements and relevant subledgers.

### 4.4 Physical FIFO is not accounting cost FIFO

The current GS sale flow allocates physical dispatch from stock using FIFO. It does not establish the statutory inventory valuation formula. Cost layers must remain independently identifiable through tank mixing and dispatch. The Tunisian accountant must approve FIFO, weighted average or another permitted method under NC 04 before valuation postings.

### 4.5 Payment reversal is not sales return

A payment reversal reverses the settlement event and restores the related receivable/payable position. A sales return or credit note changes the commercial claim and may affect revenue and inventory. These are separate source events and must never be inferred from one another.

## 5. Canonical event and posting lifecycle

Use the existing proposed identity contract:

`source_type + source_id + event_type + event_version`

The request idempotency key protects an operational command; the GL posting-source key protects an economic event. They are not interchangeable.

Recommended posting lifecycle:

1. **Source created/recorded** — source document is persisted with actor, business date, recorded timestamp and immutable ID.
2. **Source eligible** — domain-specific business conditions are met (e.g. invoice issued, purchase ownership recognized, payment accepted, credit approved).
3. **Posting claimed** — insert unique posting-source identity with canonical payload fingerprint.
4. **Journal validated** — account, currency, amount, dimensions, open period, permissions and exact debit/credit equality validated.
5. **Posted** — immutable journal entry and lines linked to the source event; posting-source marked posted.
6. **Reversed/adjusted** — new linked source event and journal entry; original remains unchanged.

The posting-source claim, journal header/lines and source-state transition must commit atomically where supported. On duplicate-key race, re-read the winning source event: same fingerprint returns idempotent success; different fingerprint raises a reconciliation conflict. Never overwrite a posted fingerprint or create a second journal entry.

## 6. Data and migration strategy

### Phase A — Freeze definitions, not operations

- Keep existing operational workflows running.
- Do not alter live invoice, payment, stock, custody or supplier records to make them fit the future ledger.
- Define canonical IDs and event adapters in parallel with the current source model.
- Use Decimal/Decimal128 or integer minor units for money; use Decimal quantities with explicit units. Never post from float or formatted display strings.
- Store business date, recorded timestamp and posted timestamp separately.

### Phase B — Build source adapters and reconciliation read models

For each source domain, implement a read-only adapter that emits normalized candidate events with:
- stable source type, source ID, event type and version;
- source document number as display-only metadata;
- event business date and immutable recorded timestamp;
- TND currency or explicit non-money unit;
- exact Decimal amount/quantity and unit;
- party, ownership, location, lot, cost-centre and season dimensions where applicable;
- canonical payload fingerprint;
- eligibility status and explicit blocking reason;
- link to original/reversal/credit event where applicable.

Adapters must be read-only initially. Reconcile candidate event counts and totals to existing source documents and subledgers before enabling posting.

### Phase C — Establish opening positions

Opening balances must be supported by signed reconciliation schedules, not copied from dashboard totals:
- customer receivables by invoice and canonical receipt;
- supplier payables by purchase and payment;
- buyer receivables and credits;
- custody quantities by owner, product, lot and location (not company inventory value);
- company-owned inventory quantities and independently supported cost layers;
- cash drawers and bank accounts using physical counts and bank statements;
- fixed assets and accumulated depreciation, if in scope;
- equity, shareholder current account, loans and retained earnings;
- tax/social balances supported by official statements.

Unreliable legacy amounts remain explicitly unresolved/unvalued. Never manufacture missing payment dates, cash accounts, tax treatment, inventory cost or gross/tare weights. Keep legacy source IDs and snapshots.

### Phase D — Controlled parallel reconciliation

Before posting is enabled, run candidate journals in a non-posting preview and reconcile:
- source document totals to candidate events;
- receivable/payable subledgers to source balances;
- physical stock to stock movement history;
- valuation subledger to supported cost records;
- cash/bank events to external evidence;
- trial balance debits and credits;
- party balances by legal relationship;
- fiscal-period cut-off and backdated-event exceptions.

No silent opening-balance plug account. Any difference must be classified, evidenced, approved and tracked to resolution.

### Phase E — Limited posting pilot

Enable posting only for a narrow, approved event family after all its tests and accountant sign-off pass. Use a feature flag and a single canonical posting path. Reconcile daily. Expand by event family only after the prior family is stable. Do not run a shadow posting path in parallel that can post the same source event twice.

### Phase F — Statutory close and reports

Only after opening balances, account mappings, tax rules and fiscal periods are approved:
- trial balance;
- general ledger by account;
- customer/supplier subledger reconciliation;
- balance sheet;
- income statement;
- cash-flow statement;
- inventory valuation and COGS;
- tax reports;
- period close/reopen and retained-earnings carry-forward.

## 7. Non-destructive legacy migration rules

- Preserve every existing source ID, business code, original date, actor and source document snapshot.
- Do not rewrite old invoices, payment amounts, stock movements, lot ownership, custody records or production quantities.
- Do not retrofit gross/tare to old loads that only have `olive_kg`; classify them as legacy net-only with unknown gross/tare.
- Do not infer a cash or bank account from payment method.
- Do not infer tax suspension from company legal form, régime réel or an owner statement.
- Do not assign cost to legacy lots without reliable acquisition/production cost evidence.
- Do not auto-merge parties or net balances across roles.
- Do not convert customer-owned custody into company inventory.
- Every migration mapping must be repeatable, versioned, dry-runnable, idempotent and produce a reconciliation report before writes.

## 8. Decision register — blocking only dependent work

| Decision | Current state | Work blocked |
|---|---|---|
| Traditional pressing tariff basis (olive kg, oil kg or other contractual basis) | Unresolved; invoice and statistics formulas differ | Financial formula changes and traditional invoice GL template |
| Inventory cost formula and NC 04 allocation (including by-products, conversion overhead, abnormal loss and impairment) | Requires Tunisian accountant approval | Monetary valuation, production cost and COGS posting |
| VAT suspension authorization and transaction scope | Reported by owner, official document not verified | Tax calculation, tax posting and statutory invoice tax wording |
| Fiscal-year start/end and opening date | Deliberately deferred | Fiscal-period creation, opening balances and statutory annual close |
| Which employees receive direct olive-purchase registration capability | Designated employee capability required; individuals/roles not yet specified | Runtime permission grant only; architecture and non-runtime design continue |
| Cash drawers, bank accounts and verified opening balances | Not yet configured/reconciled | Treasury posting and bank reconciliation |
| Canonical party identity matches | Not verified | Consolidated cross-role party reporting; separate existing subledgers continue |
| Accountant-approved NC 01 account subdivisions and journal templates | Design baseline only | Statutory GL posting |

These decisions do not block documentation, source adapters, read-only reconciliation tools, test design or other non-destructive foundation work.

## 9. Direct olive-purchase rule — explicit owner decision

The owner has explicitly rejected a human purchase-approval queue for olive purchase/reception. The authorized employee records the purchase and the vehicle gross/tare weights; the server derives net weight and commits the purchase, traceability lot, stock receipt and audit evidence atomically. No pending approval state is inserted between employee entry and stock registration.

This is a narrowly scoped operational exception. It does not authorize workers generally to approve supplier payments, customer receipts, payment reversals, sales, stock adjustments, or GL journals. The exact employee capability assignment remains a separate permission decision.

For all new vehicle receptions:
- gross and tare are independently recorded with unit, weighing source, actor and timestamps;
- net is computed server-side as gross minus tare using Decimal;
- client-supplied net is never trusted;
- tare must be less than gross and quantities must satisfy precision/range validation;
- future scale integration adds a scale/device identity and captured reading provenance, but must not be claimed until implemented;
- legacy `loads.olive_kg` remains a compatibility alias for net during migration;
- supplier variety lines must sum exactly to reception net before stock posting;
- direct purchase of an existing customer load inherits its recorded net and never performs a second weighing.

## 10. Acceptance criteria before first GL posting

- [ ] Accountant-approved NC 01 chart, account rules and financial statement mapping.
- [ ] Explicit fiscal year, periods and verified opening balances.
- [ ] Canonical source-event IDs and unique posting-source index.
- [ ] Immutable event fingerprints and duplicate-key race recovery.
- [ ] Decimal-safe money and quantity normalization.
- [ ] Traditional receipt overlap is deduplicated and legacy fallback is explicit.
- [ ] Invoice, payment, reversal, credit and return are distinct tested events.
- [ ] Company-owned inventory and customer custody never cross-post.
- [ ] Cost layers and production allocation are approved and reconciled.
- [ ] Cash/bank account identity and external evidence are captured.
- [ ] Tax treatment and suspension scope are verified and versioned.
- [ ] Party subledgers reconcile without automatic netting.
- [ ] Full source-event integration tests, backend suite, frontend build/typecheck and production smoke tests run with recorded CI evidence.
- [ ] Pilot reconciliation has no unexplained differences and is signed off by the Tunisian accountant.

No GL posting endpoint or accounting collection is implemented by this document.
