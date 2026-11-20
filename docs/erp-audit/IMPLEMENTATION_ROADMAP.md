# Oro Verde ERP Implementation Roadmap

Target decisions:
- One mill (single site), with no multi-site complexity in the first release.
- Full double-entry accounting.
- All staff use the system through role-specific access.
- Start with foundation audit; do not rebuild working modules.
- Future weighbridge integration is a defined operational requirement: capture gross, tare and net weights for vehicle loads, with a manual-first path and later electronic scale integration.

## Stage 0 — Source and runtime audit (current)

- [x] Confirm repository `abdelwehed-hue/huilerie-pro5`, default branch `main`.
- [x] Confirm the pro5 frontend and backend Render services exist and their latest inspected deploys are live on the same main commit.
- [x] Inspect FastAPI entry point, shared MongoDB handle, core routers and frontend routes.
- [x] Confirm that GS and the traditional app import the same configured MongoDB handle.
- [x] User confirmed that pro5 intentionally uses database `huilerie-pro3`.
- [x] Identify existing accounting dashboard/reporting and its limitations.
- [x] Connect read-only to the available Atlas project and inspect listed databases, collections, selected document counts and indexes.
- [x] Inspect core authentication policy and representative traditional load, invoice and accounting mutation paths.
- [ ] Complete all route, collection, index and permission inventories.
- [ ] Inspect unclassified migration/snapshot collections and validate data references.
- [ ] Run existing automated tests and frontend typecheck/build in a controlled environment.

**Findings requiring Stage 1 treatment:**
- Accounting overview is a source-document reporting layer, not double-entry general-ledger accounting.
- Passive income and expense records can be physically deleted; traditional invoices also have a physical delete endpoint. Replace financial deletion with reversal/void workflows and preserve immutable history.
- Commercial permissions are granular, but the assignable permission set is narrower than the full commercial permission set; purchases, production, sales and some operational capabilities remain admin-only in the current policy.
- Traditional load operations are authenticated but not all use explicit role-specific permissions. Build a least-privilege endpoint matrix before expanding staff access.
- The app correctly rejects disabled authentication in production through runtime validation. Preserve this fail-closed guard.
- The backend's traditional and commercial modules share the same MongoDB handle. Do not split the database as part of the foundation work.
- Traditional load records must support gross weight, tare and net weight distinctly. Current source inspection shows the reception form persists only one `olive_kg` value; separate gross/tare capture is not yet implemented. Add manual gross and tare entry first, derive net server-side, preserve downstream compatibility through the existing `olive_kg` field during migration, and later connect the electronic weighbridge. Do not treat scale integration as live until separately implemented and tested.

**Exit gate:** verified source/runtime map, permission matrix, relationship/integrity report and a regression-tested list of existing behavior that must not regress.

### Weighing and intake integrity gate (must precede scale integration)

- [ ] Extend traditional customer-load intake to capture gross and tare separately; derive net server-side using Decimal-safe arithmetic.
- [ ] Apply the same reception-level weighing snapshot to supplier vehicle deliveries; require supplier line quantities to reconcile to the measured net before posting stock.
- [ ] Keep `olive_kg` equal to validated net for existing downstream traditional and GS integrations; never map gross into it.
- [ ] Add request idempotency to traditional `POST /loads`; add complete-command fingerprinting and concurrent retry recovery to GS `POST /olive-receptions`.
- [ ] Add immutable correction events and explicit manual/scale provenance. Do not populate historical gross/tare values.
- [ ] Prove that the same net quantity flows through intake, GS stock, production and invoices before enabling the electronic scale interface.

## Stage 1 — Stabilize the existing operational platform

- Define ownership and contracts for traditional loads, invoices, lab and GS documents.
- Resolve contradictory database documentation.
- Review destructive delete paths and replace deletion of financially meaningful records with cancellation/reversal where required.
- Verify traceability, idempotency, transaction boundaries and stock-ledger reconciliation.
- Standardize business identifiers and source-document references.
- Establish role matrix and permission checks for every sensitive endpoint.
- Design the load-weight data contract: gross, tare, net, unit, vehicle/load association, weighing time, operator, reading source and correction audit. Preserve raw readings and calculate net from the matched gross/tare pair.

**Exit gate:** core reception-to-production-to-stock-to-sale workflows pass regression tests; load weights are internally consistent and auditable.

## Stage 2 — Accounting foundation (design before UI)

- [x] Confirm jurisdiction: Tunisia; legal form: SUARL; owner-declared tax regime: régime réel.
- [x] Record owner-reported VAT suspension as unverified because the official authorization is not currently available; do not automate VAT suspension until scope, validity and supporting evidence are reviewed.
- [ ] Confirm fiscal-year start, accountant-approved NC 01 chart of accounts, activity-specific tax rules and invoice requirements.
- Design chart of accounts and account classes.
- Define journal types (sales, purchases, cash, bank, payroll, inventory, general).
- Define posting templates for each source event.
- Design fiscal periods, opening balances and migration of historical balances.
- Define posting idempotency, reversals, period close and reconciliation rules.

**Exit gate:** approved accounting design and sample postings for representative workflows.

## Stage 3 — General ledger MVP

- Implement chart of accounts.
- Implement journal entry headers and debit/credit lines.
- Implement posting service with balanced-entry validation and idempotency.
- Implement general journal and general ledger views.
- Implement trial balance.
- Implement period controls and audit history.
- Add accountant/admin permissions and read-only management views.

**Exit gate:** test cases prove every posted entry balances and duplicate posting is impossible.

