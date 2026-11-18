# Accounting Regression Test Coverage Audit

Project: huilerie-pro5  
Base: main at `d2042d4de00d07396e7525634dbc3e3608f04a97`  
Method: static inspection of test sources and source functions. Tests were not executed in this audit.

## 1. Executive finding

The repository contains useful unit and MongoDB integration tests for invoice mutation, client statement payment calculations, GS payment reversals, purchase/production stock operations and transactional rollback. However, the accounting daily-situation endpoint's cross-source event projection is not covered by an endpoint-level regression test in the inspected test tree.

This gap allowed an overlap between traditional invoice `payments[]` and `history[]` to remain untested: the invoice unit test explicitly confirms that one incremental payment adds both a payment item and an updated history item, while the daily report independently projects both as receipts.

## 2. Existing relevant test coverage

### Traditional invoice unit tests

`backend/tests/test_invoices_unit.py` includes:
- invoice total and balance calculation;
- duplicate invoice prevention per load;
- invoice update/history behavior;
- incremental payment appended to payment array;
- overpayment and negative-payment validation;
- price snapshot preservation;
- concurrent invoice edit rejection;
- deletion audit snapshot behavior.

The incremental payment test checks that after a payment, both `payments` and `history` have been appended. It does not call the daily-situation endpoint or assert that the report emits one receipt event only.

### Client account statement tests

`backend/tests/test_client_accounts_unit.py` covers:
- itemized partial payments counted once;
- legacy aggregate paid amount fallback;
- oversized/inconsistent payment array behavior;
- aggregate remainder fallback;
- multiple invoices and cancellation informational events.

These tests cover the client statement helper, not the separate daily-situation projection. Therefore passing client-account helper tests does not prove daily-situation reconciliation.

### Accounting aggregation tests

`backend/commercial/tests/test_accounting_aggregation.py` covers:
- Decimal conversion in aggregation pipeline;
- source filters before grouping;
- Tunis business timezone;
- explicit business date handling;
- millime precision in a single event helper;
- Decimal parsing behavior.

The inspected file does not exercise the full daily-situation route against a dataset containing invoices, payment arrays, history deltas, purchase documents, settlement documents, reversals, passive income and expenses.

### GS payment and stock integration tests

The repository includes focused tests for:
- immutable commercial payment reversals and invoice balance updates;
- payment reversal idempotency/concurrency;
- transaction rollback;
- purchase approval and stock receipt;
- production olive consumption and oil receipt;
- sale dispatch and payment flows;
- sale return, credit note and buyer credit.

These are valuable source-workflow tests, but they do not yet establish a complete accounting reconciliation from all source events to accrual P&L, receivables/payables, cash/bank and inventory valuation.

## 3. Required accounting regression suite

Add tests at the pure projection/service layer first, then a small route integration suite. The test matrix must include:

| Scenario | Required assertion |
|---|---|
| Traditional incremental receipt | A TND 50.000 payment produces exactly one TND 50.000 receipt in daily-situation; paid snapshot and balance reconcile. |
| Itemized + history overlap | Same receipt represented in both legacy fields is counted once, not twice. |
| Legacy aggregate only | Legacy `paid_amount` without itemized event is marked `UNALLOCATED_LEGACY`; it is not counted as an authoritative cash receipt. |
| Itemized partial receipts | Multiple partial receipts each appear once on their own payment dates. |
| History-only legacy invoice | Positive history deltas are retained as audit evidence and flagged `LEGACY_UNRESOLVED`; they are not promoted to cash receipts without itemized payment evidence. |
| GS PAY + REV | Cash receipt and reversal reconcile to net paid balance without mutating the original payment. |
| Supplier purchase + payments | Inventory acquisition, payable balance and disbursement are separate; purchase is not automatically period P&L expense. |
| Customer-to-mill purchase | Ownership acquisition is recognized once; existing custody stock is not physically received twice. |
| Manual expense unpaid/part-paid | Accrual obligation and later settlement dates are independent. |
| Passive income uncollected/part-collected | Revenue recognition and later receipts are separate events. |
| Inventory costing | Olive cost moves through production into oil/by-product valuation; sale relieves COGS once. |
| Return/credit note | Revenue credit, receivable adjustment, stock return and cost restoration reconcile separately. |
| Treasury | Cash/bank account movement matches canonical payment IDs and bank statement lines. |
| Tax | Applied tax rule/version and authorization scope are preserved on invoice and credit note. |
| Fiscal periods | Posting period is determined by configured fiscal year, not active olive season. |

## 4. Test execution and CI evidence

This document records source-level test coverage only. It does not claim that tests pass.

The latest previously inspected GitHub Actions run in the audit record had jobs with no assigned runner, no steps and no logs. That is an infrastructure/no-execution result, not a passing or failing code assertion. Do not merge runtime accounting changes on the assumption that an unexecuted workflow passed.

Before any runtime financial fix is merged:
1. Run backend unit tests for affected modules.
2. Run MongoDB replica-set integration tests for transactions, concurrency and idempotency.
3. Run frontend typecheck/build.
4. Add a report-level regression test for the exact defect being fixed.
5. Run end-to-end smoke tests against a controlled environment and verify the production database was not modified.
6. Capture CI run IDs and successful job logs as evidence.

## 5. Non-negotiable testing principle

A green unit test for invoice balance is not proof of a correct cash report. A green stock quantity test is not proof of monetary inventory valuation. A green payment reversal test is not proof of bank reconciliation. Each accounting projection must reconcile its own source-event identities and balances.
