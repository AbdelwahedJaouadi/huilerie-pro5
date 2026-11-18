# Daily Situation Report — Source-Level Reconciliation Findings

Project: Oro Verde / huilerie-pro5  
Reviewed source: `backend/routers/accounting.py` and `backend/routers/invoices.py` on `main`  
Status: read-only source review; no runtime correction made  
Date: 18 Nov 2026

## 1. Executive finding

`GET /accounting/daily-situation` is a useful operational projection, but its current implementation is not a reliable statutory P&L, cashbook, receivables/payables ledger or GL source.

The source review confirms several concrete issues:
1. A traditional invoice payment created through the current incremental-payment path is recorded in both `invoices.payments[]` and `invoices.history[]`; the daily-situation endpoint sums both as separate receipts. This can double-count the same receipt.
2. Supplier olive acquisitions and customer-to-mill purchases are classified as period expenses without a corresponding inventory/ownership cost-consumption model. This can understate operational result in the acquisition period.
3. Manual passive income is projected as both revenue and receipt on the same date; manual expense is projected as both expense and disbursement on the same date. The schema does not separately record earning/incurrence and settlement dates or proof of payment.
4. The endpoint's current receivable/payable totals are snapshots from source documents, not balances derived from a complete event subledger.
5. The endpoint does not load or project GS credit notes and accepted sale returns, so it is not a complete commercial revenue/returns view.

No data was changed. No claim is made that any particular live invoice has been double-counted; the issue is deterministic from the current write/read code paths and needs endpoint-level regression tests.

## 2. Confirmed traditional receipt double-count

### Write path

In `backend/routers/invoices.py`, `PATCH /invoices/{invoice_id}`:
- accepts `payment_amount`;
- increments the invoice paid amount;
- appends an item to `invoices.payments[]` when `payment_amount > 0`;
- in the same transaction, also appends a generic `history` event with `before.paid_amount` and `after.paid_amount`.

The same receipt is therefore represented in two places by design.

### Read path

In `backend/routers/accounting.py`, `GET /accounting/daily-situation`:
- iterates every `payments[]` item and adds its amount to `known_paid` and the day's `receipt` events;
- then iterates every `history[]` event with action `updated`;
- computes `after.paid_amount - before.paid_amount`;
- adds every positive delta as another `receipt` event and again increments `known_paid`.

The endpoint does not deduplicate the history delta against the payment child.

### Deterministic example

Invoice before payment:
- `paid_amount = 0`

One incremental receipt:
- `payment_amount = 100.000 TND`
- `payments[]` receives one item for 100.000
- `history[]` records paid amount changing from 0.000 to 100.000

Daily-situation projection:
- itemized payment contributes 100.000 to receipts;
- history delta contributes another 100.000;
- displayed `encaissements` can therefore include 200.000 for a single 100.000 receipt;
- `unallocated_legacy_receipts` is clamped at zero and does not correct the overcount.

This is a confirmed code-path defect, not a measured claim about current database totals.

### Required correction when runtime changes are safe

- Treat stable itemized payment child events as the canonical receipt source.
- Treat generic history only as audit evidence.
- Do not infer a second receipt from `history[].before/after` when an itemized payment event represents the same change.
- Add immutable payment IDs to itemized receipt records; current synthetic display IDs based on invoice/time/amount are not durable economic event IDs.
- For legacy invoices without itemized receipts, keep aggregate paid amounts and history deltas as `LEGACY_UNRESOLVED` / unallocated evidence. Do not invent a cash receipt date, payment method or treasury account.
- If an invoice has both itemized payments and an aggregate remainder, report the remainder separately for reconciliation; do not fabricate a payment.

## 3. Inventory acquisition misclassified as expense

The daily-situation endpoint reads approved `commercial_olive_purchases` and emits each purchase total as an `expense` event. It also reads supplier payment documents as `disbursement` events.

It reads `commercial_oil_purchase_documents` for customer-to-mill olive/oil acquisitions and emits their agreed amounts as `expense` events; associated payment documents become `disbursement` events.

The cash disbursement and the acquisition are different economic dimensions, so displaying them in separate report columns is not itself duplicate cash. The defect is that the report's `total_expenses` and `net_result` treat the acquisition value as period expense regardless of inventory recognition/consumption.

Required accounting distinction:
- company-owned raw material acquisition: inventory/ownership acquisition and payable/cash settlement;
- customer-owned custody: no company inventory or purchase expense merely from receipt/storage/processing;
- inventory consumption/COGS: recognized under approved NC 04 cost valuation and title/consumption rules;
- supplier/customer payment: settlement only, not another purchase cost.