## Stage 4 — Operational subledgers and automated posting

- Connect traditional service invoices and receipts.
- Connect GS olive purchases and supplier payments.
- Connect wholesale sales, receipts, returns, credit notes and reversals.
- Connect customer olive/oil purchases and custody settlements as applicable.
- Connect cash and bank accounts.
- Reconcile client/supplier subledgers to control accounts.

**Exit gate:** source-document totals reconcile exactly to accounting control accounts.

## Stage 5 — Financial statements and compliance

- Balance sheet.
- Income statement.
- Cash-flow statement.
- Tax codes, tax ledgers and periodic tax reports.
- Fixed assets and depreciation.
- Bank reconciliation.
- Fiscal close and opening balances for the next year.
- Export/print formats approved by the accountant.

**Exit gate:** accountant validates statements and tax outputs against independently prepared sample periods.

## Stage 6 — Industrial cost accounting

- Cost centres and cost categories.
- Direct material, labour and overhead capture.
- Production run cost allocation.
- Inventory valuation policy.
- Cost per litre / batch and margin analysis.
- Machine downtime and maintenance cost linkage.
- Link raw-material quantities and weighbridge evidence to production and cost calculations.

**Exit gate:** sample batch costs reconcile to source expenses and inventory valuation.

## Stage 7 — Workforce, maintenance and management dashboards

- Staff records, shifts, attendance and task assignments.
- Equipment register, preventive maintenance and downtime.
- Role-specific operational dashboards.
- Executive dashboard with drill-down to source records.
- Alerts for operational, stock and financial exceptions.
- Weighbridge equipment register, calibration/verification history and scale maintenance workflow before certified automatic weighing is enabled.

## Stage 8 — Optimization

- Season comparisons and forecasting.
- Anomaly detection after data quality is proven.
- Integrate the physical weighbridge (stable reading capture, device protocol/API, scale ID, idempotent submission, manual override audit) after selecting the actual scale model and interface.
- Offline mill workflow and synchronization only after the online source-of-truth model is defined and tested.
- Multi-site support only if the business later requires it.

## Delivery rules

- Work only in `huilerie-pro5`.
- Keep ERP audit documentation versioned with the active pro5 codebase; the original audit branch was merged through PR #3 on 18 Nov 2026.
- No production data changes during source audit.
- No database split during the initial phases.
- No large-bang rewrite.
- Every implementation unit includes backend tests, frontend typecheck/build and a regression test for affected existing workflows.
- Deploy only after the user approves the implementation scope and the release passes its test gate.


## Stage 0 security and destructive-operation audit update (17 Nov 2026)

The following source reviews are now documented alongside the original project/database/business-flow audit:

- `SECURITY_AND_DELETION_REVIEW.md`: production authentication startup guard, traditional invoice/accounting/load/client/lab/user deletion risks, verified GS cancellation semantics, and test gaps.
- `COMMERCIAL_PERMISSION_MATRIX.md`: static inventory of all 89 commercial API handlers, including dependency and commercial-permission guards.

Key confirmed findings:
- `backend/server.py` runs `validate_runtime_security()` before startup; Render is classified as production, and production startup rejects `AUTH_DISABLED=true`. Preserve this guard and its test.
- All 89 commercial routes inspected have either `current_user` or `require_admin`; the inspected loads, invoices and accounting routers also had no unguarded routes. This does not prove that the effective worker permissions match the mill's desired job roles.
- The traditional single-load delete checks invoices and ownership transfer, but not all downstream references.
- The client-wide delete path checks invoices only and bulk-deletes all of the client's loads, bypassing the single-load ownership-transfer guard. It can therefore remove a traditional source load that GS documents may still reference.
- Traditional invoice, passive-income and expense endpoints hard-delete business documents. Lab analysis and user records also have hard-delete endpoints.
- Existing load/client deletion unit tests currently validate the narrower invoice-only rule; they must be strengthened rather than preserved as the desired ERP behavior.
- GS supplier deactivation, draft olive-purchase update/cancellation, preproduction cancellation and reviewed-quality immutability already demonstrate safer domain patterns.

**Updated Stage 0 exit gate:** complete the full load-reference inventory (including all direct-purchase, custody, lot and production links); define the client-deletion behavior for mixed histories; and replace the invoice-only deletion rule with shared, tested deletion eligibility used by both single-load and client-wide operations. No production environment or data was changed during this audit.


## Client history preservation fix implemented on audit branch

The approved client-deletion rule has been implemented in source (not yet merged/deployed):

- Historical clients are deactivated rather than deleted; all associated loads, lab, SMS, invoices and GS references remain.
- Clients without operational history can still be hard-deleted.
- GS buyer and custody identities are checked using schema-verified phone fields.
- Inactive clients are hidden from new-operation selectors; new load creation is rejected until reactivation.
- Reactivation and deactivation each write an audit event transactionally.
- Traditional load deletion now uses one shared eligibility guard and blocks invoice, transfer/custody, processing, GS lot/purchase/receipt, lab and SMS references.
- A unique partial `clients.phone` index and intake guard version protect client identity and the activation check.

**Validation gate still open:** run backend pytest (including the updated client-delete, client-options, load-delete and atomic-deletion tests), run frontend TypeScript/build checks, inspect CI results, then review the complete branch diff before merging or deploying. No live database documents were modified by this implementation.


**CI status:** the validation workflow now includes `audit/erp-foundation`, but two push runs ended before any job step started; no logs were produced. This is an infrastructure/runner validation blocker, not evidence that the code passed or failed. Keep the branch unmerged until the runner issue is resolved and backend tests plus frontend build actually execute.


