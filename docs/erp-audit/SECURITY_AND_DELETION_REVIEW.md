# Security, Permissions and Destructive-Operation Review

Audit branch: `audit/erp-foundation`  
Scope: source inspection only; no production data or environment variables were changed.

## Executive findings

### S0 — Public authentication mode can grant administrator authority to every visitor

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

- No production Render environment variable was read or changed.
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
