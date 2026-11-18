# Cash and Bank Ledger Audit

Project: huilerie-pro5  
Base: main at `36b8d54c827e228f9ce308a87975ffb064e43da7`  
Method: static inspection of traditional invoice receipts, GS payment schemas/services, reversals, accounting reports and repository source tree. No live payment or bank data changed.

## 1. Executive finding

The application records payment amounts, dates, methods and (for selected GS payment types) references. It does not currently provide a full cashbook/bank ledger with named cash drawers and bank accounts, account-level balances, bank reconciliation, cheque lifecycle, cash counts, statement import or transfer controls.

A payment method is not a cash/bank account. A reference string is not a bank statement reconciliation.

## 2. Current payment evidence

### Traditional pressing invoices

- Initial invoice receipt is embedded in `invoices.payments[]` with timestamp, actor username and amount.
- Incremental `payment_amount` appends another embedded payment item.
- The inspected traditional payment event does not capture a payment method, cash drawer, bank account, cheque number, bank transaction reference or settlement status.
- The compatibility `paid_amount` aggregate can be updated independently of an itemized payment event; this is already documented as a source-of-truth/idempotency risk.

### GS wholesale sale receipts

`SalePaymentDraft` records payment date, amount, method (`CASH`, `BANK_TRANSFER`, `CHEQUE`), optional reference and notes. A reference is required for bank transfer and cheque. The payment document is immutable and idempotent, and invoice receivable snapshots reconcile to PAY/REV ledgers.

However, the inspected schema does not identify a specific cash drawer, bank account, cheque book, deposit account or bank transaction. It does not record bank value date, cleared/pending status, cheque deposit/clearance lifecycle, fees or matched statement-line ID.

### Supplier and customer purchase settlements

Supplier olive purchase payments and customer-to-mill oil/olive purchase payments store date, amount, method and reference. They reconcile against payable snapshots and payment documents. They do not identify the actual cash/bank account used or provide account-level cash/bank balances.

### Reversals

Commercial payment reversals link to the original payment and preserve evidence reference, original method and amount. This is a useful source-document control, but the inspected reversal record is not a bank/cash movement against a specific account and does not prove that the external bank transfer or cheque has actually been reversed/cleared.

## 3. Missing treasury capabilities

No dedicated cash/bank/account module or route was found in the inspected repository tree for:
- cash drawers / tills by location or custodian;
- company bank accounts, account identifiers and opening balances;
- cash receipt/disbursement journal by account;
- transfers between cash and bank accounts;
- daily cash opening/closing counts and over/short reconciliation;
- bank statement upload/import and statement-line matching;
- bank reconciliation periods and unreconciled-item ageing;
- cheque issue, receipt, deposit, maturity, clearance, rejection and replacement lifecycle;
- bank fees, interest and direct-debit transactions;
- payment approvals and dual authorization tied to bank mandates;
- account-level permissions and audit history.

## 4. Target design

Keep each operational payment document as the source event for settlement against a receivable/payable. Add a treasury ledger that records the actual movement of money.

Minimum structures:
- **Cash/bank account:** type, currency, institution, masked account identifier, owner, opening balance/date, active status, authorized users and reconciliation settings.
- **Treasury transaction:** stable ID, source payment/reversal, account ID, direction, amount, currency, transaction date, value date, method, external reference, status, actor and idempotency identity.
- **Internal transfer:** paired debit/credit movements between two company accounts, with no revenue/expense effect.
- **Bank statement line:** imported statement ID, account, booking/value dates, amount, direction, bank reference, raw source evidence and matching status.
- **Reconciliation:** statement period, opening/closing balances, matched transactions, outstanding items, adjustments, preparer/reviewer and lock status.
- **Cash count:** drawer/custodian, opening float, expected cash, counted cash, variance, reason, actor and reviewer.
- **Cheque register:** cheque ID/number, issuer/drawer, payee, amount, issue/deposit/maturity/clearance dates, bank account, status and linked payment/reversal.

The treasury ledger must not create a second receivable/payable settlement. It records the cash/bank side of the same canonical payment event and reconciles to the payment subledger and future GL.

## 5. Important design controls

- Distinguish payment initiation, payment document recording, bank value date and actual clearance.
- A bank transfer marked as a payment is not proof it has cleared; status and evidence must be explicit where operationally required.
- Cash transactions must identify the responsible drawer/custodian.
- Internal cash-to-bank transfers are balance-sheet movements, not income or expense.
- A reversal of an internal payment document must not be assumed to have reversed the external bank movement; link the actual refund/return transaction.
- Prevent overpayment and duplicate settlement with stable payment IDs, idempotency and atomic invoice/payable updates.
- Require maker/checker or dual authorization for sensitive treasury actions according to approved roles and bank mandate.
- Bank reconciliation must match statement lines to existing source events; it must not fabricate revenue/expense to force a balance.
- Preserve all historical payment methods/references when migrating legacy records; classify missing account identity as `UNALLOCATED_LEGACY`, never guess the bank/cash account.

## 6. Acceptance tests before treasury go-live

1. Cash receipt against a sale invoice increments the selected drawer and reduces the receivable exactly once.
2. Bank transfer against a supplier payable increments the correct bank account movement and reduces payable exactly once.
3. Partial payments across multiple accounts reconcile to the invoice/purchase payment subledger.
4. Internal cash-to-bank transfer creates paired movements and no P&L impact.
5. Bank statement import matches, partially matches, leaves unmatched and flags duplicate statement lines without creating duplicate receipts.
6. Cheque received, deposited, cleared, rejected and replaced transitions reconcile to bank statements and customer receivable.
7. Payment reversal links to original settlement and records actual external refund/return separately.
8. Cash count identifies over/short variance and requires reason/approval.
9. Opening balances, statement closing balances and outstanding items reconcile at period end.
10. All transactions are TND Decimal, idempotent, auditable and tied to the correct fiscal period.

## 7. Boundaries

This is a static source audit. It does not verify any live bank account, payment balance or cash drawer. No account, payment, invoice or production record was changed. Treasury implementation requires approved bank/cash account structure, opening balances, user permissions and operating procedures.
