# Full Accounting Gap Analysis (Initial Audit)

## Executive finding

The existing `Comptabilite` module is an operational financial dashboard, not full general-ledger accounting. It consolidates source-document totals and a daily cash/accrual-style event report. No chart-of-accounts, journal-entry, general-ledger, trial-balance, balance-sheet, period-close or tax-ledger API was found in the inspected `backend/routers/accounting.py`.

## What exists today

- `GET /api/accounting/overview`: aggregates traditional invoices and GS commercial source documents for the active season.
- `GET /api/accounting/daily-situation`: builds daily/period reporting events from invoices, purchases, payments, reversals, passive income and expenses.
- Passive income records: list/create/delete.
- Expense records: list/create/delete.
- Frontend `/comptabilite`: overview and daily-situation tabs, summary cards, source-document tables and simple income/expense entry.
- Commercial workflows already retain source documents, payment records, credit notes, reversals and customer/supplier balances.

All inspected accounting endpoints depend on `require_admin`. This does not yet match the intended role-based access model for all staff (accountant, cashier, manager, read-only roles).

## Live database observation

In the inspected Atlas database `huilerie-pro3`, neither `accounting_expenses` nor `accounting_passive_incomes` existed in the collection listing; both returned zero documents. This means the simple expense/passive-income entry module appears unused in that database, or the inspected database is not the active database for pro5. The Render backend's actual `DB_NAME` remains unverified.

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
11. **Audit and corrections:** passive income and expense endpoints physically delete records; posted accounting records must instead be corrected by reversal/adjustment with full history.
12. **Cost accounting:** no integrated cost-centre, production-cost allocation or finished-goods valuation ledger was found in the inspected accounting module.

## Important current behavior to preserve but redesign

- Money calculations in the accounting overview use Decimal/Decimal128-oriented helpers in key aggregation paths.
- Traditional and commercial financial documents have separate source collections.
- The current summary is scoped to the active olive season. Full accounting must support fiscal years and arbitrary accounting periods independently of the olive season.
- The frontend contains an explicit cash-basis comment for collected revenue. Full accrual accounting must distinguish invoice revenue, cash receipts, payables, expenses and stock valuation rather than mixing them into one total.
- The frontend declares an `AccountingInvestment` type, but no corresponding investment API route was found in the inspected accounting backend.

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
