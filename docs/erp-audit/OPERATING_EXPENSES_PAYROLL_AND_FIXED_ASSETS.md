# Operating Expenses, Payroll and Fixed Assets Audit

Project: huilerie-pro5  
Base: main at `bc06a29dade6a747a5b0ac30b665b46be12e6ec1`  
Method: static inspection of mounted accounting routes, frontend accounting page, daily-situation projection and repository file tree. No live records changed.

## 1. Executive finding

The current accounting module records simplified season-scoped income and expense forms. It is not a payroll subledger, fixed-asset register, accrual/payable workflow, or cost-centre system. Its daily report also classifies company-owned inventory acquisitions as expenses, so its `net_result` must not be treated as statutory profit.

## 2. Confirmed classification issue in daily-situation

In `backend/routers/accounting.py`, the daily-situation endpoint:
- Adds approved supplier olive purchases from `commercial_olive_purchases` as `kind="expense"` using the full `total_amount_dt`.
- Adds customer-to-mill olive/oil purchase documents from `commercial_oil_purchase_documents` as `kind="expense"` using the full `agreed_amount_tnd`.
- Separately tracks the corresponding outstanding balances as current payables.
- Calculates `net_result = revenue - expense`.

The underlying workflows create company-owned lots/stock and represent ownership acquisition. In a normal inventory purchase, the purchase amount initially represents an inventory asset (subject to recognition and valuation rules), not automatically a period expense. The cost becomes expense through consumption/COGS or another approved write-off/impairment event.

Therefore the current daily-situation `total_expenses` and `net_result` can materially misstate period performance when inventory purchases are included. The report can remain useful as a source-document cash/operational activity view, but its profit label must not be used as statutory gross profit or net income until inventory purchase and cost recognition are corrected.

**Required treatment:** classify purchases by economic nature and ownership:
- Mill-owned olives/oil: inventory acquisition and payable/cash settlement; no immediate P&L expense merely because purchased.
- Customer-owned custody: memorandum/quantity custody and contractual service obligations; not mill inventory by default.
- Customer-to-mill ownership purchase: acquisition of mill inventory at the effective ownership-transfer date; no second physical receipt if the stock was already in custody.
- Consumables/services/wages/energy: expense or prepaid/asset according to their substance and period of benefit.
- Inventory consumption, sale dispatch, abnormal loss and approved write-down: recognize cost/expense through the applicable valuation policy.

## 3. Manual income/expense forms collapse accrual and settlement

Current `ExpenseInput` stores:
- category, description, expense date, amount, payment method, beneficiary and notes.
- It does not store supplier invoice/document identity, due date, settlement status, actual payment date, one-or-many payment events, payable balance, tax treatment, cost centre, attachment evidence or reversal reference.

The daily-situation report creates both an expense event and a disbursement event for every manual expense on the same `expense_date`, using the full amount. Thus every entry is implicitly treated as both incurred and paid on the same date. It cannot faithfully represent an unpaid supplier invoice, partial payment, advance, prepaid expense, accrued liability or later settlement.

The passive-income form has the analogous limitation: it stores income date, amount and payment method, and the daily report creates both revenue and receipt on that date. It cannot represent an earned but uncollected receivable or later/partial collection.

This is not necessarily duplicate counting inside the separate revenue/expense versus receipts/disbursements totals. It is a loss of the distinction between recognition date and settlement date.

**Required model:** record the underlying invoice/obligation or earned income separately from one or more immutable cash/bank settlement events. Each settlement needs a stable ID, actual date, method, cash/bank account, reference, amount and actor. Store due date and outstanding balance on the obligation. The report must derive accrual and cash views independently.

## 4. Payroll is not implemented as a payroll subledger

The UI and API expose a generic expense category `WAGES`, but the inspected repository contains no dedicated payroll run, employee compensation, attendance/time, gross pay, deductions, employer contributions, net-pay settlement, payslip, payroll tax/withholding or employee payable workflow.

A single WAGES expense line cannot support:
- employee-by-employee gross/net payroll;
- accrual of wages before payment;
- salary advances and deductions;
- statutory social contributions and withholding;
- separate employer cost versus employee net payment;
- allocation of labour to pressing, production runs, maintenance, administration or other cost centres;
- payroll reconciliation to cash/bank and liabilities.

Do not mistake the presence of a WAGES expense category for payroll functionality. Build a payroll module only after the Tunisian accountant/payroll specialist confirms applicable obligations, rates, filing requirements and employee data controls.

## 5. Fixed assets and depreciation are not implemented

A repository-wide source-tree scan found no dedicated fixed-asset, depreciation or disposal module/API. The frontend declares an `AccountingInvestment` type, but the inspected accounting backend has no matching investment endpoints. This type alone is not an asset register.

Required future capabilities:
- asset identity, class, owner, location, custodian, supplier and acquisition document;
- acquisition date, in-service date, cost basis, eligible directly attributable cost and tax treatment;
- useful life, residual value, depreciation method and frequency, accumulated depreciation and net book value;
- componentization where needed, impairment, revaluation where legally permitted, disposal and gain/loss;
- links to invoices, payments, maintenance, insurance and production cost centres;
- immutable depreciation runs, reversals and GL posting identities.

Do not treat every item categorized as investment as a fixed asset without checking recognition criteria and materiality. Repairs/maintenance and capital improvements must be distinguished under the applicable Tunisian rules.

## 6. Deletion and audit risk

The current manual income/expense records have physical DELETE endpoints. The frontend exposes delete actions. This is unsuitable once those records support statutory postings, payroll accruals or asset accounting. Posted records must be corrected by linked reversal/adjustment events, with actor, date, reason and original source retained.

## 7. Acceptance gates

1. Inventory acquisition test: approve a company-owned olive purchase; daily P&L expense does not immediately include the full inventory asset cost.
2. Consumption/COGS test: when the inventory is consumed or sold, the correct valued cost is recognized once.
3. Unpaid expense test: record a supplier invoice with no payment; expense/asset and payable recognition are separate from cash disbursement.
4. Partial settlement test: one obligation can have multiple immutable payment events; remaining payable reconciles.
5. Passive-income test: earned income and later partial collection appear on separate recognition and cash dates.
6. Payroll test: gross wages, employer charges, deductions, employee payable, net payment and cost-centre allocation reconcile.
7. Asset test: capitalized asset cost, depreciation, accumulated depreciation, net book value and disposal reconcile to GL.
8. Deletion test: posted income, expense, payroll and asset events cannot be physically deleted; reversals preserve history.
9. Report test: accrual P&L, cash movement, receivables/payables and inventory/COGS are separate views with reconciled source-event IDs.
10. All events use TND Decimal arithmetic, fiscal periods independent of olive seasons, stable IDs and idempotent posting.

## 8. Boundaries

This document records static code findings and target controls. It does not establish that the current live database contains any particular expense, payroll or fixed-asset records. No runtime code, database document or financial balance was modified. Tunisian payroll, tax and asset policies require specialist confirmation before implementation.
