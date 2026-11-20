# Treasury Movement Recording — Phase 11

Status: implementation proposal, subject to CI and deployment validation.

## Scope

The operational treasury register records the cash/bank side of an already-recorded GS payment only after an administrator explicitly confirms that individual source payment in the UI.

Supported source events:
- GS_SALE_PAYMENT: incoming receipt against an existing GS sales invoice.
- GS_SUPPLIER_PAYMENT: outgoing settlement against an approved olive purchase.

The canonical payment and invoice/payable subledger remain the source of truth for settlement. This movement register is a linked operational record, not a second payment, expense, receipt, revenue, or GL posting.

## Safety controls

- Admin-only endpoint; explicit confirmation required in the client and confirm: true required by the API.
- MongoDB transaction inserts the movement and immutable audit event together.
- Deterministic movement/event IDs plus unique (source_type, source_id) index make retries idempotent.
- The source payment, invoice, supplier purchase and active TND treasury account are re-read inside the transaction.
- The same reconciliation composer used by the preview blocks missing/mismatched invoices or purchases, inactive/unknown/wrong-type/non-TND accounts, unallocated payments, invalid dates, unsupported methods and invalid amounts.
- A supplier movement is allowed only when its source olive purchase is approved and supplier identity matches.
- A sale movement is allowed only when its invoice exists and sale identity matches.
- CASH is recorded as CASH_RECORDED; BANK_TRANSFER remains PENDING_BANK_CONFIRMATION; CHEQUE remains PENDING_CHEQUE_CLEARANCE.
- No opening balance, account balance, running balance, cash count or bank reconciliation is calculated.
- No invoice, receivable, payable, source payment, stock or GL document is changed.
- No bank transfer is initiated; no reversal, refund, or cheque clearance is inferred.
- TND Decimal128 only.

## Explicitly deferred

- Opening balances (require accountant-verified, owner-approved evidence).
- Bank statement import and reconciliation.
- Cash counts, custodian close-outs and over/short adjustments.
- Internal account transfers.
- Manual non-source movements.
- External refund/reversal evidence and cheque lifecycle.
- General-ledger posting, tax recognition and financial statements.
- Maker/checker approval matrix beyond the admin authorization of this recording action.

## Operational interpretation

A recorded movement is not automatically a reconciled or cleared bank transaction. The status is an evidence state, not a computed account balance. The register must not be used as a bank statement or statutory cash/bank balance until opening balances and reconciliation controls are separately implemented and approved.
