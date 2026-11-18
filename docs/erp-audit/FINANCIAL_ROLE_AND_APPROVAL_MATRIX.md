# Financial Role and Approval Matrix

Status: design and source-audit document only  
Branch: `audit/erp-foundation`  
Review date: 17 Nov 2026  
Runtime authorization changed: **No**

## 1. Executive conclusion

The current application has two coarse authorization models, not a complete job-role and approval model:

- Traditional API: public, any authenticated user, or administrator. The 29 authenticated-user routes include several write operations.
- GS API: administrator plus a worker permission allowlist. Several financial/operational capabilities exist only in the administrator set and cannot be assigned to workers. Some routes additionally require `require_admin`, so assigning a commercial permission would not make them worker-accessible.

The current model does not enforce maker/checker separation. A single administrator can create and approve purchases or sales, record payments, reverse payments, and perform other high-risk actions. This is a control gap, not proof of misuse.

**Do not solve this by granting all GS administrator permissions to every worker.** Introduce job roles and action-level capabilities, then enforce approval rules in backend services and transactions.

## 2. Current access observed in source

### 2.1 Traditional application

The mounted traditional-router inventory contains 85 routes: 7 public, 29 `current_user`, and 49 `require_admin`.

| Operation | Current access | Source-level observation |
|---|---|---|
| Register/load intake | Any authenticated user | `POST /loads` |
| Record oil output / update load status / deliver | Any authenticated user | `PATCH /loads/{id}/oil`, `PATCH /loads/{id}/status`, `POST /loads/{id}/deliver` |
| Create laboratory record | Any authenticated user | `POST /lab` |
| Create client | Any authenticated user | `POST /clients` |
| Read traditional invoices | Any authenticated user | `GET /invoices` |
| Create/update/delete traditional invoice | Administrator | `POST /invoices`, `PATCH /invoices/{invoice_id}`, `DELETE /invoices/{invoice_id}` |
| Accounting overview, daily situation, passive income and expenses | Administrator | Mounted accounting routes use `require_admin` |
| Client account statements and financial reports | Administrator | Admin-only routes in the mounted inventory |
| TV administration | Any authenticated user | Existing employee TV-editing requirement is reflected in current access; upload/delete/settings scope still needs a business decision |

Traditional authentication distinguishes administrator from authenticated user, not receptionist, press operator, lab analyst, cashier, accountant or supervisor. Consequently, any worker accepted by `current_user` can currently perform the listed operational writes.

### 2.2 GS purchases and suppliers

| Operation | Current access | Source-level observation |
|---|---|---|
| Create supplier | Administrator + `commercial.manage_purchases` | `POST /suppliers` |
| Update/deactivate supplier | Worker-capable `commercial.edit_records` / `commercial.delete_records` | `PUT/DELETE /suppliers/{supplier_id}` |
| Create olive reception + purchase + lot + stock receipt | Authenticated user + `commercial.manage_purchases` | `POST /olive-receptions`; workers cannot currently be assigned this permission |
| Create separate olive purchase draft | Administrator + `commercial.manage_purchases` | `POST /olive-purchases` |
| Edit/cancel purchase draft | Worker-capable `commercial.edit_records` / `commercial.delete_records` | `PUT /olive-purchases/{purchase_id}`, cancel route |
| Approve purchase / post received stock | Administrator + `commercial.manage_purchases` | `POST /olive-purchases/{purchase_id}/approve` |
| Record supplier purchase payment | Authenticated user + `commercial.manage_purchases` | `POST /olive-purchases/{purchase_id}/supplier-payments`; worker allowlist mismatch currently makes it admin-only in practice |

### 2.3 GS sales, payments and credits

| Operation | Current access | Source-level observation |
|---|---|---|
| Create sale draft | Administrator + `commercial.manage_sales` | `POST /sales` |
| Approve sale, issue invoice and dispatch stock | Administrator + `commercial.manage_sales` | `POST /sales/{sale_id}/approve`; transaction includes invoice, FIFO dispatch, stock movements and audit event |
| Cancel sale draft | Administrator + `commercial.manage_sales` | `POST /sales/{sale_id}/cancel`; service only cancels drafts |
| Receive/accept/reject sale return | Administrator | Return acceptance issues credit note; rejection dispatches quarantined stock |
| Record customer payment | Administrator + `commercial.manage_sales` | `POST /sales-invoices/{invoice_id}/payments` |
| Reverse customer payment | Administrator + `commercial.manage_sales` | `POST /sale-payments/{payment_id}/reversals` |
| Apply buyer credit | Administrator + `commercial.manage_sales` | `POST /sales-invoices/{invoice_id}/credit-applications` |
| Customer-owned custody receipt/release | Administrator + `commercial.manage_custody` | Receipt/release endpoints are admin-dependent |
| Internal ownership transfer / stock movement | Authenticated user + `commercial.post_stock` | Worker allowlist does not permit this capability |
| Adjust lot balance | Authenticated user + `commercial.edit_records`; zeroing also requires `commercial.delete_records` | `POST /lots/{lot_id}/adjust-balance`; both permissions are worker-assignable, but no separate approver is enforced |
| Pump selection/status | Authenticated user + `commercial.read` | State-changing handlers currently use a read permission; correct this in a future authorization change |