## Traditional API permission inventory added

`TRADITIONAL_PERMISSION_MATRIX.md` now maps the 85 mounted traditional API routes: 7 intentionally public, 29 available to any authenticated user, and 49 administrator-only. This makes the current role boundary explicit and identifies broad worker write access to loads, production updates, lab creation, client creation and TV management. A role-specific capability matrix remains a Stage 1 decision; do not expand permissions ad hoc.


## Financial lifecycle review update (17 Nov 2026)

- Added `FINANCIAL_DOCUMENT_LIFECYCLE.md` documenting traditional invoice receipt handling, a confirmed mismatch between invoice payment totals and the embedded payment-event ledger, the branch-level fix, and remaining invoice/expense/income reversal decisions.
- Added a targeted unit test for incremental receipt persistence. It has **not** executed because the current GitHub Actions runner-allocation failure remains unresolved.
- The invoice repricing and physical-delete endpoints remain unchanged pending an approved legal/accounting document lifecycle. Do not infer that a generic audit history makes a posted invoice immutable or compliant.


## Tunisia jurisdiction decision (17 Nov 2026)

The owner confirmed that the company is registered in Tunisia, selected **SUARL (Société Unipersonnelle à Responsabilité Limitée)** as its legal form, and confirmed **régime réel**. The accounting design baseline is documented in `TUNISIA_ACCOUNTING_BASELINE.md`, using the Tunisian Enterprise Accounting System (Law 96-112, conceptual framework and NC 01) rather than the public-sector state chart or a generic IFRS-only chart.

The SUARL decision adds explicit requirements for separating company and shareholder transactions, recording signed sole-shareholder decisions, maintaining the prescribed decision register, and supporting annual inventory, management report and accounts approval within the statutory period. The legal form, country framework, owner-declared régime réel and owner-reported **suspension de TVA** are settled. The exact scope, validity and documentary conditions of the VAT suspension, activity-specific tax treatment, applicable tax rates, accounting year, auditor applicability and opening balances remain unverified. The ERP must distinguish suspension from non-liability and ordinary exemption; do not apply it automatically to every transaction until the authorization is checked and the accountant approves the rules.


## Tunisia tax-profile decisions (17 Nov 2026)

- Confirmed by owner: Tunisia, SUARL, régime réel.
- Reported by owner: suspension de TVA.
- Evidence gap: owner does not currently have the official suspension certificate/authorization. Treat the status as reported but unverified; do not treat it as non-assujettissement, a blanket exemption, or permission to suppress VAT on all transactions.
- Continue non-tax ERP foundation work. Keep tax automation behind an evidence-and-accountant-approval gate.


## Permission-model audit addendum (17 Nov 2026)

The GS worker assignment allowlist does not currently include the core operational capabilities for tank management, stock posting/reversal, sales, custody, purchases or production, even though administrators possess them. The pump selection/status handlers are guarded by `commercial.read` despite mutating operational state. Traditional routes also grant broad authenticated-worker write access to several intake and production actions. These are documented gaps, not permissions to broaden automatically.

Stage 1 must define job-role capabilities and maker/checker separation, then implement backend route guards and frontend affordances together with authorization regression tests. Do not grant every capability to all workers.


## Fiscal-year configuration decision (17 Nov 2026)

The owner deferred choosing the fiscal-year closing date. The ERP must therefore keep the fiscal year configurable and unset until the owner/accountant confirms it. No calendar-year default and no olive-season-derived fiscal year. Statutory annual close and annual financial statements remain blocked until the company profile has approved start/end dates.


## NC 01 chart-of-accounts design completed (17 Nov 2026)

Added `docs/erp-audit/TUNISIAN_CHART_OF_ACCOUNTS_DESIGN.md` as a design-only blueprint. It preserves the seven NC 01 classes, defines Oro Verde analytical dimensions and SUARL controls, separates customer-owned custody from company inventory, and outlines source-event posting gates. It intentionally does not invent detailed account codes or debit/credit templates; these require current NC 01 cross-check and written approval by the Tunisian accountant.

Next technical foundation tasks:
1. Finish read-only inventory of source-event schemas and identifiers for every operational financial event.
2. Define canonical posting-source identity and idempotency rules before building journal APIs.
3. Define fiscal-period configuration as unset/required, honoring the owner's deferred fiscal-year decision.
4. Build chart/journal/posting only after accountant-approved accounts, tax treatment, opening balances and fiscal-year configuration are available.


## Financial source-event audit completed (17 Nov 2026)

Added `docs/erp-audit/FINANCIAL_EVENT_SOURCE_REGISTER.md`. The register maps traditional pressing invoices/receipts; GS olive and oil purchases/payments; wholesale invoices, payments, reversals, credits and returns; custody; production; stock; and manual passive income/expenses to authoritative source records. It explicitly separates revenue from cash settlement, customer custody from mill inventory, credit applications from cash, and stock movements from revenue.

Before GL implementation, resolve the listed traditional invoice replacement-payment and repricing/deletion hazards, give embedded traditional payments stable identities, normalize Decimal arithmetic, and define cancellation/reversal plus accrual/settlement semantics for manual income/expenses. GS tax treatment remains unconfigured. These are Stage 1/2 blockers, not permissions to alter live financial records.


## Posting identity contract completed (17 Nov 2026)

