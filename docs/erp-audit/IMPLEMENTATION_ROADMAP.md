# Oro Verde ERP Implementation Roadmap

Target decisions:
- One mill (single site), with no multi-site complexity in the first release.
- Full double-entry accounting.
- All staff use the system through role-specific access.
- Start with foundation audit; do not rebuild working modules.

## Stage 0 — Source and runtime audit (current)

- [x] Confirm repository `abdelwehed-hue/huilerie-pro5`, default branch `main`.
- [x] Confirm the pro5 frontend and backend Render services exist and their latest inspected deploys are live on the same main commit.
- [x] Inspect FastAPI entry point, shared MongoDB handle, core routers and frontend routes.
- [x] Confirm that GS and the traditional app import the same configured MongoDB handle.
- [x] Identify existing accounting dashboard/reporting and its limitations.
- [x] Connect read-only to the available Atlas project and inspect the listed databases, collections, selected document counts and indexes.
- [ ] Confirm the pro5 Render service's actual `MONGO_URL` target and `DB_NAME`; current Render service details did not expose these values.
- [ ] Complete all route, collection, index and permission inventories.
- [ ] Inspect unclassified migration/snapshot collections and validate data references.
- [ ] Run existing automated tests and typecheck/build in a controlled environment.

**Exit gate:** documented source/runtime map and a verified list of existing behavior that must not regress, including confirmation of the production database used by pro5.

## Stage 1 — Stabilize the existing operational platform

- Define ownership and contracts for traditional loads, invoices, lab and GS documents.
- Resolve contradictory database documentation.
- Review destructive delete paths and replace deletion of financially meaningful records with cancellation/reversal where required.
- Verify traceability, idempotency, transaction boundaries and stock-ledger reconciliation.
- Standardize business identifiers and source-document references.
- Establish role matrix and permission checks for every sensitive endpoint.

**Exit gate:** core reception-to-production-to-stock-to-sale workflows pass regression tests.

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

**Exit gate:** sample batch costs reconcile to source expenses and inventory valuation.

## Stage 7 — Workforce, maintenance and management dashboards

- Staff records, shifts, attendance and task assignments.
- Equipment register, preventive maintenance and downtime.
- Role-specific operational dashboards.
- Executive dashboard with drill-down to source records.
- Alerts for operational, stock and financial exceptions.

## Stage 8 — Optimization

- Season comparisons and forecasting.
- Anomaly detection after data quality is proven.
- Offline mill workflow and synchronization only after the online source-of-truth model is defined and tested.
- Multi-site support only if the business later requires it.

## Delivery rules

- Work only in `huilerie-pro5`.
- Keep the audit documentation isolated on branch `audit/erp-foundation`.
- No production data changes during source audit.
- No database split during the initial phases.
- No large-bang rewrite.
- Every implementation unit includes backend tests, frontend typecheck/build and a regression test for affected existing workflows.
- Deploy only after the user approves the implementation scope and the release passes its test gate.
