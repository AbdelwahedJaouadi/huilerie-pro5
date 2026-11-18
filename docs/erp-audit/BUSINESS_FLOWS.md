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

### Future weighbridge requirement — preserve in the data model

Oro Verde must support a future physical vehicle weighbridge. The load/reception workflow must be designed to store, at minimum:

- Gross vehicle/load weight (`poids brut`).
- Tare/empty vehicle weight (`tare` / `poids à vide`).
- Net olive/load weight (`poids net`), calculated as gross minus tare.
- Weight unit, weighing timestamps, and the load/vehicle association.

The first implementation may continue to accept manual readings. The data contract should be ready for a later electronic scale integration without changing the load identity or rewriting historical load records.

For a proper weighbridge audit trail, retain each weighing event as a reading with its timestamp, operator/source (manual or scale), scale/device identifier when available, and any correction reason. Do not silently overwrite a previous reading. The system should validate that gross and tare are non-negative and net is positive; tare must be lower than gross. If a vehicle is weighed in two passes (loaded and empty), preserve both readings and derive net from the matched pair. Do not assume a fixed tare per truck: trailers, vehicles and configurations can change.

When a scale is integrated, the captured stable reading should be linked to the active load and protected against duplicate submission. Manual override remains possible only with a recorded actor, reason and audit event. Calibration and scale verification records should be added as part of the equipment/compliance workflow before treating scale readings as certified measurements.

This is a future requirement, not an instruction to create a new collection or change live load behavior during the current audit.

### Controls already visible in source

- Traditional invoice collection has unique indexes on invoice ID, invoice number and non-null source load ID.
- Invoice creation uses a MongoDB transaction and checks that the source load is completed and not already invoiced.
- Invoice creation writes a source-load guard version in the same transaction.
- Invoice changes/deletions and load operations have audit-event writes in inspected paths, but coverage and immutability need a complete review.
- Client statements aggregate events from multiple source collections.
- A traditional invoice DELETE endpoint physically deletes the invoice and writes an audit event; this preserves evidence of deletion but removes the invoice from the operational source collection. Financial corrections should become void/reversal documents, not hard deletes.
- A load can be physically deleted only when no invoice exists; the deletion also removes its lab records and writes a GS audit event. This path needs policy review for retention and legal traceability.

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
- Commercial permissions are assigned per worker; admin receives the full declared commercial permission set. The assignable worker permission list is narrower than the full admin set, leaving purchase, production, sales-management and other high-impact actions unavailable to ordinary workers unless the policy is deliberately expanded.
- Accounting passive-income and expense records have physical DELETE endpoints; these should be replaced by reversal/void semantics before they are treated as accounting records.

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
- Traditional mill load records must preserve gross, tare and net weight as distinct, auditable measurements, ready for future weighbridge integration.
