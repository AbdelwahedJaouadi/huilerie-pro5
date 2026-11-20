# Treasury Movement Register — Phase 12

## Scope
Add a read-only register for movements already explicitly recorded from canonical GS sale receipts and approved supplier payments.

The register is restricted to the active season and supports filters by:
- treasury account
- inflow / outflow direction
- settlement evidence state
- inclusive movement-date range
- bounded pagination (50 rows per page in the UI; API limit 1–200 and offset capped at 50,000)

## Safety
- Admin-only API access.
- No create, update, delete, reversal, clearance, or reconciliation actions are exposed by this register.
- No sums are presented as account balances.
- No opening balance, running balance, or closing balance is calculated.
- Bank transfers and cheques remain pending until separate evidence-backed settlement workflows exist.
- The register reads only persisted operational movements; it does not infer new movements from source payments.
- Currency remains TND and amounts are read as Decimal128-safe values.

## API
GET /accounting/treasury/movements

Returns rows, total_count, limit, offset, active season, and explicit flags:
- read_only: true
- balances_calculated: false

Filters are validated before constructing the MongoDB query. Every query is scoped to the active season. Date bounds are ISO YYYY-MM-DD and inclusive.

## Deferred
- All-season reporting and archival navigation.
- Bank statement import and reconciliation.
- Cash count and custodian close-out.
- Opening balances and calculated balances.
- Settlement confirmation for transfers and cheques.
- Internal account transfers and manual movements.
- General-ledger posting.
