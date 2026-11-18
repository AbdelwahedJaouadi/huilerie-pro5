# Full Accounting Gap Analysis (Initial Audit)

## Executive finding

The existing `Comptabilite` module is an operational financial dashboard, not full general-ledger accounting. It consolidates source-document totals and a daily event report. No chart-of-accounts, journal-entry, general-ledger, trial-balance, balance-sheet, period-close or tax-ledger API was found in the inspected `backend/routers/accounting.py`.

## What exists today

- `GET /api/accounting/overview`: aggregates traditional invoices and GS commercial source documents for the active olive season.
- `GET /api/accounting/daily-situation`: builds daily/period reporting events from invoices, purchases, payments, reversals, passive income and expenses.
- Passive income records: list/create/delete.
- Expense records: list/create/delete.
- Frontend `/comptabilite`: overview and daily-situation tabs, summary cards, source-document tables and simple income/expense entry.
- Commercial workflows already retain source documents, payment records, credit notes, reversals and customer/supplier balances.
- Accounting routes inspected so far use `require_admin`; this is not yet a role matrix for accountant, cashier, manager and read-only staff.

## Runtime and database facts

- The user explicitly confirmed that pro5 intentionally uses the existing MongoDB database named `huilerie-pro3`. Do not treat the database name as evidence of a wrong connection.
- `backend/lib/db.py` creates one Mongo client and one configured `db` object. The traditional API and `backend/commercial/routers.py` import that same handle. GS and the traditional app therefore share the same database in the application code.
- Whether the Render environment variables match that intended database was not independently exposed by the Render service-details response; the user's explicit confirmation is the accepted operational configuration for this audit.
- The collection listing observed earlier did not show `accounting_expenses` or `accounting_passive_incomes`; their existence/use should be verified against the confirmed live database before assuming these modules contain operational history.

## Critical gaps for full double-entry accounting

1. **Chart of accounts:** no configurable account tree, account classes, account codes or account control rules found.
2. **Journals and entries:** no general journal, balanced debit/credit entry model, posting service or immutable posted-entry lifecycle found.
3. **General ledger:** no account-by-account ledger with opening, movement and closing balances found.
4. **Trial balance:** no debit/credit trial balance endpoint or reconciliation found.
5. **Financial statements:** no formal balance sheet, income statement or cash-flow statement generated from posted ledger balances.
6. **Receivables/payables subledgers:** operational balances exist in source workflows, but no demonstrated reconciliation to control accounts in a general ledger.
7. **Cash and bank:** payment methods are recorded in source documents, but no complete cashbook, bank account ledger, bank reconciliation or bank statement import workflow was found.
8. **Tax:** no configured tax codes, tax periods, tax reports or jurisdiction-specific posting rules found.
9. **Fixed assets:** no asset register, depreciation schedules or disposal accounting found.
10. **Period close:** no accounting-period locking, closing entries, retained earnings carry-forward or reopening approval workflow found.
11. **Audit and corrections:** passive income and expense endpoints physically delete records. Traditional invoice deletion also physically removes the invoice after writing an audit event. These are material financial-history risks; the target ledger must correct posted financial events through reversal/adjustment rather than deletion.
12. **Cost accounting:** no integrated cost-centre, production-cost allocation or finished-goods valuation ledger was found in the inspected accounting module.

## Important current behavior and risks to preserve or resolve

- Money calculations in parts of the accounting overview use Decimal/Decimal128-oriented helpers, but the traditional invoice workflow still converts oil quantity to binary float before calculating the total. The financial core should standardize decimal-safe quantity and money handling end-to-end.
- Traditional and commercial financial documents have separate source collections but share the same database.
- The current summary is scoped to the active olive season. Full accounting must support fiscal years and arbitrary accounting periods independently of the olive season.
- The frontend contains explicit cash-basis comments for collected revenue. Full accrual accounting must distinguish invoice revenue, cash receipts, payables, expenses and stock valuation rather than mixing them into one total.
- The frontend declares an `AccountingInvestment` type, but no corresponding investment API route was found in the inspected accounting backend.
- Traditional load creation, status changes, oil recording and delivery are available to authenticated users; invoice creation/update/deletion are admin-only. This is a partial role split, not yet a documented least-privilege role matrix.
- Production runtime validation rejects `AUTH_DISABLED=true` when the app is running in production. Keep this fail-closed behavior.

## Proposed target accounting architecture

- `accounting_chart_accounts`
- `accounting_fiscal_periods`
- `accounting_journals`
- `accounting_journal_entries` (header)
- `accounting_journal_lines` (debit/credit lines)
- `accounting_posting_sources` (unique source type + source ID + event type)
- `accounting_tax_codes` and tax-period summaries
- `accounting_bank_accounts` and bank-reconciliation records
- `accounting_fixed_assets` and depreciation schedules
- Cost centres / production cost allocations as a later subledger.

These are proposed names, not existing collections. Do not create them until the posting rules and migration strategy are approved.