### 2.4 Permission-model mismatch

The current worker allowlist is limited to:

- `commercial.read`
- `commercial.lab_record`
- `commercial.quality_release`
- `commercial.view_audit`
- `commercial.manage_preproduction_samples`
- `commercial.edit_records`
- `commercial.delete_records`

Administrator capabilities additionally include purchase, sales, custody, production, stock-posting, stock-reversal and tank-management permissions. A route with `Depends(current_user)` plus one of these non-assignable capabilities is effectively unavailable to workers. A route with `Depends(require_admin)` is administrator-only regardless of the worker assignment list.

This is why route access must be evaluated from the combined dependency and effective-permission check, not from the permission string alone.

## 3. Target job-role model

The following is a proposed least-privilege target. It is not active runtime policy.

| Target role | May prepare / record | May approve / post | Must not do |
|---|---|---|---|
| Reception operator | Load intake, gross/tare capture, client lookup, receiving evidence | No financial approval | Approve own intake exceptions, alter posted invoices |
| Purchasing / reception operator | Direct olive purchase registration, supplier and delivery evidence, gross/tare/net capture, supplier-payment request | No authority to approve supplier payments or payment reversals | Alter posted weighing evidence without a correction event; authorize own supplier payment |
| Lab analyst | Sample and quality measurements, correction request | No quality release unless separately designated | Release own assessment |
| Quality approver | Review evidence and release/reject quality | Quality release only | Rewrite analyst measurements without trace |
| Production operator | Production run measurements, machine/pump progress | No inventory adjustment or sale approval | Post manual stock correction |
| Warehouse/tank operator | Receive/move stock, tank assignment, count/measurement proposal | Only low-risk receipt confirmation within assigned limits; high-risk adjustments require checker | Approve own stock adjustment or ownership transfer |
| Sales operator | Buyer/order/sale draft, dispatch request, return evidence | No sale approval, credit-note approval or payment reversal | Approve own sale or credit |
| Cashier | Record receipt/payment with method, account and reference | No reversal approval; no journal posting | Reverse own payment |
| Accountant | Review source documents, prepare journals, reconcile subledgers, tax evidence | Post only within delegated journal classes/limits; independent review for material entries | Create and approve same high-risk journal |
| Supervisor | Review operational exceptions and approve within explicit delegated limits | Approve designated operational events, not own requests | Override audit trail or approve own transaction |
| Administrator / owner | User/role configuration, policy configuration, exceptional authorization | Final approval only where governance permits | Bypass immutable audit or self-approve maker-created high-risk transactions |

Role assignment must be per user and may combine roles only where the conflict-of-duties policy allows. `admin` should not be treated as an automatic exemption from maker/checker controls.

## 4. Mandatory maker/checker rules

For the following events, the creator and approver must be different active users. The backend must reject self-approval even if the caller has both capabilities.

| Event | Maker | Checker / approver | Posting point |
|---|---|---|---|
| Olive purchase / reception | Authorized purchasing or reception employee records the purchase directly, including supplier, gross/tare/net weight, variety, price, receiving location and evidence | **No routine submission or second-person approval**; direct registration is the required operating rule | Save purchase, traceability lot and stock receipt atomically; preserve actor, timestamp and full weighing evidence |
| Supplier payment | Cashier/purchasing operator records payment request and supporting reference | Authorized finance approver verifies amount, payee, method and supporting proof | Record immutable settlement and update payable atomically |
| Wholesale sale | Sales operator creates draft | Sales supervisor approves price, buyer, quantity, tank and credit exposure | Approve sale, issue invoice and dispatch FIFO stock atomically |
| Customer receipt | Cashier records amount/method/reference | Finance approver for configured threshold, unusual method or exception | Post payment event and update receivable atomically |
| Payment reversal | Cashier/accountant requests reversal with reason and external evidence | Different finance approver authorizes it | Append reversal; never edit/delete original payment |
| Stock adjustment | Warehouse operator records count and discrepancy evidence | Different inventory controller/supervisor approves quantity, value and reason | Append adjustment movement and audit event atomically |
| Custody correction/release cancellation | Operator raises correction request | Different supervisor approves with customer evidence | Append compensating custody event; preserve original |
| Credit note / sale return | Sales operator records return and inspection | Different commercial/finance approver approves quantity, quality, value and credit | Issue credit note and any stock movement atomically |
| GL journal | Accountant prepares entry with source and support | Another authorized accountant/controller approves and posts | Balanced immutable journal + unique source posting identity |

