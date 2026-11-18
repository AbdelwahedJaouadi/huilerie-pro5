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

## 6. CI execution evidence rechecked (18 Nov 2026)

The recorded GitHub Actions run `44212833785` was inspected again through the job and step endpoints. It contains these jobs:

- `runner-smoke`
- `backend-syntax`
- `mongodb-transaction-integration`
- `frontend-build`
- `commercial-unit-tests`
- `invoice-unit-tests`

All six jobs report `conclusion=failure`, but each has `steps=null` in the job response and the runner-smoke step query returns an empty step list. No job logs are available. Therefore this run proves neither a code failure nor a successful test execution; it is an infrastructure/no-execution result.

The latest inspected `main` commit at this audit point (`85e9e896f10f5c840c903f113983ff69dfa669b6`) has no associated workflow runs and no combined status checks. Do not describe the current branch as CI-green.

**Required next CI action:** identify and repair the runner/workflow trigger configuration so a new pull-request commit receives an assigned runner and actual steps/logs. Then require successful backend syntax, invoice/commercial unit tests, MongoDB transaction integration and frontend build/typecheck before any runtime accounting fix is merged. Do not rerun the historical run as a substitute for validating the current source commit.

## 7. Runner provisioning diagnosis (18 Nov 2026, second attempt)

A second direct inspection was performed on PR validation run `44218616527` (attempt 1), then the failed jobs were re-run using GitHub's retry operation (attempt 2).

Observed attempt 2:
- All six jobs were created and immediately completed as `failure` within approximately 2–3 seconds.
- Every job reports `runner_id=0`, empty `runner_name`, and empty `steps[]`.
- The `runner-smoke` job itself did not execute, so this is not a Python setup, dependency installation, test assertion, Docker or MongoDB failure.
- Downloading the job logs returns `BlobNotFound`; no runner logs exist for this attempt.
- The workflow YAML is present at `.github/workflows/validate-factures.yml`, includes `pull_request: branches: [main]`, `workflow_dispatch`, and jobs using `ubuntu-latest`. The workflow was therefore discovered and expanded into six jobs.

**Diagnosis boundary:** the evidence localizes the failure before runner assignment/execution. It does not identify whether the underlying GitHub-side cause is Actions availability/billing policy, hosted-runner provisioning, or repository/account policy. The available repository connection cannot read the Actions settings/billing endpoints, so none of those causes is asserted as fact.

**Action taken:** retried the failed jobs once. The retry reproduced the same runner-allocation failure. Do not keep retrying identical runs or change application code/workflow steps to compensate for a failure that occurs before any step starts.

**Required owner-side check:** in GitHub repository `Settings → Actions → General`, verify that Actions are enabled and permitted for the repository; then inspect the account's Actions billing/usage and GitHub Actions service notices. If Actions are enabled and within quota, contact GitHub Support with run `44218616527`, attempt 2, and the six job IDs; include the fact that each job has `runner_id=0`, no steps, and no logs.

Until a hosted runner actually starts the smoke step and returns a runner ID, all backend, MongoDB integration and frontend test results remain **not executed**.

## 8. Endpoint defect verified against current source (18 Nov 2026)

The current write/read path is now traced end-to-end:
- `PATCH /invoices/{invoice_id}` appends a payment child when `payment_amount > 0` and also appends an `updated` history event containing the same before/after paid-amount delta.
- `GET /accounting/daily-situation` loops over `payments[]` and then independently loops over positive `history[]` paid deltas, adding both to receipt events and `known_paid`.

Therefore a single new TND 100.000 payment can produce TND 200.000 in the endpoint's receipt total. The endpoint's `unallocated_legacy_receipts` clamps negative remainder to zero and does not expose this overcount as a reconciliation difference.

The report also:
- classifies supplier and customer-to-mill acquisitions as expenses before any inventory consumption/COGS valuation;
- projects manual income/expense as same-day accrual plus same-day receipt/disbursement;
- omits GS credit notes and sale-return records from its source query.

The detailed source findings and correction contract are in `DAILY_SITUATION_RECONCILIATION_FINDINGS.md`. Runtime code has not been changed because CI still does not assign runners and endpoint-level tests cannot currently be executed.