Added `docs/erp-audit/POSTING_IDENTITY_AND_IDEMPOTENCY.md`. It defines a unique source-event identity separate from API request idempotency, a transactional posting sequence, payload-fingerprint conflict handling, immutable reversals, business-date/fiscal-period separation, Decimal/unit normalization and the minimum concurrency/retry/reversal test matrix. This is a design contract only; no ledger collection or posting endpoint was created.

## Financial roles and maker/checker audit completed (17 Nov 2026)

Added `FINANCIAL_ROLE_AND_APPROVAL_MATRIX.md` after inspecting the actual GS permission implementation, financial route dependencies, service transactions and traditional accounting/invoice handlers.

Confirmed:
- Traditional API access remains coarse: 29 mounted routes accept any authenticated user, including load intake, oil-output/status/delivery, lab record creation and client creation.
- GS worker permissions cannot currently express purchase, sales, custody, production or stock-posting duties. Some routes require these non-assignable permissions with `current_user`; other high-risk routes additionally require `require_admin`.
- Purchase/sale approvals, customer payments, payment reversals, buyer credit and custody receipt/release remain administrator-only.
- GS stock adjustment can be initiated by a worker assigned broad `edit_records` (and `delete_records` for zeroing) without an independent checker. Pump state mutations use `commercial.read`.
- Selected GS sale, payment, supplier-payment, stock and custody workflows have useful transaction/idempotency controls, but these do not provide maker/checker separation.
- Traditional manual income/expense writes are direct inserts and deletes are physical; traditional invoice updates/deletes are transactional but still permit unsafe posted-document lifecycle behavior.

No runtime permissions were changed. Stage 1 now requires owner-approved job roles, independent checker assignments, financial visibility rules and thresholds, followed by backend service-level authorization, frontend capability alignment and API regression tests. Do not merge or deploy until the existing CI runner issue is resolved and tests execute.

### Direct olive-purchase registration and weighing evidence

The source review found that `POST /commercial/v1/olive-receptions` internally performs the purchase transition, lot creation and stock receipt in one transaction under the registering actor. The owner explicitly confirmed that the employee must record this purchase directly without a human review queue. The workflow must therefore **not** be split into a pending submission/checker process. Keep the transaction atomic and make it available only through a dedicated capability assigned to designated employees after that role assignment is decided. When gross/tare fields are implemented, bind both readings, server-derived net, measurement source, actor and timestamps to the same immutable reception evidence.


### Owner decision — direct olive purchase entry (17 Nov 2026)

The owner clarified that the employee must register the olive purchase and gross/tare/net weights directly, without submitting the operation for review. Do not add a purchase approval queue or hold the stock receipt pending supervisor approval. Stage 1 must make direct registration available to a designated employee capability, calculate and validate net weight server-side, and atomically commit purchase + traceability lot + stock receipt + audit evidence. Corrections must be explicit, reasoned and auditable. This direct-entry exception applies only to olive purchase/reception; it does not remove controls for payments, reversals, sales approval, stock adjustments or GL journals.


## Release and audit status after PR #3 (18 Nov 2026)

- The current `audit/erp-foundation` branch was merged into `main` through PR #3. Merge commit: `77af9cbbae845060e52a79fb5420c89f370e1f71`.
- The active pro5 Render frontend and backend are configured for `main` with automatic deploy on commit. The merge triggered both deployments, and both completed successfully with status `live` for merge commit `77af9cbbae845060e52a79fb5420c89f370e1f71` (frontend deploy `dep-dbufnpou01pc73eu90v0`; backend deploy `dep-dbufnpou01pc73eu90p0`). Render build/deploy events report success. A separate HTTP/browser smoke test was not possible through the available verification channel.
- GitHub Actions did not execute the required test steps in the latest known run because no runner was assigned (steps/logs were empty). This is not a passing test result. Backend tests, frontend build/typecheck and production smoke tests remain required.
- The branch audit documentation is now part of `main`; do not keep describing the already-merged audit as isolated/unmerged. Continue adding follow-up audit findings on a new focused branch or directly through the normal reviewed release process.
- The owner explicitly authorized merging and publishing the current state despite the runner issue. This release authorization does not waive the requirement to validate tests before the next functional implementation/release.

## Quantity-lineage follow-up (18 Nov 2026)

Source review traced the traditional intake quantity through GS and pressing:

1. Traditional intake stores one `loads.olive_kg` float; gross/tare do not exist yet.
2. GS direct purchase reads that source field, converts it to Decimal, and uses it for the customer-custody receipt, olive lot and ownership-transfer movement.
3. GS production consumes explicit Decimal quantities from GS olive lots; it does not read traditional load quantity directly. Lot balance/owner/quality checks govern consumption.
4. Traditional invoice creation copies both source `olive_kg` and measured `oil_kg`, and calculates its total from `oil_kg × price_per_kg`.
5. Traditional `/stats` currently calculates revenue from `olive_kg × price_per_kg`. This differs from invoice creation and requires a business-definition decision before either formula is changed.

The full field lineage, float/Decimal boundaries and the 12,450 / 4,250 / 8,200 kg acceptance case are recorded in `DATABASE_MAP.md`. Do not enable weighing or claim a scale integration until those tests pass and gross/tare/net are persisted with auditable provenance.


## Reporting and tariff-basis gate (18 Nov 2026)

The quantity-lineage review found that the traditional invoice total uses `oil_kg × price_per_kg`, while `/stats`, worker-report revenue and client-summary amount use `olive_kg × price_per_kg`. The revenue report instead sums cash payment events by payment date, and the client statement uses invoice totals and payment credits. These are distinct measures and must not be collapsed into one “revenue” number.

