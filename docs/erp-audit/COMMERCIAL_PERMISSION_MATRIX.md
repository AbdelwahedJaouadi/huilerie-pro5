# Commercial API Permission Inventory (Static Source Map)

Branch: `audit/erp-foundation`  
Source: `backend/commercial/routers.py`  
Static scan date: 17 Nov 2026

## Reading this inventory

- `Admin dependency` means the route requires `Depends(require_admin)` in addition to any listed commercial permission.
- `Authenticated user` means the route requires `Depends(current_user)`; where a commercial permission is listed, `_authorize` enforces it.
- `—` means no explicit `_authorize` call was found in the handler; check the route's admin dependency and any delegated service authorization.
- This is an inventory of source guards, not a proposed business role matrix. The effective result still depends on `AUTH_DISABLED`, the worker permission allowlist, and domain-service checks.

## Coverage summary

- Commercial route handlers scanned: **89**
- Handlers with `require_admin`: **26**
- Handlers with `current_user`: **63**
- Handlers without either dependency: **0**
- No unguarded handler was found in this scan.

## Route-by-route inventory

| Method | Route | Handler | Guard | Commercial permission |
|---|---|---|---|---|
| GET | `"/global-search"` | `global_search` | Authenticated user | — |
| GET | `"/status"` | `commercial_status` | Authenticated user | commercial.read |
| POST | `"/bootstrap"` | `bootstrap_commercial_domain` | Admin dependency | — |
| GET | `"/me/permissions"` | `get_my_commercial_permissions` | Authenticated user | — |
| GET | `"/tanks"` | `list_commercial_tanks` | Authenticated user | commercial.read |
| POST | `"/tanks"` | `create_commercial_tank` | Admin dependency | commercial.manage_tanks |
| POST | `"/tanks/{tank_id}/role"` | `update_commercial_tank_role` | Admin dependency | commercial.manage_tanks |
| PUT | `"/tanks/{tank_id}/capacity"` | `update_commercial_tank_capacity` | Admin dependency | commercial.manage_tanks |
| GET | `"/locations"` | `list_commercial_locations` | Authenticated user | commercial.read |
| POST | `"/locations"` | `create_commercial_location` | Admin dependency | commercial.manage_tanks |
| POST | `"/suppliers"` | `create_commercial_supplier` | Admin dependency | commercial.manage_purchases |
| PUT | `"/suppliers/{supplier_id}"` | `update_commercial_supplier` | Authenticated user | commercial.edit_records |
| DELETE | `"/suppliers/{supplier_id}"` | `deactivate_commercial_supplier` | Authenticated user | commercial.delete_records |
| GET | `"/suppliers"` | `list_commercial_suppliers` | Authenticated user | commercial.read |
| GET | `"/suppliers/{supplier_id}/statement"` | `get_supplier_payable_statement` | Authenticated user | commercial.read |
| GET | `"/olive-purchases/{purchase_id}/supplier-payments"` | `list_supplier_olive_purchase_payments` | Authenticated user | commercial.read |
| POST | `"/olive-purchases/{purchase_id}/supplier-payments"` | `create_supplier_olive_purchase_payment` | Authenticated user | commercial.manage_purchases |
| GET | `"/varieties"` | `list_commercial_varieties` | Authenticated user | commercial.read |
| POST | `"/buyers"` | `create_commercial_buyer` | Admin dependency | commercial.manage_sales |
| GET | `"/buyers"` | `list_commercial_buyers` | Authenticated user | commercial.read |
| PUT | `"/buyers/{buyer_id}"` | `update_commercial_buyer` | Admin dependency | commercial.manage_sales |
| POST | `"/buyers/{buyer_id}/status"` | `set_commercial_buyer_status` | Admin dependency | commercial.manage_sales |
| GET | `"/buyers/{buyer_id}/account-summary"` | `get_commercial_buyer_account_summary` | Authenticated user | commercial.read |
| POST | `"/sales"` | `create_wholesale_sale` | Admin dependency | commercial.manage_sales |
| POST | `"/sales/{sale_id}/cancel"` | `cancel_wholesale_sale_route` | Admin dependency | commercial.manage_sales |
| POST | `"/sales/{sale_id}/returns"` | `receive_sale_return` | Admin dependency | commercial.manage_sales |
| GET | `"/sale-returns"` | `list_sale_returns` | Authenticated user | commercial.read |
| POST | `"/sale-returns/{return_id}/accept"` | `accept_sale_return` | Admin dependency | commercial.manage_sales |
| POST | `"/sale-returns/{return_id}/reject"` | `reject_sale_return` | Admin dependency | commercial.manage_sales, commercial.post_stock |
| GET | `"/sale-return-rejections"` | `list_sale_return_rejections` | Authenticated user | commercial.read |
| GET | `"/credit-notes"` | `list_commercial_credit_notes` | Authenticated user | commercial.read |
| GET | `"/sales/pumps"` | `list_filling_pumps` | Authenticated user | commercial.read |
| POST | `"/sales/{sale_id}/pump-selection"` | `select_sale_filling_pump` | Authenticated user | commercial.read |
| POST | `"/sales/{sale_id}/pump-status"` | `update_sale_pump_status` | Authenticated user | commercial.read |
| GET | `"/sales"` | `list_wholesale_sales` | Authenticated user | commercial.read |
| POST | `"/sales/{sale_id}/approve"` | `approve_wholesale_sale_route` | Admin dependency | commercial.manage_sales |
| GET | `"/sales-invoices"` | `list_commercial_sales_invoices` | Authenticated user | commercial.read |
| POST | `"/sale-payments/{payment_id}/reversals"` | `reverse_wholesale_sale_payment` | Admin dependency | commercial.manage_sales |
| GET | `"/sales-invoices/{invoice_id}/payment-reversals"` | `list_invoice_payment_reversals` | Authenticated user | commercial.read |
| POST | `"/sales-invoices/{invoice_id}/credit-applications"` | `apply_buyer_credit` | Admin dependency | commercial.manage_sales |
| GET | `"/sales-invoices/{invoice_id}/credit-applications"` | `list_buyer_credit_applications` | Authenticated user | commercial.read |
| POST | `"/sales-invoices/{invoice_id}/payments"` | `create_sale_payment` | Admin dependency | commercial.manage_sales |
| GET | `"/sales-invoices/{invoice_id}/payments"` | `list_sale_payments` | Authenticated user | commercial.read |
| POST | `"/olive-receptions"` | `create_olive_reception_purchase` | Authenticated user | commercial.manage_purchases |
| POST | `"/olive-purchases"` | `create_olive_purchase` | Admin dependency | commercial.manage_purchases |
| PUT | `"/olive-purchases/{purchase_id}"` | `update_olive_purchase` | Authenticated user | commercial.edit_records |
| POST | `"/olive-purchases/{purchase_id}/cancel"` | `cancel_olive_purchase` | Authenticated user | commercial.delete_records |
| GET | `"/olive-purchases"` | `list_olive_purchases` | Authenticated user | commercial.read |
| POST | `"/olive-purchases/{purchase_id}/approve"` | `approve_purchase` | Admin dependency | commercial.manage_purchases |
| POST | `"/preproduction-samples"` | `create_preproduction_sample_route` | Authenticated user | commercial.manage_preproduction_samples |
| POST | `"/preproduction-samples/auto-complete"` | `auto_complete_preproduction_sample_route` | Authenticated user | commercial.lab_record |
| GET | `"/preproduction-samples"` | `list_preproduction_samples` | Authenticated user | commercial.read |
| POST | `"/preproduction-samples/{sample_id}/cancel"` | `cancel_preproduction_sample_route` | Authenticated user | commercial.manage_preproduction_samples |
| POST | `"/production-runs"` | `create_production_run` | Admin dependency | commercial.manage_production |
| GET | `"/production-runs"` | `list_production_runs` | Authenticated user | commercial.read |
| GET | `"/users/{target_user_id}/commercial-permissions"` | `get_commercial_permissions` | Admin dependency | — |
| POST | `"/users/{target_user_id}/commercial-permissions"` | `assign_commercial_permissions` | Admin dependency | — |
| POST | `"/quality-assessments"` | `create_quality_assessment` | Authenticated user | commercial.lab_record |
| POST | `"/quality-assessments/{assessment_id}/corrections"` | `correct_quality_assessment` | Authenticated user | commercial.lab_record |
| POST | `"/quality-assessments/release"` | `release_quality_assessment` | Authenticated user | commercial.quality_release |
| PUT | `"/quality-assessments/{assessment_id}"` | `update_quality_assessment` | Authenticated user | commercial.lab_record |
| DELETE | `"/quality-assessments/{assessment_id}"` | `delete_quality_assessment` | Authenticated user | commercial.lab_record |
| GET | `"/quality-assessments"` | `list_quality_assessments` | Authenticated user | commercial.read |
| GET | `"/lots"` | `list_commercial_lots` | Authenticated user | commercial.read |
| POST | `"/lots/{lot_id}/adjust-balance"` | `adjust_ready_olive_lot_balance` | Authenticated user | commercial.edit_records, commercial.delete_records |
| POST | `"/stock-movements"` | `create_stock_movement` | Authenticated user | commercial.post_stock |
| GET | `"/oil-purchases"` | `list_customer_oil_purchases` | Authenticated user | commercial.read |
| GET | `"/oil-purchases/customers/{customer_id}/statement"` | `get_customer_oil_purchase_statement` | Authenticated user | commercial.read |
| GET | `"/oil-purchases/{purchase_id}/payments"` | `list_customer_oil_purchase_payments` | Authenticated user | commercial.read |
| POST | `"/oil-purchases/{purchase_id}/payments"` | `create_customer_oil_purchase_payment` | Authenticated user | commercial.manage_sales |
| POST | `"/customer-purchases/loads"` | `purchase_customer_olive_load_directly` | Authenticated user | commercial.post_stock, commercial.manage_custody |
| GET | `"/internal-movements"` | `list_internal_stock_movements` | Authenticated user | commercial.read |
| POST | `"/internal-movements"` | `create_internal_stock_movement` | Authenticated user | commercial.post_stock |
| POST | `"/customer-custody/receipts/batch"` | `receive_customer_custody_olives_batch` | Admin dependency | commercial.manage_custody |
| POST | `"/customer-custody/receipts"` | `receive_customer_custody_olives` | Admin dependency | commercial.manage_custody |
| POST | `"/customer-custody/receipts/{receipt_id}/cancel"` | `cancel_customer_custody_receipt` | Authenticated user | commercial.delete_records, commercial.manage_custody |
| POST | `"/customer-custody/receipts/{receipt_id}/correct"` | `correct_customer_custody_receipt` | Authenticated user | commercial.edit_records, commercial.manage_custody |
| GET | `"/customer-custody/receipts"` | `list_customer_custody_receipts` | Authenticated user | commercial.read |
| POST | `"/customer-custody/releases"` | `release_customer_custody_oil` | Admin dependency | commercial.manage_custody |
| POST | `"/customer-custody/releases/{release_id}/cancel"` | `cancel_customer_custody_release` | Authenticated user | commercial.delete_records, commercial.manage_custody |
| POST | `"/customer-custody/releases/{release_id}/correct"` | `correct_customer_custody_release` | Authenticated user | commercial.edit_records, commercial.manage_custody |
| GET | `"/customer-custody/releases"` | `list_customer_custody_releases` | Authenticated user | commercial.read |
| GET | `"/customer-custody/owners/{customer_id}/statement"` | `get_customer_custody_statement_route` | Authenticated user | commercial.read |
| POST | `"/customer-custody/owners/resolve"` | `resolve_customer_custody_owner_route` | Authenticated user | commercial.post_stock |
| GET | `"/customer-custody/owners"` | `list_customer_custody_owners` | Authenticated user | commercial.read |
| GET | `"/stock-balances"` | `list_stock_balances` | Authenticated user | commercial.read |
| GET | `"/stock-movements"` | `list_stock_movements` | Authenticated user | commercial.read |
| GET | `"/audit-events"` | `list_commercial_audit_events` | Authenticated user | commercial.view_audit |
| POST | `"/reports/export.pdf"` | `export_commercial_report_pdf` | Authenticated user | commercial.read |

