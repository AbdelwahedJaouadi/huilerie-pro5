# Security, Permissions and Destructive-Operation Review

Audit branch: `audit/erp-foundation`  
Scope: source inspection only; no production data or environment variables were changed.

## Executive findings

### S0 — Public authentication mode is rejected at production startup; retain this fail-closed guard

In `backend/lib/auth.py`, `current_user()` checks `AUTH_DISABLED`. When the value is one of `1`, `true`, `yes` or `on`, it returns the first active database user whose role is `admin`, without validating a session cookie or identity. `require_admin()` then accepts that returned administrator.

This means that **if `AUTH_DISABLED` is enabled on the public production API, unauthenticated visitors are treated as an administrator**. This is not merely a hidden login screen: it bypasses the authentication boundary for every route depending on `current_user` or `require_admin`, including commercial write operations and administration.

The source default is `false`, but the live Render environment value was not independently read in this audit. Therefore the production exposure is **conditional and unverified**, not a claim that the live service is currently exposed.

**Required release gate:** verify the production backend environment has `AUTH_DISABLED=false` (or the variable is absent) before treating the API as protected. Do not change the live setting blindly as part of this documentation-only audit; coordinate the authentication transition and verify that the login/session flow works first.

### S1 — Traditional invoice deletion permanently removes the invoice

`backend/routers/invoices.py`, `DELETE /invoices/{invoice_id}`:
- Requires `require_admin`.
- Deletes the invoice document with `delete_one`.
- Writes an `INVOICE_DELETED` audit event containing a subset of the removed values.

The audit event is not a substitute for preserving the original financial document. For full accounting, posted invoices must be immutable and corrected by a linked void/reversal or credit document. Deletion should be limited to explicitly permitted unposted drafts, if that state is formally introduced.

### S1 — Accounting income and expense records are hard-deleted

`backend/routers/accounting.py`:
- `DELETE /passive-incomes/{income_id}` directly deletes the record.
- `DELETE /expenses/{record_id}` delegates to a helper that directly deletes the record.
- Both are administrator-only.

These records currently belong to a lightweight operational accounting view, not a double-entry ledger. Before full accounting is implemented, replace deletion with an auditable cancellation/reversal or correction workflow. Preserve the original values and actor, timestamp and reason.

### S1 — Traditional load deletion checks only a subset of downstream references

`backend/routers/loads.py`:
- The delete helper blocks a load when a traditional invoice exists.
- It also blocks a load whose ownership has been transferred to the mill.
- Otherwise it deletes the load and all linked `lab` documents, then writes `LOAD_DELETED`.

The helper does not establish that every possible downstream reference is absent (including GS references, quality, custody, production, stock, or other audit-linked documents). A missing invoice is not proof that a load is safe to erase.

**Required policy:** enumerate all collections that can reference a load; block hard deletion if any downstream reference exists; prefer cancellation with a reason and preserve the original load and lab history. Do not retrofit invented gross/tare weights into legacy loads.

## Commercial permission model observed

### Effective permission sets

`backend/commercial/permissions.py` defines:

- Administrators: all declared commercial permissions.
- Workers: always `commercial.read`, plus only explicitly assigned permissions from `ASSIGNABLE_COMMERCIAL_PERMISSIONS`.
- Assignable worker permissions currently include:
  - `commercial.read`
  - `commercial.lab_record`
  - `commercial.quality_release`
  - `commercial.view_audit`
  - `commercial.manage_preproduction_samples`
  - `commercial.edit_records`
  - `commercial.delete_records`

The worker permission resolver fails closed for inactive users, non-worker roles, malformed permission lists and unknown permission names.

### Route-level implications

The commercial router applies `_authorize` on its inspected endpoints, but some sensitive handlers additionally require `require_admin`. A permission assignment does not override a separate administrator-only dependency.

Observed examples:
- Supplier update/deactivation: `commercial.edit_records` / `commercial.delete_records`; deactivation is soft-delete and retains historical supplier references.
- Olive purchase draft update/cancel: `commercial.edit_records` / `commercial.delete_records`.
- Quality assessment create/update/delete: `commercial.lab_record`; the delete path delegates to a domain service, so its exact retention semantics must be verified before classifying it as soft-delete or hard-delete.
- Lot balance adjustment: requires `commercial.edit_records`; a zero target additionally requires `commercial.delete_records`.
- Stock movement direct-post endpoint is deliberately rejected after authorization; movements must originate from the owning purchase, production, transfer or sales workflow.
- Several purchase, sales, tank, buyer, production and custody mutations also require `require_admin`, even where a commercial permission is checked.