Before changing any formula or building GL posting templates, obtain owner/accountant confirmation of the tariff basis (per kg olives received, per kg oil measured/returned, or another service-fee basis) and define which screens show invoice value versus cash collected. Add a cross-report reconciliation test for one sample load with partial payment. This is a decision gate, not a code fix to guess.


## Detailed quantity-source audit (18 Nov 2026)

The source review confirms the following implementation boundaries:

- Traditional load intake currently accepts and stores only `olive_kg` as a float. No gross/tare snapshot is captured.
- Traditional pressing completion writes `loads.oil_kg`; yield uses `oil_kg / olive_kg`.
- Traditional invoice creation snapshots `olive_kg` and `oil_kg`, but computes the service invoice total as `oil_kg × current app price_per_kg`. The invoice stores the selected tariff and total.
- Traditional `/stats` and related client/worker summary paths use `olive_kg × price_per_kg`, not the invoice formula. This is a confirmed reporting/tariff-basis inconsistency. Do not patch one formula based on guesswork; owner/accountant must define whether the pressing tariff is per kg olives received, per kg oil returned, or another contractual basis. Then align invoice, dashboard, worker report and client statement with explicit separate measures for billed value and cash collected.
- GS direct customer-load purchase reads the traditional source `loads.olive_kg`, converts it through `Decimal(str(value))` when the source is a float, then creates the custody receipt, olive lot and ownership-transfer stock movement in one transaction. The original load is closed as sold and marked transferred. This path does not take a second weighing.
- GS supplier reception accepts Decimal variety-line quantities and posts purchase/lot/receipt atomically. It does not yet capture vehicle gross/tare/net or compare the sum of variety lines with a measured net weight.
- GS production takes explicit Decimal quantities against selected olive lots and posts matching consumption movements. It does not read traditional `loads.olive_kg` directly. Production input total is the sum of the entered lot lines.
- Precision crosses a float boundary in traditional intake and oil-output records; invoice code also converts oil output to float before Decimal tariff multiplication. GS command quantities and stock quantities use Decimal/Decimal128. This is a migration and serialization risk, not proof of an observed wrong value in existing records.

**Adopted design decision:** use server-derived net weight as the canonical quantity for all new vehicle receptions; retain `loads.olive_kg` as a compatibility alias equal to net until all traditional consumers are migrated. Supplier variety lines must reconcile exactly to the same reception net before posting. GS direct purchase must inherit that source net and never create a second weight. GS production continues to consume explicitly selected GS lot quantities, with stock ledger movements as the decrement authority.

**Additional release gates:**

1. Resolve the tariff basis and the confirmed invoice-vs-statistics formula mismatch before changing existing financial calculations.
2. Add an integration test proving 12,450.000 kg gross − 4,250.000 kg tare = 8,200.000 kg net, and that exactly 8,200.000 kg reaches the traditional load, GS direct-purchase lot/movement, supplier line reconciliation and any downstream production consumption.
3. Prove that the traditional invoice retains net olive kg as context but calculates its amount from the approved tariff basis and measured oil output where contractually appropriate.
4. Add a partial-payment reconciliation test distinguishing invoice value, paid amount, remaining balance and cash collected by payment date.
5. Add idempotent retry tests for traditional load creation and GS direct reception, including concurrent duplicate submissions.
6. Do not retrofit gross/tare into historical records that contain only `olive_kg`; classify them as legacy net-only/unknown gross and tare.
7. Keep runtime untouched until the tariff basis is confirmed and the weight/precision migration contract plus regression tests are approved.


## Critical accounting reconciliation gate — duplicate receipt projection (18 Nov 2026)

Static source inspection of `backend/routers/invoices.py` and `backend/routers/accounting.py` confirms that an incremental traditional invoice receipt currently has two representations:
- `invoices.payments[]` receives the new payment item.
- `invoices.history[]` receives an `updated` event whose paid-amount delta is the same receipt.

The daily-situation report currently projects both representations as receipt events. A single incremental receipt can therefore be counted twice in the report even though the invoice paid balance itself advances once. The client statement helper uses a different precedence rule, creating a further reconciliation risk between reports.

**Gate (must pass before financial reporting is treated as authoritative):**
1. Define one canonical payment-event identity and one source of truth for each receipt.
2. Change daily-situation projection so payment items and generic history deltas cannot both create the same receipt.
3. Preserve a legacy fallback only where itemized payment events are absent; mark inferred dates/amounts as legacy estimates.
4. Add tests for itemized-only, history-only, both-present, partial payments, and payment replacement compatibility. The TND 50.000 incremental payment test must show exactly TND 50.000 receipt once.
5. Reconcile daily-situation totals, invoice paid/balance snapshots, and client statement totals against the same underlying receipt IDs.
6. Do not edit historical financial records in place as a shortcut; any migration must be deterministic, auditable and separately approved.

This is a confirmed reporting defect, not a proposed accounting preference. Runtime code remains unchanged pending regression coverage and a runnable CI environment.


## Fiscal-year separation gate

The current accounting overview and daily-situation report are season-scoped through `active_season()` / `season_prefix()`. A date filter narrows the active-season dataset; it does not provide a fiscal-year ledger across seasons. This is a mill operations report boundary, not a valid substitute for a legal entity's annual accounting period.

Before implementing statutory GL reporting:
- Add a configurable fiscal year independent of the olive season.
- Require explicit start/end dates, opening balances, period status and close/reopen controls.
- Store business date, recorded timestamp and posted timestamp separately.
- Permit prior-period comparative reports across seasons without relying on current `active_season()`.
- Do not infer a calendar-year fiscal period. The user has deliberately deferred the dates.


