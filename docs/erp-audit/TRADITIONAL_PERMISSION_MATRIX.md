# Traditional Application API Permission Inventory

Branch: `audit/erp-foundation`  
Source routers mounted by `backend/server.py`: auth, loads, lab, admin, extras, campaign, TV, invoices, client accounts and accounting. The unused `extras_pdf_backup.py` is not mounted and is excluded.

## Static scan summary

| Guard class | Routes | Meaning |
|---|---:|---|
| Public | 7 | No user dependency; only login/logout image and TV display endpoints |
| Authenticated user | 29 | Any active authenticated account, including workers |
| Administrator | 49 | `require_admin` |
| **Total** | **85** | Source-decorator inventory |

No unguarded route outside the explicit public allowlist was found in the mounted traditional routers. This is a source scan, not an API penetration test.

## Public allowlist

- `GET /login-image`
- `POST /login`
- `POST /logout` (clears the session cookie; does not grant access)
- `GET /tv/display-settings`
- `GET /tv/display-settings/version`
- `GET /tv/music/audio/{file_id}`
- `GET /tv/board`

These endpoints support the unauthenticated login flow and public TV display. Keep public TV responses restricted to display/media fields; do not expose user, invoice, buyer or accounting data through them.

## Authenticated-user routes (workers and administrators)

### Loads and production
- `POST /loads`
- `GET /loads`
- `GET /loads/by-code/{code}`
- `PATCH /loads/{id}/oil`
- `PATCH /loads/{id}/status`
- `POST /loads/{id}/deliver`
- `GET /stats`

**Important:** the current code allows any authenticated worker to register loads, record oil output, change load status and deliver oil. This is broad module-level access, not a role-specific authorization policy.

### Laboratory
- `GET /lab`
- `POST /lab`

### Client and reference data
- `GET /mill`
- `GET /sms`
- `GET /sms/status`
- `GET /clients`
- `GET /clients/options`
- `POST /clients`
- `GET /clients/{phone}/all-loads`
- `GET /clients/{phone}`
- `GET /lab/{id}/certificate`
- `GET /invoices`

### Campaign and varieties
- `GET /seasons`
- `GET /varieties`

### TV administration
- `GET /tv/media-settings`
- `PUT /tv/media-settings`
- `POST /tv/music/upload`
- `GET /tv/control`
- `PUT /tv/control`
- `GET /tv/admin`
- `PATCH /tv/items/{id}`

TV management is currently available to any authenticated employee, consistent with the requested employee access to TV media controls. Confirm whether deleting/uploading media and changing display settings should remain open to all roles.

### Authentication
- `GET /me`

## Administrator-only routes

### Accounting and financial reports
- `GET /accounting/overview`
- `GET /accounting/passive-incomes`
- `POST /accounting/passive-incomes`
- `DELETE /accounting/passive-incomes/{income_id}`
- `GET /accounting/expenses`
- `POST /accounting/expenses`
- `DELETE /accounting/expenses/{record_id}`
- `GET /accounting/daily-situation`
- `GET /reports/revenue`
- `GET /reports/workers`
- `GET /reports/revenue.xlsx`
- `GET /reports/revenue.pdf`

### System administration and user management
- `GET /admin/reset/preview`
- `POST /admin/reset`
- `GET /admin/reset/counters/preview`
- `POST /admin/reset/counters`
- `GET /admin/export.zip`
- `GET /admin/export.pdf`
- `GET /users`
- `POST /users`
- `PATCH /users/{id}`
- `DELETE /users/{id}`
- `GET /settings`
- `PUT /settings`

### Client and messaging administration
- `DELETE /sms/{sms_id}`
- `GET /sms/twilio`
- `PUT /sms/twilio`
- `DELETE /sms/twilio`
- `GET /sms/tunisie`
- `PUT /sms/tunisie`
- `POST /sms/tunisie/test`
- `POST /sms/test`
- `POST /sms/reminders/run`
- `PUT /clients/{phone}`
- `DELETE /clients/{phone}` (deactivates clients with history; hard-deletes only history-free records)
- `POST /clients/{phone}/reactivate`

### Invoices
- `GET /invoices/eligible-loads`
- `POST /invoices`
- `PATCH /invoices/{invoice_id}`
- `DELETE /invoices/{invoice_id}`

### Client account statements
- `GET /client-accounts/search`
- `GET /client-accounts/{phone}`

### Seasons and varieties
- `POST /seasons`
- `PUT /seasons/active`
- `PUT /varieties`

### Load administration
- `GET /loads/cancellations`
- `POST /loads/{id}/cancel`
- `DELETE /loads/{id}` (shared downstream-reference guard)

### Laboratory
- `DELETE /lab/{id}`

## Authorization gaps and decisions required

1. `current_user` is a binary authenticated-user check. It does not distinguish reception, pressing operator, lab analyst, quality approver, warehouse/tank operator, sales, accountant or supervisor.
2. Workers currently have write access to several sensitive traditional operations (load registration, oil entry, status changes, delivery, lab creation, client creation, TV settings/media and TV item updates).
3. Invoice creation/update/deletion, client-account statements, accounting, reports and most master-data settings are administrator-only. Verify whether the accountant role should receive selected accounting functions without full admin privileges.
4. The GS router has a separate commercial permission system, but some endpoints also require administrator authority. Keep the two models distinct until a unified role matrix is approved.
5. Public TV endpoints are intentionally unauthenticated; add regression tests to ensure their payloads never expand to confidential data.
6. Route dependency presence does not prove that the effective production authentication configuration is safe. Preserve the production startup guard against `AUTH_DISABLED`.

## Recommended role design before changing permissions

Define explicit capabilities per job role, not merely per screen:

- Reception: register arrivals and capture gross/tare/net weights.
- Pressing operator: update processing status and record actual oil output.
- Lab analyst: enter analyses.
- Quality approver: independently release/reject quality decisions.
- Warehouse/tank operator: receive, transfer and reconcile stock.
- Sales: create buyer sales and record customer payments.
- Accountant: view and post financial transactions, subject to separation of duties.
- Supervisor/manager: approve exceptions, cancellations and adjustments.
- Administrator: manage users, security, global settings and controlled resets.

Do not grant all permissions to every worker to fix a blocked button. Add route-level tests for anonymous, inactive, worker-without-capability, worker-with-capability and administrator cases.