## Permission interpretation

The current worker allowlist is narrower than the administrator permission set. In particular, workers cannot be assigned `commercial.manage_tanks`, `commercial.manage_purchases`, `commercial.manage_sales`, `commercial.manage_custody`, `commercial.manage_production`, `commercial.post_stock`, or `commercial.reverse_stock` through the current assignment endpoint. Some routes for those operations are administrator-only in any case.

The current assignable permissions are `commercial.read`, `commercial.lab_record`, `commercial.quality_release`, `commercial.view_audit`, `commercial.manage_preproduction_samples`, `commercial.edit_records`, and `commercial.delete_records`.

Do not expand this allowlist just to make a screen or button work. Define the job responsibilities and separation-of-duties rules first. For example, the person recording a quality assessment should not automatically be the person authorized to release it; the code already separates `commercial.lab_record` and `commercial.quality_release`.

## Follow-up required

1. Compare this source map with every frontend action and identify inaccessible or overexposed controls.
2. Define roles for reception, lab analyst, quality approver, production operator, warehouse/tank operator, buyer/sales operator, accountant and manager.
3. Decide whether edit/delete permissions should be entity-specific rather than global.
4. Test anonymous, inactive, worker-no-permission, worker-with-permission and administrator access at API level.
5. Re-run the inventory after any router changes.