## Inventory valuation and production-cost audit gate (18 Nov 2026)

Static source inspection confirms the GS stock ledger is quantity/ownership-based. Purchase lines retain acquisition price, but purchase-created lots and stock movements do not carry monetary value. Production records input/output quantities and extraction rate but no input-cost roll-up or conversion-cost allocation. Wholesale sale uses FIFO physical dispatch allocation, but the inspected flow does not post monetary inventory relief / COGS.

Before full-accounting go-live:
1. Keep the physical stock ledger authoritative for quantity, location, lot and ownership.
2. Add a separate append-only valuation subledger with cost layers linked to purchase/production source events and physical movement IDs.
3. Carry acquisition cost from approved olive purchase lines into company-owned olive cost layers.
4. Consume olive cost layers in production and allocate eligible conversion costs into oil/by-product outputs under the approved NC 04 policy.
5. Relieve oil carrying value on dispatch and reconcile returns/credit notes to the original cost layers.
6. Keep customer-owned custody outside mill-owned inventory valuation until an effective ownership transfer.
7. Preserve cost-layer identity through tank mixing; physical FIFO dispatch must not be mistaken for a statutory cost formula.
8. Reconcile valuation subledger totals to GL inventory control accounts at each fiscal close.

**Policy gate:** obtain written Tunisian accountant approval for cost formula, attributable acquisition costs, conversion overhead allocation, by-product and abnormal-loss treatment, impairment/NRV policy, and customer-custody/toll-processing treatment. Do not infer the cost formula from the current FIFO dispatch allocator.

**Acceptance gate:** the 10 test scenarios in `INVENTORY_VALUATION_AND_COST_ACCOUNTING.md` pass, including purchase-to-lot valuation, production input/output cost conservation, mixed-tank dispatch, returns, customer custody, retry idempotency and GL reconciliation. Legacy lots without reliable source cost remain explicitly unvalued; do not invent costs.

No runtime code or production data was changed in this audit.


## Expense recognition, payroll and fixed-asset gates (18 Nov 2026)

The existing manual expense/income forms do not separate recognition from settlement. The daily report treats each manual expense as incurred and paid on the same date, and each passive income as earned and collected on the same date. A generic WAGES category is not a payroll module; no dedicated payroll or fixed-asset/depreciation API was found.

The current daily-situation report also places approved olive inventory acquisitions (supplier purchases and customer-to-mill ownership purchases) in the expense bucket. Do not rely on its `net_result` as statutory profit until inventory acquisition, consumption and COGS are separated.

Before accounting go-live:
1. Introduce source documents/obligations separately from cash/bank settlement events, supporting due dates, partial payments, advances, and outstanding balances.
2. Reclassify company-owned olive/oil purchases as inventory acquisitions when recognition criteria are met; recognize costs on consumption/COGS or approved write-off, not merely on purchase.
3. Replace hard-delete of posted expenses/incomes with auditable reversal/adjustment events.
4. Design payroll only after Tunisian payroll specialist validation; support employee-level gross/net, employer charges, deductions, liabilities, payments and cost-centre allocations.
5. Add fixed-asset register, in-service date, cost basis, useful life, depreciation, impairment, disposal and GL reconciliation, subject to accountant-approved policies.
6. Keep the operational daily report distinct from statutory P&L, cashflow, receivables/payables and inventory valuation reports.

**Acceptance gate:** unpaid and partially paid supplier expense; earned but uncollected income; inventory purchase not immediately expensed; employee payroll reconciliation; asset depreciation/disposal; and all reversals must pass source-event reconciliation tests. No accounting policy or payroll rate should be invented in application code.


## Tax engine and invoice-compliance gate (18 Nov 2026)

Static source inspection confirms:
- Traditional pressing invoices do not store tax base/rate/amount, withholding, stamp duty, suspension evidence or a tax-rule version.
- GS wholesale invoices explicitly carry `tax_treatment_status = NOT_CONFIGURED`; no tax calculation is applied in the inspected sale-invoice flow.
- The company-reported VAT suspension is not backed by an authorization document available for verification.

Before tax posting or statutory invoice compliance is enabled:
1. Verify the current official suspension authorization, beneficiary, scope, conditions, quotas and validity.
2. Obtain accountant-approved tax treatment separately for pressing, olive purchase, custody, ownership purchase, bulk oil sale, by-products, assets and payroll.
3. Implement versioned effective-dated tax rules and immutable tax snapshots on posted documents.
4. Distinguish suspension, exemption, non-liability, non-registration and out-of-scope transactions.
5. Add mandatory legal invoice fields and tax adjustment/credit/debit-note workflows.
6. Keep the current fail-closed `NOT_CONFIGURED` state until approval; do not infer rates or tax outcomes from SUARL or régime réel alone.

**Acceptance gate:** prove valid/in-scope, expired, out-of-scope, historical invoice and credit-note tax scenarios with accountant-approved expected results. No tax rate or suspension treatment may be invented in code.


## Treasury / cash and bank reconciliation gate (18 Nov 2026)

The current payment documents identify payment amount/date and, for GS, method/reference. They do not identify a named cash drawer or bank account, and no cashbook, bank statement import/reconciliation, cheque lifecycle or cash-count module was found.