Until valuation and ownership policies are approved, the daily report's `net_result` must remain explicitly an operational indicator, not statutory profit.

## 4. Manual income/expense date conflation

The current `accounting_passive_incomes` and `accounting_expenses` records contain one business date, amount, payment method and notes. The daily-situation endpoint emits:
- passive income as both `revenue` and `receipt` on `income_date`;
- expense as both `expense` and `disbursement` on `expense_date`.

The same source record is therefore assumed to be earned/incurred and settled on the same date. The schema does not prove that a receipt/disbursement actually occurred, does not identify a cash drawer/bank account, and does not support partial settlement or independent due/settlement dates.

Required future lifecycle:
- source document / obligation or earned-income record;
- recognition date and due date;
- one or more stable settlement events with settlement date, method, account identity and external evidence;
- void/reversal events instead of physical deletion.

Do not derive cashbook entries from the existing generic `payment_method` field.

## 5. Incomplete commercial event coverage

The daily-situation query currently loads:
- traditional invoices;
- approved GS supplier olive purchases and supplier payments;
- customer-to-mill purchase documents and payments;
- GS sales invoices, sale payments and payment reversals;
- passive incomes and expenses.

It does not load the GS credit-note collection or accepted/rejected sale-return records. Therefore its revenue/receivable view cannot be treated as complete for periods containing credits or returns. A payment reversal is included as a negative receipt adjustment, but it is not a substitute for a credit note or accepted goods return.

Future event adapters must separately represent:
- payment reversal;
- commercial credit note and credit application;
- accepted physical return and stock restoration;
- rejected return (informational, no credit/stock posting).

## 6. Current report fields and interpretation

The endpoint calculates:
- `total_revenue` from revenue events;
- `total_expenses` from expense events;
- `net_result = total_revenue - total_expenses`;
- `encaissements` from receipt and receipt-adjustment events;
- `decaissements` from disbursement events;
- current receivables/payables from document outstanding snapshots;
- unallocated legacy receipts from paid amount less projected known receipt amounts, clamped at zero.

These values are not a balanced accounting statement:
- revenue/expense categories currently include inventory acquisitions and manual records with conflated dates;
- receipt events can double-count current traditional incremental payments;
- outstanding balances are not derived from a canonical customer/supplier subledger;
- tax, inventory valuation, COGS, fixed assets, payroll and bank reconciliation are incomplete;
- accepted returns and credit notes are omitted.

Do not label `net_result` statutory net profit or `encaissements/decaissements` reconciled cashbook balances.

## 7. Required endpoint-level regression tests

The current repository has invoice unit tests and client statement unit tests, but no dedicated endpoint-level test was found for the full `/accounting/daily-situation` projection. Add tests before changing this endpoint:

1. **Single current receipt:** one `payments[]` child plus matching history paid delta produces exactly one receipt event and exactly 100.000 TND, not 200.000.
2. **Multiple partial receipts:** two stable payment children plus two matching history entries produce the sum of the two children exactly once.
3. **Legacy aggregate only:** positive `paid_amount` without itemized payments remains unallocated; no authoritative receipt is fabricated.
4. **Legacy history only:** positive history delta without itemized receipt remains unresolved audit evidence and is not a cash receipt.
5. **Itemized plus unexplained remainder:** itemized total is counted once; difference from paid snapshot is separately flagged.
6. **Price edit only:** history event with no paid delta creates no receipt.
7. **Supplier purchase:** acquisition value is not represented as statutory operating expense until inventory consumption/approved valuation policy says so; payment is settlement only.
8. **Customer custody:** owner-owned product does not become mill inventory or purchase expense.
9. **Manual expense/income:** no actual settlement is inferred without a separate settlement record.
10. **Payment reversal vs sale return:** reversal changes settlement only; accepted return/credit are distinct events.
11. **Credits/returns:** accepted credit and return are visible in a complete commercial period report; rejected return has no recognized credit/stock event.
12. **Receivable/payable snapshots:** document snapshot totals reconcile to the source subledger and report discrepancies rather than silently substituting them.

These tests must run through the endpoint with isolated fixtures and assert both event lists and summary totals. Unit tests for helper functions alone are insufficient.

## 8. Release boundary

Do not patch the runtime endpoint until:
- GitHub Actions actually assigns a runner and executes steps (current CI attempts show `runner_id=0`, empty steps and no logs);
- endpoint-level tests exist and pass;
- legacy receipt handling is specified and reconciled;
- product ownership and inventory cost policy are approved where they affect financial results.

This document changes no runtime code, collections, financial records, permissions or Render deployment.