### Traditional app and accounting access

Traditional loads and invoices generally depend on `current_user`, with selected actions requiring `require_admin`. The current accounting overview, passive-income and expense routes inspected here require administrator access. There is no single cross-module role matrix proving that every intended employee can perform their assigned job without over-privileging them.

**Required next step:** derive a route-by-route matrix from every router, then agree the business role matrix (operator, reception, lab/quality, production, warehouse, sales, accountant, manager/admin) before changing authorization. Do not infer role permissions from UI visibility.

## Recommended implementation sequence

1. Verify production `AUTH_DISABLED` state and complete the normal authenticated session test before any public release.
2. Build a route-by-route authorization matrix for traditional, commercial and accounting APIs; flag endpoints missing explicit dependencies or domain authorization.
3. Inventory every reference to `loads.id` and define hard-delete blockers.
4. Introduce a preserved-document cancellation/reversal model for invoices and accounting records; do not rewrite posted history.
5. Verify the domain service behind quality-assessment deletion and every commercial cancel/correct workflow.
6. Add tests for anonymous, worker-without-permission, worker-with-permission, inactive user and administrator cases for each sensitive route.
7. Add regression tests proving historical source documents remain retrievable after cancellation/reversal.

## Explicit non-changes

- No production Render environment variable was read or changed. The source startup guard and its unit test were inspected.
- No MongoDB documents or collections were changed.
- No operational API behavior was changed.
- No branch was merged and no deployment was triggered.
- The application remains `huilerie-pro5` using the user-confirmed `huilerie-pro3` database.


## Route inventory coverage (static scan)

A static decorator/dependency scan of the commercial router found 89 route handlers. Every inspected handler declares either `Depends(current_user)` or `Depends(require_admin)`; no handler without one of those authentication dependencies was found in that router scan. The same scan found no unguarded route in the inspected traditional files:

- `backend/routers/loads.py`: 10 routes, all authenticated; 3 administrator-only (cancellations, cancel, delete).
- `backend/routers/invoices.py`: 5 routes, all authenticated; eligible-loads, create, update and delete are administrator-only.
- `backend/routers/accounting.py`: 8 routes, all administrator-only.

This is a static source check, not a live authorization test. It does not negate the S0 `AUTH_DISABLED` bypass: when that switch is on, `current_user` returns an administrator and therefore all of these dependencies accept the request.

## Verified semantics behind selected commercial delete/cancel routes

Further inspection of the called domain services narrows several earlier concerns:

- Supplier DELETE is a **soft deactivation** (`active=false`) with version check, actor metadata and an audit event; historical purchase references remain.
- Olive purchase UPDATE is restricted to `DRAFT` and writes before/after details to the audit event. Olive purchase cancel is also restricted to `DRAFT`, requires a reason, changes status to `CANCELLED`, and preserves the document and audit details. Approved receipts cannot use these draft-only operations.
- Quality-assessment DELETE is restricted to the submitting analyst or an administrator, only for the latest assessment in `AWAITING_INDEPENDENT_REVIEW`, and restores the prior lot quality state. Reviewed assessments are explicitly immutable. The assessment document itself is deleted, but a detailed audit event stores its snapshot and the prior/after lot state. This is a narrowly scoped draft-like deletion, not deletion of a reviewed decision.
- Preproduction sample cancellation is a state transition to `CANCELLED`; it requires a reason and only permits cancellation of a currently rejected sample with its latest rejected assessment.
- Customer-custody receipt/release cancellation and correction are domain workflows that check later stock activity before allowing cancellation. Their service methods preserve cancellation metadata and audit events.

The above means the commercial domain already contains several sound patterns worth reusing. The highest-risk destructive gaps remain traditional invoice deletion, accounting income/expense deletion, and traditional load deletion without a complete downstream-reference check.

## Permission assignment caveat

The route inventory distinguishes two controls:
1. `_authorize(...)` checks the commercial permission.
2. `Depends(require_admin)` independently restricts the endpoint to administrators.

Workers can be assigned only the allowlisted permissions in `ASSIGNABLE_COMMERCIAL_PERMISSIONS`. Some endpoints that check management permissions also carry an administrator dependency, so assigning a permission alone does not grant worker access. Conversely, worker-assignable `edit_records` and `delete_records` permissions can enable draft/specific-record operations such as supplier deactivation, olive-purchase draft changes, and the limited quality-assessment deletion above.