Before treasury go-live:
1. Configure company cash drawers and bank accounts with opening balances and authorized custodians.
2. Link each canonical payment/reversal event to exactly one actual treasury movement without duplicating receivable/payable settlement.
3. Add internal cash/bank transfers as paired balance-sheet movements with no P&L effect.
4. Implement bank statement import/matching, unmatched-item handling and period reconciliation.
5. Implement cheque receipt/issue/deposit/clearance/rejection lifecycle and cash drawer counts.
6. Preserve legacy payments without account identity as `UNALLOCATED_LEGACY`; never infer account from payment method alone.
7. Enforce dual authorization where required by the bank mandate and approved role matrix.

**Acceptance gate:** cash receipt, supplier payment, partial settlement, internal transfer, bank statement match, cheque clearance/rejection, payment reversal and cash-count variance all reconcile to payment subledgers and GL. See `CASH_AND_BANK_LEDGER_AUDIT.md`.


## Accounting regression coverage gate (18 Nov 2026)

Static test-source review found that the repository has useful invoice, client-statement, GS payment-reversal and stock/production tests, but no endpoint-level test for the full `/accounting/daily-situation` cross-source projection.

The traditional incremental-payment unit test explicitly confirms both an itemized payment and an `updated` history record are appended. The client statement helper has deduplication tests, but those do not cover the independent daily-situation projection. The accounting aggregation tests cover helper functions, not end-to-end event reconciliation.

Before any runtime financial fix:
- Add daily-situation regression tests for itemized/history overlap, legacy fallback, partial payments, GS PAY/REV, purchase inventory-vs-expense classification, unpaid/partial manual expenses, income collection, returns/credit notes and period boundaries.
- Run backend unit and MongoDB replica-set integration suites.
- Run frontend typecheck/build and affected e2e smoke tests.
- Require CI runner execution and logs; an unassigned/no-step workflow is not a pass.
- Preserve test run IDs and source-event reconciliation assertions.

See `ACCOUNTING_REGRESSION_TEST_COVERAGE.md`. No tests were run as part of this static audit.


## Canonical party master and subledger reconciliation gate (18 Nov 2026)

Traditional clients, GS suppliers, GS buyers and custody owners are separate role/domain records. Custody owners link to legacy clients, but no canonical party ID across all roles was found. Separate statements exist for traditional clients, supplier payables, buyer receivables, customer-to-mill purchase payables and custody balances.

Before consolidated ERP party reporting:
1. Introduce a canonical party identity with role-specific links, preserving every existing domain ID.
2. Resolve duplicates only through verified legal identifiers and controlled human review; never auto-merge by phone/name.
3. Keep receivable, payable and custody subledgers separate by legal relationship.
4. Display consolidated exposure by role without automatic set-off/netting.
5. Reconcile all legacy statements and preserve historical document snapshots during migration.

**Acceptance gate:** a party with multiple roles has one canonical identity and separate reconciled role balances; ambiguous legacy matches remain unlinked. See `PARTY_MASTER_AND_SUBLEDGER_RECONCILIATION.md`.

## Read-only source-adapter contract (17 Nov 2026)

Added `READ_ONLY_FINANCIAL_SOURCE_ADAPTER_CONTRACT.md` as the next technical design gate. It specifies a deterministic, versioned candidate-event envelope, source-specific adapters, eligibility states, stable blocking reasons, source fingerprints, and reconciliation reports.

The contract explicitly prevents the current `/accounting/daily-situation` projection from being reused as a GL feed. It records the confirmed duplicate traditional receipt projection (itemized payment plus history delta), the unallocated legacy paid-amount problem, the incorrect expense classification of inventory acquisitions, and the same-day accrual/settlement conflation in manual income and expense records.

**Next implementation sequence (still non-posting):**
1. Establish runnable backend/frontend CI and endpoint-level regression coverage before runtime financial changes.
2. Implement pure Decimal/date/unit normalization and deterministic fingerprints with unit tests.
3. Implement read-only adapters first for traditional invoice/receipt and GS supplier purchase/payment sources.
4. Add report-only reconciliation with explicit unresolved records and prove the adapter performs zero database writes.
5. Extend to sales, credits/returns, custody and stock only after event identities and lifecycle tests are available.
6. Keep all GL posting, tax calculation, inventory monetary valuation and treasury posting disabled until their separate policy and accountant gates pass.

No runtime code, permissions, database documents, financial records or Render services were changed by this design update.


## Daily-situation source-code reconciliation findings (18 Nov 2026)

Added `DAILY_SITUATION_RECONCILIATION_FINDINGS.md` after direct inspection of the current `backend/routers/accounting.py` and `backend/routers/invoices.py` implementations.

Confirmed:
- Current incremental traditional invoice payment writes both a `payments[]` item and a `history[]` paid-amount delta in the same transaction; `/accounting/daily-situation` sums both as receipts. A single receipt can therefore be reported twice.
- Manual income and expense records are projected as both recognition and cash settlement on the same date, although the source schema has no independent settlement event/account evidence.
- Supplier olive and customer-to-mill purchases are placed in the expense bucket; the report's `net_result` is not statutory profit because inventory acquisition is not separated from consumption/COGS.
- The endpoint does not load GS credit-note and return records, so it is not a complete sales/returns report.
- No dedicated endpoint-level regression test for the full daily-situation route exists in the inspected test tree.

**Runtime correction remains blocked** until the hosted runner starts and endpoint-level regression tests execute. CI run `44218616527` attempt 2 again ended with all six jobs at `runner_id=0`, empty steps and no logs. The source-level diagnosis is documented; no live records or runtime code changed.

## Vehicle weighing and future weighbridge contract (18 Nov 2026)

