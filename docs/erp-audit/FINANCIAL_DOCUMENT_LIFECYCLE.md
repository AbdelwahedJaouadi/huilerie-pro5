# Financial Document Lifecycle Review

Audit branch: `audit/erp-foundation`  
Date: 17 Nov 2026  
Scope: static source inspection and targeted unit-test additions. No production database or Render service was changed.

## Verified traditional invoice behavior

The traditional invoice endpoint currently supports:
- Creation from a completed, non-cancelled load.
- A single invoice per source load.
- An initial payment snapshot stored in both `paid_amount` and the embedded `payments` array.
- Administrator edits to the tariff and/or additional payment amount.
- Physical invoice deletion through `DELETE /invoices/{invoice_id}`.

The invoice update endpoint writes a new `paid_amount` and `balance`, and adds a generic before/after history entry. The accounting daily-situation report, however, derives payment events from the invoice's `payments` array when that array is non-empty.

### Confirmed defect and branch fix

Before this audit update, an incremental payment sent as `payment_amount` increased `paid_amount` but did not append a corresponding item to `payments`. For invoices that already had an initial payment, the daily-situation report therefore omitted the later receipt because it preferred the non-empty event array over the aggregate `paid_amount`.

On `audit/erp-foundation`:
- The invoice update now appends `{at, by, amount}` to `payments` whenever `payment_amount > 0`.
- The invoice balance update, payment event, history event and audit event remain in the same MongoDB transaction.
- A targeted unit test asserts that the payment total, balance and embedded payment ledger advance together.

**Validation status:** the regression test has been added but has not yet executed. GitHub Actions previously failed before runner allocation (`runner_id=0`, no steps), so this is a source change with an unverified test, not a validated release.

## Remaining financial controls — do not change without an approved policy

1. **Invoice repricing after issuance:** `PATCH /invoices/{id}` can change `price_per_kg` and recalculate the total of an existing invoice, including one with receipts. The current generic history/audit event is not a substitute for a formal credit/debit note or invoice correction document.
2. **Invoice deletion:** `DELETE /invoices/{id}` physically removes the invoice and leaves only a partial audit snapshot. Posted financial documents should be preserved and corrected by linked reversal/credit/debit documents. Whether an unposted draft can be deleted requires an explicit document-state policy.
3. **Legacy `paid_amount` replacement input:** the endpoint still accepts `paid_amount` as a replacement value for compatibility. Unlike `payment_amount`, this does not inherently identify a new receipt event or its effective date. It must be retired or given a formally defined adjustment/reversal behavior before the system becomes the authoritative ledger.
4. **Passive incomes and expenses:** their DELETE endpoints physically remove records. Replace with cancellation/reversal and preserve the original document once a posting/approval lifecycle is designed.
5. **Payment metadata:** the current traditional invoice receipt shape does not capture payment method, cash/bank account, external reference, or receipt number. Those are required design inputs for a reliable cash/bank subledger; do not fabricate them from existing records.

## Required accounting design decisions

Before implementing the general ledger or financial correction workflows, obtain approval for:
- Legal entity jurisdiction and applicable accounting/tax framework.
- Fiscal year and period-close rules (separate from olive season).
- Invoice lifecycle states: draft, issued/posted, voided, corrected.
- Whether tariff changes after issuance are allowed, and which corrective document is required.
- Receipt methods, cash drawers/bank accounts, payment references and receipt numbering.
- Reversal permissions, approval thresholds and audit retention.
- Opening balances and treatment of historical documents.

## Release boundary

- No invoice, income, expense or payment record was changed in MongoDB.
- No live API behavior was deployed.
- The payment-event synchronization fix is isolated to the audit branch.
- Do not merge or deploy until the test suite, frontend checks and affected workflow regression tests have actually run successfully.
