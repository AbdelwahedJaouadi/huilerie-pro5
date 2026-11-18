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


## E. Quantity lineage: traditional loads → invoices and GS stock → production

This section records the currently observed source-of-truth boundaries. It does not change runtime behavior.

| Business path | Authoritative source quantity | Derived/copied quantity | Downstream use | Invariant / gap |
|---|---|---|---|---|
| Traditional customer load | `loads.olive_kg` (currently accepted as a float by `LoadCreate`) | Load response exposes `olive_kg`; available customer quantity defaults to it unless ownership/custody fields override it | Load list, load display, customer account and GS direct-purchase eligibility | This is the current net-like olive quantity. Gross and tare are not persisted separately yet. |
| Traditional pressing completion | Same source load; `loads.oil_kg` is entered separately by the operator | Yield is calculated as `oil_kg / olive_kg × 100` | Completion status, yield display, invoice eligibility | Traditional pressing does not create a GS production run or consume a GS olive-stock lot. |
| Traditional invoice | Source `loads.oil_kg` and current app setting `price_per_kg` | Invoice snapshots `olive_kg`, `oil_kg`, tariff, total and balance | Invoice PDF/list, payment history, accounting overview | The billed service quantity is oil kg, not olive kg: `total = oil_kg × price_per_kg`. Olive kg is retained as supporting traceability/context. The invoice is created transactionally with the load completion path. |
| GS direct purchase of a traditional customer load | Source `loads.olive_kg` | Converted with `Decimal(str(value))` when needed, then passed to the custody receipt and ownership-transfer stock movement | Customer custody receipt, olive lot, stock ledger and later production | The source load is closed/cancelled as sold and marked ownership-transferred in the same transaction. The stock quantity comes from the original load quantity; it is not re-weighed in this endpoint. |
| GS supplier olive reception | Command line `quantity_kg` values (Decimal, 3 decimal places) | Purchase lines and approved receipt/olive lot quantities are derived from those lines | Supplier purchase, traceability batch, stock receipt, available olive stock | There is no gross/tare vehicle weighing snapshot in this command yet. The sum of variety lines is currently the declared received quantity; it is not reconciled against a separately captured vehicle net weight. |
| GS production | Each `CommercialProductionDraft.inputs[].quantity_kg` (Decimal) for identified olive lots | `total_olive_input_kg` is the sum of input lines; stock consumption movements use those same line quantities | Production run, olive stock consumption, actual oil output, output oil lot and tank receipt | Production is entered against GS lot balances, not by reading `loads.olive_kg` at production time. Stock movements are the quantity-control boundary. The production schema rejects output greater than input, but does not enforce a business yield range. |

### Findings and design consequences

1. **There are two separate production domains.** Traditional pressing records a load-level oil output on `loads.oil_kg`; GS production consumes commercial olive lots and posts stock ledger movements. Do not silently treat the traditional load completion endpoint as a GS production posting.
2. **The future weighbridge net must become the canonical intake quantity.** For new measured loads, calculate `net_weight = gross_weight - tare_weight` on the server using decimal-safe arithmetic. The compatibility field `loads.olive_kg` must equal that validated net quantity until all legacy consumers have been migrated. Never feed gross weight into inventory, production input, customer billing context or GS purchase quantity.
3. **The direct customer-load purchase is a conversion boundary.** It currently reads a legacy float `olive_kg`, converts via `Decimal(str(...))`, and persists commercial stock quantities as Decimal128. This avoids importing the float's binary representation directly, but it cannot recover precision already lost at the traditional load API/storage boundary. A future migration must preserve the original legacy value and explicitly classify historical records as net-only/unknown-gross-and-tare.
4. **Supplier reception needs a reconciliation gate.** When vehicle weighing is introduced, the sum of variety-line quantities must equal the validated vehicle net quantity before purchase posting and stock receipt. A mismatch must block posting and require correction with audit evidence; do not silently scale or redistribute variety lines.
5. **Production must consume only available lot quantities.** Each input line remains tied to a lot, source location and owner. The posted consumption movement is the inventory decrement; `total_olive_input_kg` is the sum of those lines, not a second independent stock quantity.
6. **Traditional invoice pricing is based on oil output.** The tariff basis must remain explicit and versioned/configurable. The current source code uses oil kg × the current app tariff and stores a snapshot on the invoice. Any future change to tariff basis must be a deliberate business decision and must not recalculate historical invoices silently.
7. **Precision is not yet end-to-end uniform.** Traditional load intake and oil output use float-facing schemas/fields; GS command quantities use Decimal and stock documents use Decimal128. Traditional invoice code converts oil kg to float before multiplying by a Decimal tariff. Before enabling precision-critical weighing, define one canonical decimal scale/unit and audit every conversion and response serialization boundary.

### Required acceptance tests before activating gross/tare

- Given gross 12,450.000 kg and tare 4,250.000 kg, server-calculated net is exactly 8,200.000 kg.
- The persisted canonical net and compatibility `loads.olive_kg` both equal 8,200.000 kg; a client-supplied conflicting net is rejected or ignored according to the final API contract.
- The load UI/API, traditional pressing yield denominator and invoice traceability snapshot all use 8,200.000 kg as the olive quantity; gross and tare never substitute for net.
- A GS direct purchase from that load creates exactly 8,200.000 kg of olive stock and a matching ownership-transfer movement; it does not create more than one receipt on a retry.
- A supplier reception with variety-line sum 8,199.000 kg against vehicle net 8,200.000 kg is rejected before stock posting; an exact 8,200.000 kg sum is accepted.
- GS production consumes only the explicitly selected lot quantities; the sum of consumption movements equals `total_olive_input_kg`, and no input quantity exceeds the available lot balance.
- A traditional invoice uses the persisted oil output quantity for its tariff calculation, while preserving the source net olive quantity as context; no invoice total is derived from gross weight.
- Legacy loads containing only `olive_kg` remain readable and are explicitly classified as historical net-only records; gross/tare are not fabricated.
- Repeated create/submit attempts for the same logical traditional load cannot create duplicate loads once the intake idempotency contract is implemented.