Thresholds must be configurable and approved by the owner/accountant. Do not invent monetary thresholds in code. Low-value exceptions may use a documented alternate checker, but never silently disable maker/checker.

## 5. General authorization rules

1. Separate capabilities: `view`, `create_draft`, `edit_draft`, `submit`, `approve`, `post`, `reverse`, `cancel_draft`, `view_sensitive_financials`, `manage_users`.
2. A broad `edit_records` or `delete_records` permission must not authorize edits to posted financial/stock/custody documents.
3. Approval must check the source document state/version, maker identity, approver identity, role assignment, amount/quantity thresholds and evidence completeness inside the same transaction as posting.
4. Enforce authorization in service/domain functions as well as HTTP routes. Frontend button hiding is not a security boundary.
5. Read access must be segmented: workers may need operational invoice status without access to margins, supplier prices, bank details, full customer balances or accounting reports.
6. The audit event must include actor, role/capability snapshot, maker, approver, source ID, event type, old/new values or payload fingerprint, reason, evidence references and timestamps.
7. No direct update/delete of posted financial events. Use draft edits before posting and immutable reversal/adjustment events afterward.
8. Emergency override requires a reason, independent approver where available, explicit exception marker and audit event; no silent superuser bypass.
9. Protect role assignment itself: only designated owner/admin can grant roles, and privilege escalation must be audited.
10. Keep traditional app and GS role policies consistent where the same physical operation is represented in both modules.

## 6. Source-level implementation gaps and route targets

- `backend/commercial/permissions.py`: worker allowlist does not include purchase/sales/custody/stock/production capabilities. Replace broad permission names with action-level capabilities and role mapping only after approval.
- `backend/commercial/routers.py`: `/olive-receptions` requires `commercial.manage_purchases` with `current_user`, but that capability is not worker-assignable today. The route currently performs direct purchase approval and stock receipt in one transaction; the target is to make this direct-registration flow available to specifically authorized employees, without a pending-review step.
- `backend/commercial/routers.py`: separate purchase create/approve, sale create/approve, customer payment, payment reversal, buyer credit and custody receipt/release routes use `require_admin`; keep their controls distinct from the direct olive-reception rule.
- `backend/commercial/routers.py`: lot balance adjustment uses `edit_records` and optionally `delete_records`; no independent approval record is required.
- `backend/commercial/routers.py`: pump selection and pump-status mutation use `commercial.read`; replace with operational pump capabilities.
- `backend/routers/loads.py`: load creation, oil output, status and delivery are open to any authenticated user. Introduce reception/pressing/delivery capabilities without breaking the current employee workflow.
- `backend/routers/lab.py`: laboratory record creation is open to any authenticated user; separate analyst and approver actions.
- `backend/routers/invoices.py`: traditional invoice create/update/delete are admin-only; update can reprice and append payment, while delete physically removes the invoice. Introduce draft/issue/receipt/reversal lifecycle and independent approval for post-issue corrections.
- `backend/routers/accounting.py`: manual income/expense creation and deletion are admin-only; creation is a direct insert and deletion is physical, without a separate review/post state. Replace with request/review/post/reversal workflow.
- `backend/commercial/services/sales.py`: sale approval and payment recording are transactional and include audit events; preserve these atomic boundaries while adding maker/checker checks.
- `backend/commercial/services/purchases.py` and purchase-approval service: purchase draft and approval are separate states; add maker/checker identity validation to approval.
- Stock, custody, payment reversal and credit services must receive and validate the approval context, not trust a route-only check.

## 7. Transaction and idempotency observations

Positive controls already present in selected GS paths:

- Sale draft creation and audit insertion are in one transaction.
- Sale approval creates invoice, FIFO stock dispatch movements and audit event in one transaction; the service checks an approval idempotency key/fingerprint and optimistic version.
- Sale payment recording checks request idempotency and updates payment, invoice receivable and audit event in one transaction.
- Supplier olive-purchase payment has an idempotency key/index and transaction wrapper.
- Lot adjustment and internal movement routes use transaction wrappers.
- Several custody and return workflows execute their multi-document changes inside transactions.

