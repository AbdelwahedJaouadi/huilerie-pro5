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

- Confirm legal jurisdiction, fiscal-year start, accounting standard, chart of accounts, tax rules and invoice requirements with the company's accountant.
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
- Keep audit documentation isolated on branch `audit/erp-foundation`.
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
