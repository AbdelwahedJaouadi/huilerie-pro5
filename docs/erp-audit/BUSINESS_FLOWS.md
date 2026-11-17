# Business Flow Map (Initial Audit)

## A. Traditional mill workflow

Source modules inspected: `loads.py`, `lab.py`, `invoices.py`, `client_accounts.py`.

1. Create a load/reception record.
2. List and search loads; retrieve by code.
3. Record oil quantity and update processing status.
4. Record laboratory analysis linked to a load.
5. Deliver, cancel or delete a load through explicit endpoints.
6. Create an invoice for an eligible completed load.
7. Record invoice payments and update invoice details.
8. Display client account statements using load and invoice history.

### Controls already visible in source

- Traditional invoice collection has unique indexes on invoice ID, invoice number and non-null source load ID.
- Invoice creation uses a MongoDB transaction and checks that the source load is completed and not already invoiced.
- Invoice creation writes a source-load guard version in the same transaction.
- Invoice changes/deletions and load operations have audit-event writes in inspected paths, but coverage and immutability need a complete review.
- Client statements aggregate events from multiple source collections.

## B. GS / commercial workflow

Source module inspected: `backend/commercial/routers.py` and its service/schema modules.

1. Initialize commercial setup, tanks and season counters.
2. Maintain suppliers, buyers, varieties and storage locations.
3. Draft olive purchases and approve/reception-post them.
4. Create pre-production samples and cancel where permitted.
5. Record quality assessments, corrections and independent release/rejection.
6. Complete production runs from eligible olive balances.
7. Create oil lots and post stock ledger movements.
8. Transfer stock between locations/tanks and manage ownership/custody.
9. Create sales, approve/dispatch, issue invoices and record payments.
10. Process payment reversals, sale returns, credit notes and credit applications.
11. View stock balances, movement history, customer statements and audit events.

### GS controls already visible

- Many critical commands run inside MongoDB transactions.
- Idempotency keys are used in important command schemas and guarded by unique indexes.
- Stock ledger is a dedicated service; the API rejects direct arbitrary stock movement creation.
- Quality has release and correction workflows.
- GS has a dedicated audit-events collection with indexes by date, entity, actor and action.
- Commercial permissions are assigned per worker; admin receives the full declared commercial permission set.

## C. Accounting connection today

The current accounting overview reads from source documents such as traditional invoices, GS purchases, supplier payments, sales invoices, customer purchases, payments and credit notes. It aggregates totals for the active season.

The daily situation endpoint builds period events from those source documents, passive income and expense records. The frontend explicitly labels the accounting overview as read-only and includes a cash-basis calculation comment for collected revenue.

This is useful operational reporting, but it is not a posted double-entry accounting system.

## D. Required end-to-end invariants

- One stable traceability code per GS lot from purchase through production, storage and sale.
- Every production output must reconcile to consumed input lots and the resulting stock entry.
- Stock balance must be derivable from posted stock movements.
- No sale/dispatch may exceed available stock.
- Returns and reversals must create traceable compensating documents; never erase the original history.
- Every invoice/payment must be linked to its source document and customer/supplier account.
- Once accounting is introduced, every financially relevant approved source event must post at most once to the general ledger.
- Accounting posting must be atomic with, or reliably recoverable from, the source workflow.
