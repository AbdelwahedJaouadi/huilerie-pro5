# Vehicle Weighing Evidence and Future Weighbridge Integration Contract

Project: Oro Verde / huilerie-pro5  
Scope: vehicle olive reception and quantity lineage across traditional intake and GS  
Status: design specification only; no runtime schema/API/UI or device integration implemented  
Date: 18 Nov 2026

## 1. Source-code baseline

A current-main source review confirms two separate vehicle-reception paths:

### Traditional customer load — POST /loads
- backend/models/schemas.py::LoadCreate accepts olive_kg: float.
- backend/routers/loads.py::create_load stores this value as loads.olive_kg.
- No gross weight, tare weight, separate weighing timestamps, weighing source or scale identity is captured.
- Downstream traditional invoices, production/yield views and GS direct purchase of an existing load rely on this olive_kg value.

### GS supplier olive reception — POST /commercial/v1/olive-receptions
- OliveReceptionPurchaseCommand accepts supplier/date, variety lines, receiving location, notes and idempotency key.
- Each line stores quantity_kg and unit price in millimes.
- No vehicle gross/tare readings or weighing evidence is present in the command.
- The route creates the purchase, lots and stock receipt atomically. The owner has explicitly required direct employee registration without a human approval queue.

### GS direct purchase of an existing customer load
- POST /commercial/v1/customer-purchases/loads reads the existing loads.olive_kg value.
- It transfers ownership of the already-recorded quantity; it must not weigh the same vehicle/load a second time.

These paths must not be conflated. A supplier reception is a new purchase/reception. A customer load is an existing traditional intake. A GS direct customer-load purchase changes ownership of an existing net quantity.

## 2. Canonical weighing model

Use a reusable vehicle-weighing evidence object linked to the source reception/load. Logical model:

| Field | Meaning |
|---|---|
| weighing_id | Immutable ID for one weighing pair/record |
| gross_weight | Decimal gross vehicle weight, including load |
| tare_weight | Decimal empty-vehicle weight |
| net_weight | Server-derived gross minus tare |
| weight_unit | Explicit unit; kg initially |
| weighing_source | MANUAL or SCALE |
| gross_measured_at | Timestamp of gross reading |
| gross_recorded_by | Authenticated employee who captured gross |
| tare_measured_at | Timestamp of tare reading |
| tare_recorded_by | Authenticated employee who captured tare |
| scale_device_id | Optional future scale identity |
| scale_ticket_reference | Optional device ticket/sequence reference |
| raw_scale_payload_hash | Optional integrity reference for future device capture |
| created_at / created_by | Server recording metadata |
| correction_of / correction_reason | Link and reason for a later correction |

Persist weights as Decimal128 or an equivalently exact Decimal representation. Do not use binary float for weight arithmetic or monetary calculations derived from weight.

### Net-weight rule

net_weight = gross_weight - tare_weight

- The server calculates net from gross and tare.
- The client may display the computed net immediately, but a submitted client net is never authoritative.
- If the UI shows a net field, it is a read-only computed result, not a third independent input that can disagree with gross/tare.
- Gross and tare must both be present before the reception quantity can be finalized and stock posted.
- Require gross > tare > 0, subject to a separately configured tare policy if empty vehicle readings can legitimately be zero.
- Reject negative values, unsupported precision, non-finite values, implausible ordering and mismatched units.
- Preserve raw exact decimal values; formatting and rounding are presentation-only.

## 3. Capture lifecycle without human approval

The owner's direct-entry instruction is explicit: the designated employee registers the olive purchase and weighing data without sending the transaction to a human reviewer.

This does not mean incomplete measurement data can be treated as a finalized quantity. Separate the operational weighing lifecycle from a human approval lifecycle:

1. Gross captured: record the loaded vehicle reading, actor, source and timestamp.
2. Tare captured: after unloading, record the empty vehicle reading, actor, source and timestamp.
3. Net derived: server computes net and validates the pair.
4. Reception finalized: supplier lines reconcile to net, and purchase + traceability lot(s) + stock receipt + audit evidence commit atomically.
5. Correction: if a finalized reading is wrong, create a linked correction event with old/new values, actor, time and mandatory reason. Never silently overwrite a posted weighing or stock quantity.

A reception waiting for tare is an incomplete operational measurement, not a pending human approval. It must not create a finalized stock quantity or payable/inventory valuation based on an unknown net. The interface should make this state explicit and allow the designated operator to complete the tare capture.

If the actual mill process weighs the empty vehicle before it is loaded, the same evidence model can capture tare first and gross later; the two measurements remain separately timestamped. Do not require a specific order beyond both readings being valid before finalization.

## 4. Reconciliation with variety lines and stock

For GS supplier reception:
- sum(lines[].quantity_kg) = computed net_weight exactly at the supported 0.001 kg precision.
- Each line must reference a registered olive variety.
- No stock receipt, lot quantity or purchase total is posted if the line sum differs from net.
- Purchase line prices are monetary data; compute line totals with Decimal and preserve TND/millime precision separately from kg precision.
- The total stock receipt quantity must equal net, grouped by product, owner and receiving location.
- Purchase, weighing evidence, lot creation, stock movement and audit event remain one transaction.