## Non-negotiable accounting invariants

- Each posted journal entry balances: total debit = total credit.
- Posted entries are immutable; corrections use reversing or adjusting entries.
- Source posting is idempotent: a source event can be posted only once.
- Journal posting and source-state transition are atomic where possible.
- Subledger totals reconcile to general-ledger control accounts.
- Every entry records source document, actor, timestamps, currency and fiscal period.
- Fiscal-period closure blocks unauthorized backdated postings.
- All money is stored and calculated using Decimal128 or integer minor units; never binary floating point.


## Financial source-event register completed (17 Nov 2026)

Added `FINANCIAL_EVENT_SOURCE_REGISTER.md` after inspecting the traditional invoice routes and GS purchase, production, sale, payment, reversal, credit-application, return, custody and stock-ledger services.

Additional source-level risks confirmed:
- Traditional invoice PATCH still accepts legacy `paid_amount` as a replacement aggregate. It can change the cumulative paid snapshot without creating a corresponding immutable payment event. Restrict/retire this path before GL posting.
- Traditional invoice repricing and physical deletion remain incompatible with immutable posted accounting documents.
- Traditional invoice payment events are embedded objects without their own immutable payment ID; legacy aggregate fallback cannot establish the actual receipt date.
- Traditional invoice quantity conversion passes through Python float before amount calculation; standardize Decimal arithmetic end-to-end.
- GS sales invoice currently stores `tax_treatment_status = NOT_CONFIGURED`; tax treatment must remain blocked until accountant-approved tax rules are configured.
- Manual passive-income and expense endpoints create season-scoped records but physically delete them. Their schemas also do not clearly separate expense/income recognition from the related cash settlement.
- Customer custody receipts/releases and stock movements are physical/ownership subledger events, not automatically company purchases, revenue or cash.
- Buyer credit application settles receivables using existing credit; it is not a cash payment or new revenue.
- Payment reversal reverses a settlement event and must not be treated as a sales return/revenue reversal by default.

The register is based on static source inspection. It does not imply a GL implementation or prove every legacy document shape.

## Financial roles, approvals and source-level controls (17 Nov 2026)

Added `FINANCIAL_ROLE_AND_APPROVAL_MATRIX.md` after reviewing current route dependencies and the underlying GS and traditional services.

The key distinction is between transaction atomicity and segregation of duties: several GS flows correctly transact their source document, stock/payment changes and audit event together, but the same administrator can still create and approve the transaction. The code does not yet enforce maker/checker identity separation.

Current blockers include:
- The worker allowlist cannot grant purchasing, sales, custody, production or stock-posting capabilities; some routes with `current_user` therefore remain inaccessible to workers, while other high-risk routes explicitly require an administrator.
- Lot balance adjustment is available through broad worker-edit permissions without independent approval.
- Pump selection/status mutate state under `commercial.read`.
- Traditional load, oil-output, status, delivery, lab creation and client creation routes are available to any authenticated user rather than job-specific roles.
- Manual passive income/expense creation is a direct insert and deletion is physical; no review/post/reversal state exists.
- Traditional invoice update/delete are transactional but still allow repricing and physical removal of financial source documents.

Target controls now specify role-specific action capabilities, no self-approval for purchases, sales, payments, reversals, stock adjustments or GL journals, audit evidence, exception handling, and route-level tests. This remains a design/source-audit result only; runtime authorization and live data were not changed.

### One-step purchase and weighing approval control

A further route-level review found that `POST /commercial/v1/olive-receptions` internally builds an approval command and performs purchase approval, lot creation and stock receipt within the same transaction initiated by one actor. This is atomic but not maker/checker. The workflow must be split into submitted draft and independent approval, with approval posting purchase + lot + stock + audit atomically.

The approved snapshot must include gross, tare and server-calculated net weights, weighing provenance, supplier, varieties, prices and receiving location. Any change after submission must invalidate the approval. This is also the required foundation for future scale integration; no scale integration is claimed today.


## 13. Inventory valuation and production-cost audit (18 Nov 2026)

A dedicated source review of `commercial/services/purchases.py`, `purchase_approval.py`, `production.py`, `sales.py`, `stock_ledger.py` and the inventory schemas confirms that GS currently maintains a **quantity/ownership stock ledger**, not a complete monetary valuation subledger.

- Olive purchase lines store Decimal128 quantity, unit price and line total.
- Purchase approval creates an olive lot and a quantity-only receipt movement. The inspected lot does not retain acquisition unit cost or carrying value.
- Production stores olive input quantities, oil output quantity and extraction rate, then posts olive consumption and oil receipt movements. It does not accumulate input carrying value or conversion costs into the produced oil lot.
- Sale approval uses FIFO stock allocations for physical dispatch, but the inspected flow does not relieve a monetary inventory value or post COGS. FIFO quantity allocation is not proof that FIFO is the approved statutory cost formula.
- The owner dimension distinguishes mill-owned from customer-owned custody stock; preserve this distinction in any valuation subledger.