The route scan confirms dependency presence, not that the current assignment model matches the mill's intended staffing model. A role matrix and endpoint tests are still required.


## Existing test coverage and a test that currently encodes the weak load-delete rule

- `backend/commercial/tests/test_permissions.py` covers the pure permission resolver, explicit worker grants, separation between lab recording and quality release, edit/delete assignment and inactive/unknown users.
- `backend/commercial/tests/test_security_config.py` verifies that production rejects `AUTH_DISABLED=true`; this supports the fail-closed conclusion above.
- `backend/tests/test_load_delete_unit.py` currently asserts that a load can be deleted whenever no invoice is found.
- `backend/tests/test_atomic_invoice_deletes_unit.py::test_load_delete_checks_invoice_and_deletes_with_same_session` also expects the sequence invoice-check → load-read → load-delete → lab-delete → audit-event. It does not simulate a GS purchase, custody, quality or production reference.

The last two tests are transaction-focused, but their expected behavior is too permissive for the target ERP traceability model. They should be strengthened when the complete load-reference inventory is finished: a referenced load must be retained and cancellation must not erase its source history. Keep the transaction/audit atomicity assertions while adding the downstream-reference blocker cases.

## First implementation candidate (not yet changed)

The first narrowly testable source correction should be the traditional load deletion policy, after enumerating all actual load references. The change should:
- keep the existing invoice and ownership-transfer checks;
- add explicit checks for every confirmed downstream reference, rather than guessing collection names or checking only a subset;
- reject hard deletion with a stable conflict code when a reference exists;
- preserve the current transaction boundary and audit event;
- add tests for each reference type and for the genuinely unreferenced case.

Do not implement this by blanket-blocking every load forever, because that would silently remove the ability to clean up a mistaken, never-used draft. The rule must distinguish an unreferenced intake draft from a source record already consumed by a business workflow.


## Additional critical path: deleting a client bypasses the safer single-load deletion helper

A further source trace found a second deletion route in `backend/routers/extras.py`:

- `DELETE /clients/{phone}` loads every traditional load for that phone.
- It checks only whether any of those loads has a traditional invoice.
- If no invoice exists, it deletes the client, deletes the associated lab and SMS records, and bulk-deletes all matching loads in one transaction.
- It does **not** call the single-load deletion helper in `backend/routers/loads.py`.
- It does not check `ownership_transferred`, `commercial_direct_load_purchases.source_load_id`, `commercial_customer_custody_receipts.source_load_id`, `commercial_lots.source_load_id`, or other GS references before bulk deletion.

This is more serious than the single-load route: the single-load helper blocks a transferred load, but the client-wide bulk-delete path does not apply that guard. A customer whose load has been purchased directly by the mill or received into GS custody could therefore have the original traditional load removed while GS documents retain its source ID. The current Atlas snapshot's reference checks were read-only and found no dangling references at that inspection point; they do not protect against this future deletion path.

The current tests `test_client_delete_unit.py` and `test_atomic_invoice_deletes_unit.py` validate only the invoice guard and transaction order. They do not exercise transferred loads or GS references.

**Priority adjustment:** the first implementation candidate must cover both deletion entry points together. Create one shared load-deletion eligibility service used by single-load deletion and client deletion. The client deletion must either:
- reject the entire operation if any load has any downstream/ownership-transfer reference; or
- retain those source loads and only delete genuinely unreferenced draft loads, while preserving the client identity needed by historical GS/customer records.

Do not allow a bulk-delete route to bypass the domain invariants of the single-record route. The desired behavior for mixed client histories (some deletable drafts, some retained referenced loads) must be explicit and tested before implementation.


## Other traditional destructive endpoints found

The additional router scan found:

- `DELETE /lab/{id}` in `backend/routers/lab.py` directly deletes a lab-analysis document. It requires an administrator, but the inspected handler does not write a dedicated audit event or check whether the analysis is part of a historical source-load record. The client-wide deletion path also deletes all lab records for the selected loads. This should become a controlled correction/void operation or a narrowly permitted deletion of an unreferenced draft, with an audit trail.
- `DELETE /users/{id}` in `backend/routers/admin.py` hard-deletes a user account (except the currently signed-in administrator). Prefer deactivation for accounts that have authored operational or audit records so actor identity remains resolvable. Hard deletion should be limited to never-used accounts under an explicit policy.
- `DELETE /sms/{sms_id}` deletes an SMS log, and `DELETE /sms/twilio` deletes Twilio configuration. These are not equivalent to deleting business source documents; configuration removal may remain a separate administrator action, while sent-message history should generally be retained according to a defined retention policy.
- `POST /admin/reset` can clear explicitly selected operational/audit collections after the exact `RESET` confirmation and writes a separate `admin_reset_audit` record after the transaction. This is a high-impact administrative function and must remain tightly permissioned; it was not invoked in this audit.

These are source-level findings. No delete endpoint was called during the review.


## Implemented on `audit/erp-foundation`: client deactivation and shared load-delete guard

The approved rule has now been implemented in source on this audit branch. It has **not** been merged or deployed.

### Client deletion behavior

- `DELETE /clients/{phone}` hard-deletes only a client registry record with no traditional load history, no SMS history and no matching GS buyer/custody references.
- If any traditional load exists for that phone, the endpoint now deactivates the client record (`active=false`) and preserves every load, lab analysis, SMS record, invoice and GS reference.
- A client with GS identity history but no traditional load is also deactivated rather than erased.
- Deactivation and its `CLIENT_DEACTIVATED` audit event are written in the same transaction.
- The API response distinguishes `deleted` from `deactivated` and reports `loads_retained`.
- The Clients page displays active/deactivated status and offers an explicit reactivation action. Reactivation and its audit event are transactional.
- Deactivated clients are removed from `/clients/options`, and new load intake is rejected with `client_inactive`. The intake route checks the client status both before allocating a code and again inside the load-creation transaction.
- New load creation creates/updates the client registry record and increments an intake guard version. A unique partial index on `clients.phone` prevents duplicate registry identities. A read-only Atlas aggregation verified there were no duplicate string phone values in the existing `clients` collection before adding this index to application startup configuration.

### Shared load deletion policy

Single-load hard deletion now calls `_ensure_load_is_deletable`. It retains the original invoice guard and additionally blocks deletion when:
- ownership or custody has been transferred, or the customer-available quantity has decreased;
- the load has entered pressing, has oil output, was delivered or was cancelled;
- a GS direct-load purchase references it through `commercial_direct_load_purchases.source_load_id`;
- a GS customer-custody receipt references it through `commercial_customer_custody_receipts.source_load_id`;
- a GS lot references it through `commercial_lots.source_load_id`;
- a laboratory analysis or SMS log references it.

The load and linked history are no longer cascade-deleted by the single-load route. Only an unreferenced, unprocessed intake record can be hard-deleted; the deletion itself is audited in the transaction.

### GS identity fields verified against Atlas collection schemas

- `commercial_buyers.phone`
- `commercial_custody_owners.client_phone`
- `commercial_customer_custody_receipts.customer_phone`
- `commercial_direct_load_purchases.source_load_id`
- `commercial_customer_custody_receipts.source_load_id`
- `commercial_lots.source_load_id`

These field names were checked against the current `huilerie-pro3` database schema. Client deactivation checks the correct phone field for each customer/custody collection; load deletion checks the three confirmed `source_load_id` references.

### Tests added or updated

- Client with traditional load history is deactivated without deleting related documents.
- Client without operational history can still be hard-deleted.
- GS buyer or customer-custody receipt phone reference causes deactivation.
- Unknown client returns 404.
- Deactivated client is excluded from the new-client selector.
- New load intake rejects an inactive client.
- Single-load deletion checks all confirmed GS, lab and SMS references and rejects a GS-referenced load without deleting it.
- Transaction tests preserve the audit-event and deletion transaction boundary.

**Validation limitation:** the repository was edited through GitHub source operations; no local checkout or executable test runner was available in this session. The test files were updated, but pytest, TypeScript build and Render deployment have not been run. Do not treat this branch as release-ready until CI or a local checkout runs the affected test suite and frontend build.


### Boundary of this client deactivation change

The change deactivates the **traditional Oro Verde client registry** and prevents new traditional load intake. It does not modify the separate GS `commercial_buyers` or `commercial_custody_owners` master records; those records are used by distinct GS workflows and are preserved as-is. Their phone values are used to detect historical GS references and decide against hard deletion. A future unified customer master would need an explicit cross-module activation policy rather than silently changing independent GS entities.
