# Physical Cash Count Evidence — Phase 14

## Scope
Record an administrator's physical denomination count for an active TND cash account. This is immutable operational evidence, not a cash ledger, balance calculation, or accounting adjustment.

## Supported TND denominations
The count accepts integer quantities for:
- Notes: 50, 20, 10, 5, 2 and 1 TND
- Coins: 0.500, 0.200, 0.100, 0.050, 0.020, 0.010 and 0.005 TND

The total is calculated in integer millimes and stored as Decimal128. Quantities must be whole non-negative integers, with a bounded maximum per denomination. A zero-cash count is valid when at least one denomination is explicitly entered as zero.

## API
- `POST /accounting/treasury/cash-counts` — admin-only, immutable evidence creation.
- `GET /accounting/treasury/cash-counts` — admin-only, active-season scoped, filtered and paginated read-only register.

The write requires an active TND CASH account, ISO count date, denomination quantities, notes, and a UUID request ID. Request identity is unique per active season; retries with the same identity and same evidence return the original record, while reusing the identity for different evidence is rejected.

A transaction inserts both the cash-count evidence record and its audit event. No update or delete route is exposed.

## Explicit non-features
- No expected cash amount, opening float, running balance, or variance is calculated.
- No treasury movement, adjustment, income, expense, or GL entry is created.
- No bank account may be selected for physical cash counting.
- No user/custodian identity is inferred; the authenticated administrator is recorded as the actor.

## Why variance is deferred
The application has not yet established verified opening balances and complete cash movement coverage. Calculating expected cash now would produce an unreliable variance. This phase therefore preserves the physical evidence only. A later phase can introduce opening balance evidence, cashier handover, independent review, and variance approval after the operating rules are agreed.