Important gaps/limits:

- These transactions do not enforce a different maker and checker. Atomicity is not authorization separation.
- Traditional manual income/expense writes are direct inserts; deletes are direct physical deletes, with no transactionally coupled audit/reversal record.
- Traditional invoice update is transactional, but permits repricing and payment updates on the same invoice; a transaction does not make an invalid posted-document lifecycle safe.
- Traditional invoice deletion is transactional with an audit record, but still physically removes the source invoice.
- The source inspection did not prove idempotency for every endpoint. Do not assume a transaction alone prevents duplicate requests; each command needs a stable request key, unique constraint and same-payload retry semantics where duplicate submission is possible.

## 8. Required authorization and workflow tests

### API authorization matrix

For every protected route, test:
- anonymous user;
- inactive user;
- active worker with no role/capability;
- active worker with exactly the required capability;
- active worker with unrelated capability only;
- administrator;
- maker attempting to approve own transaction;
- different authorized checker;
- checker whose role was revoked after draft creation;
- concurrent approvals against the same document version.

### Financial workflow tests

- For the separate `/olive-purchases` draft/approve workflow, verify its intended approval policy explicitly; do not apply this maker/checker test to direct `/olive-receptions`. For direct supplier reception, test same-key/same-full-command retry returns the original purchase and receipt, changing any supplier identity/contact/tax field or receiving location under the same key conflicts, concurrent duplicate submissions return the winning result (not a spurious failure) and create exactly one purchase, lot set and stock receipt.
- Supplier-payment maker cannot approve own payment; overpayment and wrong payee are rejected; repeated submission cannot double-settle.
- Direct customer-load purchase (`/customer-purchases/loads`) tests must prove same-key retry returns the stored result, changed payload conflicts, concurrent requests cannot transfer the same source load twice, and the direct-purchase record has a unique idempotency index. Sale maker cannot approve own sale; stock and invoice remain unchanged if approval fails; retry does not duplicate dispatch or invoice.
- Cashier cannot reverse own payment; reversal cannot exceed unreversed original amount; original payment remains immutable.
- Stock maker cannot approve own adjustment; negative/zeroing adjustments require elevated review; ledger balance equals movement history.
- Credit note and return approval preserve the source invoice and physical stock history.
- GL journal cannot be posted by its maker; debit equals credit; source event posts once; reversal is a new linked journal.
- Frontend tests confirm controls reflect capability but API tests remain the authoritative security tests.

## 9. Decisions still required from the owner

The design can proceed without blocking ordinary source audit. Before runtime authorization changes, obtain decisions on:

1. Which named employees occupy purchasing, cashier, warehouse, sales, accountant and supervisor roles.
2. Who may act as the independent checker for each workflow when only a small number of staff are on shift.
3. Whether the owner may approve their own low-risk transaction in a documented emergency (recommended default: no for posted financial events).
4. Which operational invoice/customer balance fields employees may see.
5. Monetary/quantity thresholds requiring a second approval.
6. Whether TV media upload/delete remains available to all employees; this is separate from financial controls.

Until these are decided, keep current runtime access unchanged on the audit branch and do not merge/deploy the policy design.

## 10. Olive-purchase workflows: separate routes, separate controls

The source contains more than one olive-purchase path. They must not be conflated.

### 10.1 Supplier purchase and physical reception — `POST /commercial/v1/olive-receptions`

This is the one-step supplier purchase/reception flow relevant to the owner's direct-registration rule:

- It creates or resolves the supplier, creates an olive-purchase document, allocates the purchase traceability code, creates the lot(s), and posts the stock receipt in one MongoDB transaction.
- It internally calls the purchase-approval service immediately after creating the draft. The resulting `APPROVED` state is an internal posting transition by the same actor, **not a second-person review**.
- The command requires an `idempotency_key`. The purchase service scopes it by season and actor, stores a canonical fingerprint of the **inner purchase draft**, and the `commercial_olive_purchases` index set defines a unique `(idempotency_scope, idempotency_key)` constraint. Sequential retry with the same inner draft can return the existing purchase; a different inner-draft payload is rejected. The approval fingerprint separately includes the receiving location.
- **Endpoint-level idempotency is incomplete:** the stored purchase-draft fingerprint does not cover all outer command fields, including newly entered supplier phone/tax metadata. A same-key retry that changes such metadata may not be recognized as a changed request. The route also does not catch a concurrent duplicate-key race and re-read/return the winning result; the unique index prevents a second purchase document, but the losing request may receive a conflict instead of an idempotent success.
- The internally derived approval key and approval fingerprint protect the approval transition; they do not create a human checker.
- Current route authorization is `current_user` plus `commercial.manage_purchases`. That permission is not in the worker-assignable allowlist, so the route is effectively admin-only today.