Added `VEHICLE_WEIGHING_AND_SCALE_INTEGRATION.md` after rechecking the current traditional and GS request schemas.

Source facts:
- Traditional `POST /loads` currently accepts only `olive_kg: float`; it stores no separate gross/tare readings or weighing provenance.
- GS `POST /commercial/v1/olive-receptions` accepts per-variety Decimal quantities and millime prices, but no vehicle gross/tare snapshot.
- GS direct purchase of an existing customer load inherits the existing `loads.olive_kg` net and must not weigh or physically receive the same load again.

The target is one reusable, immutable weighing-evidence model for traditional customer-load intake and GS supplier reception, with separate gross/tare timestamps and actors, manual/scale provenance, and server-derived Decimal net. The existing `loads.olive_kg` remains the compatibility alias for net during migration. GS supplier variety-line quantities must reconcile exactly to the measured net before atomic purchase/lot/stock receipt.

A missing tare is an incomplete operational measurement, not a human approval state. No finalized stock quantity may be posted until both readings exist and net is validated; once complete, the designated employee's direct reception proceeds without a second-person review. Historical net-only loads remain unchanged. A future scale adapter must preserve device/ticket/calibration evidence and idempotent offline synchronization; no hardware integration is claimed.

**Before runtime rollout:** confirm that the shared weighing UI/API scope should cover both traditional customer loads and GS supplier receptions, and later select the scale manufacturer/interface. These decisions do not block the data contract or test design. No runtime fields, UI, API, records or permissions were changed.

## Intake idempotency and offline synchronization gate (18 Nov 2026)

Added `INTAKE_IDEMPOTENCY_AND_OFFLINE_SYNC.md` after confirming:
- traditional `POST /loads` creates a new ID/code for every request and has no client request key/fingerprint;
- GS supplier reception's nested purchase/approval fingerprints do not cover all outer new-supplier metadata, allowing changed phone/tax values under the same request key to be silently ignored;
- the traditional arrival SMS is an external post-commit side effect and needs an outbox/deduplication contract;
- future offline phone synchronization requires a durable local operation queue and server inbox/idempotency record, not component state alone.

Order of work:
1. Restore a functioning CI runner (still unresolved; jobs currently have runner_id=0 and no steps).
2. Implement and test canonical request normalization/fingerprinting.
3. Implement traditional load idempotency with same-key replay, changed-payload conflict and concurrency-safe winner recovery.
4. Complete GS outer-command fingerprinting and supplier metadata conflict behavior.
5. Add transactional notification outbox and verify retry semantics.
6. Only then add gross/tare fields to the intake command and include all measurement/device evidence in the same request fingerprint.
7. Design and implement durable offline outbox/inbox synchronization before enabling disconnected worker intake.

Do not change the traditional load's legacy quantity basis or existing invoice/statistics formulas in this work. Preserve `loads.olive_kg` as net-only compatibility field during the later weighing migration. No runtime changes were made by this audit.

## Direct olive-purchase worker capability gate (18 Nov 2026)

Added `DIRECT_OLIVE_PURCHASE_CAPABILITY.md` after verifying current router and service-layer authorization.

Confirmed mismatch:
- Owner requires designated employees to register olive purchases directly without a human review queue.
- Current `POST /olive-receptions` and both underlying purchase create/approval services require `commercial.manage_purchases`.
- That capability is not assignable to workers. Thus ordinary workers cannot currently execute the intended direct reception path.

Target: add a dedicated `commercial.register_olive_purchase` capability for selected workers, enforced at a dedicated application-service boundary. It authorizes only the atomic physical purchase/reception + traceability + stock receipt + audit operation. It must not imply supplier payments, reversals, arbitrary purchase edits/approvals, stock adjustments, sales or GL posting.

Do not grant it to all workers. The owner has not yet identified the specific employees; assignment remains a later explicit admin action. The direct purchase remains no-review. This does not justify adding a human approval stage.

Runtime authorization work is gated by real CI execution and MongoDB transaction/permission tests. No current permission or employee record was changed.


## Runtime implementation status update (20 Nov 2026)

The earlier weighing and idempotency observations above are historical findings from the initial audit and must not be read as the current source state:

- Traditional intake now captures manual gross and tare, derives net on the server using Decimal arithmetic, and preserves the measurement snapshot/provenance while retaining `loads.olive_kg` as the downstream net compatibility field. The intake UI also supports supplier vehicle gross/tare and validates the supplier line against net.
- The shared scale profile/settings panel is merged to `main` (PR #3). This stores device configuration only; it does **not** connect to a physical indicator or prove live readings.
- Traditional load request idempotency is merged (PR #6), including same-key replay, changed-payload conflict and duplicate-key winner recovery.
- Designated-worker direct olive reception is enabled through the separate `commercial.register_olive_purchase` capability (PR #7). The capability is assignable by an administrator and does not add a second-person approval queue.
- Complete outer-command idempotency for GS supplier reception is under review in PR #8; do not count it as merged until all CI checks pass and the PR is merged.
- Still outstanding before reliable offline operation: durable client-side operation queue, server inbox, transactional SMS outbox, and explicit retry/reconciliation tests.
- Before deploying the additive idempotency collections/indexes, take a production database backup as requested. Do not alter existing business records or rewrite historical weights.
- Render deployment is not confirmed: the inspected `Oroverde` workspace services are connected to `abdelwehed-hue/huilerie-pro5`, while the active code changes are in `AbdelwahedJaouadi/huilerie-pro5`. Resolve the service repository binding and verify the target live URL before rollout.