A new design-only document, `INVENTORY_VALUATION_AND_COST_ACCOUNTING.md`, records the evidence, required cost-layer and production-cost model, policy decisions requiring Tunisian accountant approval, and acceptance tests. No live stock or financial records were changed.


## 14. Operating expense, payroll and fixed-asset review (18 Nov 2026)

A source review of the mounted accounting API and frontend confirmed that:
- Manual expenses are generic records with category, description, date, amount, payment method, beneficiary and notes. There is no obligation/invoice identity, due date, payment status, partial settlement ledger, or independent settlement date.
- Daily-situation projects each manual expense as both an expense and a disbursement on the same expense date. Passive income is similarly projected as both revenue and receipt on the income date. The separate totals are not necessarily duplicate counting, but accrual recognition and cash settlement cannot be dated or reconciled independently.
- The `WAGES` category is a generic expense only. No dedicated payroll run, employee-level gross/net pay, deductions, employer contributions, payroll liabilities, payslip or payroll settlement subledger was found in the inspected repository.
- No dedicated fixed-asset register, depreciation, impairment or disposal module/API was found. The frontend's `AccountingInvestment` type has no matching backend route in the inspected accounting module.
- The daily-situation endpoint classifies approved supplier olive purchases and customer-to-mill olive/oil purchases as expenses at full purchase amount, while these workflows create company-owned inventory/ownership acquisition records. This can overstate period expenses and understate the reported net result until inventory consumption/COGS is recognized. Treat the current `net_result` as a source-document operational indicator, not statutory profit.

See `OPERATING_EXPENSES_PAYROLL_AND_FIXED_ASSETS.md` for source details, target event model and acceptance tests. No runtime code or live records changed.


## 15. Tax engine and invoice compliance review (18 Nov 2026)

The traditional invoice creation path records oil quantity, tariff, total, paid amount and balance, but the inspected invoice schema/write path has no tax base, rate, tax amount, suspension/exemption reason, stamp duty, withholding or applied tax-rule version.

The GS wholesale invoice explicitly stores `tax_treatment_status = NOT_CONFIGURED`; the inspected flow does not calculate tax or snapshot a suspension authorization. This is a correct fail-closed status and must remain until tax configuration is approved.

The owner-reported suspension de TVA is not documentary-verified. The company must not be treated as non-assujettie or given a blanket VAT exemption. See `TAX_CONFIGURATION_AND_INVOICE_COMPLIANCE.md` for required authorization evidence, transaction-specific tax-rule model and acceptance tests. No tax settings or invoices were changed.


## 16. Cash and bank ledger review (18 Nov 2026)

Traditional invoice receipts store amount, timestamp and actor but no method or cash/bank account. GS payment documents store date, amount, method and selected references, with useful PAY/REV idempotency and receivable/payable reconciliation, but no specific cash drawer/bank account identity or statement reconciliation.

A repository-tree scan found no dedicated cashbook, bank-account, cheque-register, cash-count or bank-statement reconciliation module/API. Therefore current payment documents prove settlement against an invoice/payable in the application, but do not provide a complete account-level treasury ledger or external bank clearance evidence.

See `CASH_AND_BANK_LEDGER_AUDIT.md` for target account, treasury transaction, statement line, reconciliation and cash-count structures. No payment or bank data changed.


## 17. Accounting regression coverage review (18 Nov 2026)

The test tree contains invoice mutation unit tests, client statement payment-helper tests, accounting aggregation-helper tests, and GS payment/stock integration tests. It does not contain an endpoint-level regression test for the complete `/accounting/daily-situation` projection.

In particular, `test_incremental_payment_is_appended_to_payment_ledger` confirms an incremental traditional payment appends both an item in `payments[]` and a generic `history` entry. The client-account helper tests cover their own deduplication behavior, but do not exercise the separate daily-situation endpoint that projects both representations. The accounting aggregation tests cover helper/pipeline behavior, not cross-source event reconciliation.

See `ACCOUNTING_REGRESSION_TEST_COVERAGE.md` for the source-based test inventory and required regression matrix. This is static inspection only; tests were not executed and no test pass is claimed.


## 18. Cross-domain party identity and subledger review (18 Nov 2026)

Traditional clients are primarily keyed by phone; GS suppliers and buyers are separate collections with normalized-name uniqueness; custody owners link to legacy clients by legacy client ID and phone. Separate read models exist for traditional client statements, supplier payables, buyer receivables, customer-to-mill purchase payables and custody balances.

No canonical party ID spanning all roles was found in the inspected model. This does not prove live duplicate records, but it means the same real-world party can exist in several domains without guaranteed shared identity. Cross-domain search is not identity resolution.

A future canonical party master should link role-specific records while preserving separate receivable/payable/custody subledgers. Never auto-merge by phone/name and never automatically net receivables against payables. See `PARTY_MASTER_AND_SUBLEDGER_RECONCILIATION.md`. No live party records changed.