## Additional authorization findings — assignability and state-changing reads

Source reviewed: `backend/commercial/permissions.py` and the route handlers in `backend/commercial/routers.py`.

The worker assignment allowlist currently contains only:
- `commercial.read`
- `commercial.lab_record`
- `commercial.quality_release`
- `commercial.view_audit`
- `commercial.manage_preproduction_samples`
- `commercial.edit_records`
- `commercial.delete_records`

The administrator permission set additionally contains `commercial.manage_tanks`, `commercial.post_stock`, `commercial.reverse_stock`, `commercial.manage_sales`, `commercial.manage_custody`, `commercial.manage_purchases` and `commercial.manage_production`. These operational capabilities cannot currently be assigned to workers through the assignment schema/allowlist. Consequently, the existing worker permission UI cannot express the full set of job duties proposed for reception, purchasing, production, warehouse or sales.

A second issue is that the pump selection and pump status handlers are inventoried with `commercial.read`; these operations mutate operational state and should not be authorized by a read-only capability in the target role model.

Do not simply add all administrator permissions to the worker allowlist. Before changing runtime authorization:
1. Define capabilities by action (create, edit, submit, approve, post stock, reverse, cancel, view financial data).
2. Separate maker/checker duties for quality release, stock adjustments, sales approval, payment reversal and financial posting.
3. Assign capabilities to named job roles and verify the actual user-to-role data model.
4. Add route tests for anonymous, inactive, worker without capability, worker with capability, and administrator.
5. Review frontend visibility and backend enforcement together; hiding a button is not authorization.

No runtime permission behavior was changed by this documentation update.
