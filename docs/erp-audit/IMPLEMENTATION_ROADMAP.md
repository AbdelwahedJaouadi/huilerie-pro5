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

### One-step purchase approval and weighing evidence follow-up

The financial-role review found that `POST /commercial/v1/olive-receptions` internally constructs an approval command and creates the purchase, lot and stock receipt in one transaction under the initiating actor. This preserves atomicity but provides no independent purchase checker. Stage 1 must split submission from approval while keeping approval-time stock posting atomic. The approval snapshot must bind gross, tare, server-derived net, measurement provenance, supplier, price, variety and receiving location. A change to the submitted snapshot must invalidate approval and require resubmission. This also preserves the future weighbridge integration requirement.


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
