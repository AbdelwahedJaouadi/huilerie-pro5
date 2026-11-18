# Direct Olive Purchase Registration — Capability and Control Contract

Project: Oro Verde / huilerie-pro5  
Status: proposed permission design; not implemented  
Date: 18 Nov 2026

## 1. Owner instruction

The owner explicitly requires that an authorized employee records the olive purchase and the gross/tare/net measurements directly, without submitting the purchase to a second employee for approval.

This is a direct registration workflow, not a maker/checker approval workflow. A missing tare reading may leave the physical measurement operationally incomplete, but it must never create a pending human approval task or a posted stock quantity based on an unknown net.

## 2. Current source behavior — mismatch

The GS supplier reception endpoint `POST /commercial/v1/olive-receptions` is authenticated but requires `commercial.manage_purchases`.

The same capability is required inside both:
- `create_olive_purchase_draft(...)`
- `approve_olive_purchase(...)`

The current worker-assignable allowlist does not contain `commercial.manage_purchases`. Therefore a normal worker cannot be granted this direct reception path through the current commercial-permission assignment UI. The fact that the route uses `Depends(current_user)` does not make it worker-accessible; the commercial capability check still denies the worker.

This contradicts the intended direct employee-registration workflow for any employee who is expected to perform it.

## 3. Recommended dedicated capability

Introduce one narrowly scoped capability:

`commercial.register_olive_purchase`

It should authorize only the atomic direct-reception command:
- select an existing supplier or create a supplier as part of the same reception;
- enter purchase date, variety lines, quantity/weight evidence and unit prices;
- derive net from gross/tare on the server when weighing is enabled;
- create the purchase and its traceability lot(s);
- post the corresponding physical stock receipt at the configured receiving location;
- write the immutable audit event and idempotency record.

The capability must be explicitly assignable only to designated worker accounts by an administrator. It must not be automatically granted to every worker or inferred from the generic worker role.

Do not grant this capability the following rights:
- edit arbitrary purchase drafts;
- approve separately created purchase drafts;
- change purchase supplier or posted amounts after receipt;
- register supplier payments or reverse them;
- adjust stock balances outside the reception transaction;
- manage tanks/locations or stock transfers;
- create customer sales, record customer receipts or reverse payments;
- post general-ledger journals;
- delete or silently overwrite a posted reception.

Existing administrator `commercial.manage_purchases` remains available for the separate administrative purchase-management functions.

## 4. Service-layer enforcement

A route-only guard change is insufficient. The current purchase-draft and approval service functions independently enforce `commercial.manage_purchases`.

Refactor the direct reception into a dedicated application service/command that enforces `commercial.register_olive_purchase` once at its boundary and then executes the full atomic transaction. Do not globally weaken the existing draft-creation or approval service guards.

The direct service must:
1. Validate the designated worker capability and active user.
2. Validate supplier identity, purchase date/season, varieties, exact Decimal quantities and price precision.
3. Validate complete request idempotency before creating any supplier, lot, code or movement.
4. Require complete gross/tare evidence before final stock posting when the weighing mode is active.
5. Derive net on the server and reconcile the sum of variety lines to the net at the configured precision.
6. Atomically write supplier (if new), purchase record, one purchase-level traceability code, lots, stock movements, audit event and idempotency result.
7. Return the same committed result for identical retries; reject changed payload under the same key.
8. Never create a second approval task or require another employee to sign off the same direct purchase.
9. Preserve actor ID, device/source, gross/tare timestamps, weighing source and all measurement evidence.

If the operator has entered gross but not yet tare, save only a clearly marked incomplete measurement session if that workflow is implemented. Do not create a financially recognized purchase or stock receipt until the net and variety reconciliation are complete.

## 5. Separation of duties that remains mandatory

The no-review rule applies only to the act of registering the physical olive purchase. It does not grant unrestricted control over the money or later corrections.

Keep distinct capabilities for:
- `commercial.register_olive_purchase`: direct physical purchase/reception and atomic stock receipt;
- supplier payment recording: separate payment capability and settlement evidence;
- supplier payment reversal: restricted capability with reason and original-payment linkage;
- post-reception correction: controlled correction/reversal capability, immutable before/after audit and reason;
- general stock adjustment: separate capability, not implied by purchase registration;
- financial journal posting: accounting role/service only.

A purchase may be registered without second-person approval while its payment, correction or reversal remains separately controlled. Do not conflate a purchase's inventory receipt with cash leaving the business.

## 6. Assignment policy

The owner has not yet named the employees who should receive this capability. Therefore:
- define the capability in code and tests first;
- do not assign it to all workers;
- do not automatically assign it to existing worker accounts;
- do not invent user IDs or change current permissions;
- make administrator assignment explicit per employee once the owner identifies the designated operators.

## 7. Required API and permission tests

1. Admin can use the direct reception route.
2. Worker without `commercial.register_olive_purchase` receives 403.
3. Worker with only `commercial.register_olive_purchase` can complete one valid direct reception.
4. That worker cannot create/edit/approve arbitrary drafts through the generic purchase endpoints.
5. That worker cannot register supplier payments or reverse them unless separately assigned.
6. That worker cannot perform stock adjustments, sales, tank management or GL posting.
7. Inactive worker is denied even if a stale capability remains in the user document.
8. Same request key/same payload returns the original purchase and movement IDs.
9. Same request key/changed supplier, quantity, price, location or weighing evidence returns 409.
10. Purchase, lot, stock movement, audit and idempotency record commit or roll back together.
11. No human approval task is created for the direct reception.
12. Incomplete gross/tare cannot post inventory when weighing is enabled.

## 8. Release gate

Before runtime change, ensure GitHub Actions runs the API permission tests and MongoDB transaction tests on a real runner. Assign the capability only after the owner selects the authorized employees.

No runtime route, permission allowlist, employee record, database document or Render deployment is changed by this design document.

## 9. Frontend assignment UI constraint (additional source review, 18 Nov 2026)

The administrator's `EmployeePermissionsPanel` in `frontend/src/pages/Settings.tsx` also hardcodes the worker permission checkbox list. It currently renders only:
- `commercial.edit_records`
- `commercial.delete_records`
- `commercial.lab_record`
- `commercial.manage_preproduction_samples`
- `commercial.quality_release`
- `commercial.view_audit`

Therefore adding `commercial.register_olive_purchase` to the backend allowlist alone would still leave administrators unable to assign it through the existing UI. A complete runtime change must update all three enforcement/configuration surfaces together:
1. `backend/commercial/permissions.py` assignable allowlist;
2. `backend/commercial/routers.py` route/service authorization and assignment endpoint validation;
3. `frontend/src/pages/Settings.tsx` employee-permission checkbox and localized label.

The frontend checkbox is an assignment control, not a substitute for backend enforcement. Tests must verify both the API assignment contract and the resulting route behavior. No UI or backend permission change has been made.