For traditional customer loads:
- The canonical loads.olive_kg compatibility field must represent net weight only.
- New records should preserve gross/tare/net evidence in the source load record or a linked immutable weighing record.
- Traditional pressing yield, invoice quantity basis, client statements and GS ownership transfer must continue to consume net only.
- During a staged migration, old clients may still send net-only records until the UI/API upgrade is released. Mark them LEGACY_NET_ONLY; do not fabricate gross/tare.
- Do not reinterpret bags, packaging, trailer or vehicle tare as olive quantity.

For GS direct purchase of an existing customer load:
- Read the existing loads.olive_kg net quantity.
- Carry forward a reference to the source load's weighing evidence when available.
- Do not capture a second gross/tare pair or create a second physical receipt.
- Ownership transfer changes the owner ledger; it does not increase physical stock quantity.

## 5. Future electronic weighbridge adapter

The first implementation should be manual-first and independent of a specific scale manufacturer. Device integration is a later adapter, not a change to the canonical weighing model.

A future adapter must establish:
- scale manufacturer/model and supported interface (serial, network, USB, vendor API or file export);
- stable device ID and device configuration;
- protocol, framing, encoding, units, stability indicator and error handling;
- reading sequence/ticket identity and device timestamp;
- calibration/verification status and validity evidence;
- operator identity and application capture timestamp;
- duplicate/replay protection for device ticket IDs;
- integrity validation between raw reading, parsed value and persisted Decimal value;
- offline buffering and safe retry behavior if the local network is unavailable.

Do not claim scale integration until a physical device has been selected, its protocol documented and real readings tested end-to-end. Do not infer calibration from the presence of a device ID.

The adapter must not be allowed to write a different net quantity from the canonical server formula. If the device provides only a gross/tare/net print ticket, preserve the raw ticket evidence and independently verify the net equation before accepting the record.

## 6. Offline and synchronization considerations

The mill may later operate a local Windows server with worker phones while internet connectivity is unavailable. The weighing contract must therefore:
- assign a stable client-generated operation ID before synchronization;
- use server-side idempotency on upload;
- preserve the original local capture timestamps and actor/device identity;
- store server receipt/synchronization timestamps separately;
- reject same operation ID with a changed weighing payload;
- return the already-created reception for an identical retry;
- avoid issuing a second lot, purchase or stock receipt after reconnect;
- retain scale ticket IDs to prevent importing the same physical reading twice.

Local clock time is evidence but not sufficient alone for global ordering. Use server timestamps when synchronized and preserve source timestamps without overwriting them.

## 7. Legacy compatibility and rollout

- Historical loads.olive_kg values remain net-only. Do not create estimated gross/tare.
- GS direct purchase of a historical load continues to use the stored net.
- New fields are additive and optional during a controlled rollout; do not make gross/tare mandatory for every old API client in one uncoordinated release.
- Define a versioned API contract and dual-read period before changing frontend forms.
- When the new intake UI is active, require gross and tare for new weighbridge-based receptions and compute net server-side.
- If a controlled manual net-only exception is required, record its reason and source explicitly; do not mix it with verified gross/tare records.
- Reconcile old and new quantities before retiring the legacy olive_kg input path.

## 8. Required test matrix

1. Gross 12,450.000 kg and tare 4,250.000 kg produce net 8,200.000 kg.
2. Client-submitted net that differs from server calculation is ignored/rejected; persisted net is 8,200.000.
3. Gross equals tare, tare exceeds gross, negative values, NaN/infinity and over-precision are rejected.
4. Gross-only reception cannot finalize or post stock; adding tare completes the same reception without human approval.
5. Tare-first then gross capture also works if the actual weighbridge process requires it.
6. Same operation ID and same full payload returns the same result; same ID with changed gross/tare/supplier/variety/location conflicts.
7. Concurrent identical retries create one purchase, one set of lots and one stock receipt.
8. Supplier line quantities must sum exactly to computed net; any mismatch prevents final stock posting.
9. The loads.olive_kg compatibility field equals net, never gross.
10. Traditional pressing yield and invoice calculations continue to use their existing explicitly approved quantity basis; weighing work does not silently change tariff basis.
11. GS direct purchase of an existing customer load uses source net once and creates no second physical receipt.
12. Legacy records remain net-only with gross/tare unknown.
13. Correction produces an immutable linked event and compensating quantity/valuation treatment; no silent overwrite.
14. Scale adapter rejects duplicate ticket IDs and retains raw evidence, source timestamp, device ID and calibration status.
15. Offline retry after reconnect does not duplicate the reception, lot or stock movement.

All tests must execute in a functioning CI environment and include MongoDB transaction/concurrency coverage before runtime release.

## 9. Owner/technical decisions not blocking this design

- Working design target: apply the same reusable gross/tare/net evidence model to both traditional customer-load intake and GS supplier vehicle reception, while keeping their business workflows separate. Confirm this scope before runtime form/API changes; do not silently change either live workflow.
- Select the actual scale manufacturer/model and connection interface later; no device has been selected in this design.
- Define approved operational tolerance, if any, for small discrepancies between supplier line totals and calculated net. Default is exact equality at 0.001 kg; do not invent a tolerance.
- Assign the specific employees/roles allowed to register direct supplier purchases. This is a permission assignment decision; it does not create a human purchase approval queue.

No runtime code, API schema, database records, permissions or Render services are changed by this document.