**Required target:** keep this path direct. A specifically authorized employee records the purchase and receiving evidence; there is no pending-review state and no second-person approval gate. Preserve the transaction boundary and request idempotency. Add a dedicated assignable direct-purchase capability only after the authorized employee/role assignment is decided. The current request schema records line quantity, price, variety and location, but does not yet capture separate gross/tare measurements; the weighing-evidence requirement in section 11 remains an implementation gap.

### 10.2 Separate olive-purchase draft — `POST /commercial/v1/olive-purchases`

This is a distinct workflow:

- It creates a `DRAFT` purchase only.
- A separate `POST /olive-purchases/{purchase_id}/approve` command posts the receipt and stock.
- Both creation and approval routes currently require administrator access.
- The approval service checks state/version and an approval request fingerprint, but source inspection does not establish that maker and approver must be different people.

Do not silently substitute this draft/approve workflow for the owner's direct supplier-reception process. Whether this separate draft workflow remains available for exceptional/back-office cases is a separate product decision; it must not add a review queue to section 10.1.

### 10.3 Direct purchase of a customer's existing Oro Verde load — `POST /commercial/v1/customer-purchases/loads`

This is another distinct workflow: it purchases a complete existing traditional load from a customer and transfers ownership into mill-owned GS stock. It closes the source load, records custody/ownership-transfer ledger events, and writes a direct-purchase result in one transaction.

- It has its own idempotency key, season/user scope, deterministic child IDs and request-payload comparison.
- The source load is conditionally closed only while it remains eligible and not already transferred; this is an additional concurrency guard.
- The inspected inventory-index declaration does not define a unique idempotency index for `commercial_direct_load_purchases`. Sequential retries are checked in application code, but concurrent same-key submissions therefore need a dedicated unique index (and a duplicate-key recovery test) before claiming race-safe idempotency.
- This path uses the existing source load's `olive_kg`; it does not capture new gross/tare readings. It is not the same operation as purchasing a fresh supplier delivery.

### 10.4 Idempotency is not approval

For all three paths, keep these concepts distinct:

1. **Request idempotency:** a repeated client command with the same key and same payload must not create another purchase/receipt; same key with a different payload must conflict.
2. **Business approval:** a policy decision about who may authorize a transaction. For supplier olive reception, the owner's explicit rule is direct registration without human review.
3. **Accounting posting identity:** a later GL event must have its own unique source-event identity; an HTTP idempotency key is not a journal-posting key.

Atomic transactions protect multi-document consistency. Unique indexes, stable request keys, payload fingerprints and explicit retry handling protect against duplicate commands. None of these mechanisms should be described as independent human approval.

## 11. Weight evidence and direct-registration snapshot

For olive purchase/reception, the saved purchase record must preserve the exact weighing evidence at the time of direct registration:
- gross weight, tare weight and server-calculated net weight;
- weighing source (manual or later scale integration), scale/device identifier when applicable, measurement timestamps and operator;
- correction history with old/new values, actor, time and reason;
- net quantity used by purchase totals, lot receipt and stock movement.

Because no review step is required for this operation, there is no approver snapshot. Preserve the original registered values and identify the employee who entered them. Never trust a client-supplied net value. Any later change must create an auditable correction with old/new values, actor, timestamp and reason. This preserves the future weighbridge integration without pretending it is already connected.


## 12. Owner clarification: direct olive purchase registration

The owner explicitly requires that an employee records an olive purchase and gross, tare and net weights directly, **without submitting the operation for review**. This overrides the generic maker/checker proposal for olive purchase/reception only.

Required behavior:
- No pending-review or approval queue for olive purchase.
- A specifically authorized employee can register the purchase directly.
- Net weight is calculated and validated server-side from gross minus tare; do not trust a client-supplied net.
- Purchase, traceability lot, stock receipt and audit evidence are committed atomically.
- Record the responsible employee, weighing source, measurement times and gross/tare/net values.
- Corrections remain possible through an explicit, reasoned, auditable correction event; do not silently replace the original measurements.
- This does not waive independent controls for supplier payments, customer receipts, payment reversals, sale approval, stock adjustments or GL journals.
- The exact employee role assignment and any exceptional correction authority remain to be defined.

This is an owner-confirmed workflow requirement, not yet a runtime code change.
