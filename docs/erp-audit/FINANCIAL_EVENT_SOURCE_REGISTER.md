# Financial Event Source Register — Oro Verde

Project: huilerie-pro5
Branch: audit/erp-foundation
Review date: 17 Nov 2026
Method: static source inspection of the active branch. This is a source register and accounting-design aid, not an assertion that every listed collection currently contains live data. No production records were changed.

## 1. Purpose and rule

Every future general-ledger posting must originate from one authoritative operational event. The register prevents the same economic event being posted twice from both a parent document and its payment/stock child documents.

The accounting engine must post from explicit business events, not from dashboard totals, denormalized balance snapshots, audit-event descriptions, or UI summaries.

## 2. Traditional mill workflow

| Business event | Authoritative source | Financial facts currently visible in source | Posting design / unresolved gate |
|---|---|---|---|
| Customer pressing completed and invoiced | `invoices` linked to `loads` | oil quantity, tariff, total, paid amount, balance; embedded `payments[]` | Invoice creates service receivable/revenue; each receipt is a separate cash/bank settlement. Confirm revenue-recognition date and tax classification. |
| Initial receipt on traditional invoice | `invoices.payments[]` embedded event | timestamp, actor username, amount | Treat as receipt event, not a second revenue event. Legacy aggregate fallback is not a reliable historical payment date. |
| Additional receipt | `invoices.payments[]` embedded event, appended by PATCH when `payment_amount > 0` | timestamp, actor username, amount | Post only the appended payment delta. Never post the invoice's cumulative `paid_amount` again. |
| Client receivable statement | derived from `invoices` and `loads` | invoice totals, receipts and balances | Read model only; do not use statement rows as a posting source. |
| Traditional invoice repricing | update of `invoices.price_per_kg/total/balance` | current tariff and recalculated total | Critical policy gap: issued invoice may be repriced even after receipts. Future accounting must use a credit/debit adjustment or controlled cancellation/reissue; never silently rewrite posted revenue. |
| Traditional invoice deletion | `DELETE /invoices/{id}` | physical source invoice removal plus audit event | Critical policy gap: posted financial documents must not be physically deleted. Replace with cancellation/reversal/credit-note lifecycle before GL go-live. |

### Traditional invoice compatibility hazards

- PATCH still accepts legacy `paid_amount` as a replacement aggregate. This can overwrite the cumulative paid snapshot without creating an individual payment event. It must be retired or constrained to a controlled reconciliation operation before ledger automation.
- Payment event identity is currently derived from invoice ID, timestamp and amount in the read model; it is not a first-class immutable payment-document ID. The future ledger should assign a stable payment ID and unique source-event key.
- Invoice creation converts `oil_kg` to Python float before computing the total. Standardize quantity and money arithmetic on Decimal end-to-end before statutory posting.
- Legacy invoices without itemized payment arrays fall back to one aggregate payment event dated from invoice day/creation time. Preserve this as an explicitly marked migration estimate, not a verified receipt date.

## 3. GS purchases and supplier payables

| Business event | Authoritative source | Financial facts | Posting design / gate |
|---|---|---|---|
| Draft olive purchase | `commercial_olive_purchases` | supplier, purchase date, line quantities, unit prices, line totals, total amount, status DRAFT | Draft has no GL effect. |
| Approved olive purchase | same purchase document after approval | approved status, quantity, total, supplier and batch traceability code | Recognition depends on transfer of ownership and acceptance. Confirm contractual title/risk transfer and inventory valuation policy under NC 04. |
| Supplier payment for olive purchase | `commercial_supplier_olive_purchase_payments` | payment amount TND, date, method, reference, supplier and purchase IDs | Separate payment event settles supplier payable; never derive a second payment from purchase's paid/outstanding snapshot. |
| Supplier statement | approved purchases + supplier payment documents | derived running payable balance | Read model only. Reconcile its total to supplier subledger and GL control account. |

Purchase service creates a DRAFT purchase with Decimal128 quantities/prices/totals and an idempotency scope/key. Draft updates are version-checked and audited. Draft cancellation is soft cancellation; approved stock receipts are not cancelled through that draft path.

## 4. Wholesale oil sales and buyer receivables

| Business event | Authoritative source | Financial facts | Posting design / gate |
|---|---|---|---|
| Wholesale sale draft | `commercial_sales` | buyer, quantity, unit price, total amount, status DRAFT | No GL effect while draft. |
| Approved sale and issued invoice | `commercial_sales` + `commercial_sales_invoices` | invoice number, sale date, quantity, price, gross/net/credited amounts, receivable, dispatch allocations | One revenue/receivable event at the approved recognition point, subject to NC 03 and contract/delivery terms. Stock cost is a separate inventory/COGS posting. |
| Dispatch | `commercial_stock_movements` with source sale ID | lot, quantity, tank/location, owner, movement type DISPATCH | Physical inventory event; do not treat it as revenue if invoice approval already recognized revenue. |
| Buyer cash payment | `commercial_sale_payments` | amount, date, method, reference, invoice/sale IDs | Cash/bank debit and receivable credit. This is distinct from invoice revenue. |
| Payment reversal | `commercial_payment_reversals` | original payment ID, invoice ID, reversal amount, evidence and reason | Reverse cash settlement only; do not reverse revenue unless a separate credit note/return event exists. |
| Buyer credit note | `commercial_credit_notes` | credit note source document and amount/allocations | Adjust revenue/receivable and possibly stock only according to approved reason and returned-goods state. |
| Credit applied to invoice | `commercial_buyer_credit_applications` plus `commercial_buyer_credit_ledger` | amount and source credit-note allocations | Settles receivable by applying existing buyer credit; not a cash receipt and not new revenue. |
| Sale return | `commercial_sale_returns` + return lot + stock movement | returned quantity, original sale/invoice, returned lot and acceptance state | Separate sales-return/credit and inventory-restoration policy; do not assume every physical return is accepted or saleable. |
| Return rejection | `commercial_sale_return_rejections` / buyer return rejection records | rejected quantity/reason/source reference | No automatic revenue reversal or inventory restoration without the exact accepted/rejected lifecycle. |

The wholesale sale approval service creates a sales invoice with `tax_treatment_status = NOT_CONFIGURED`, records FIFO dispatch allocations and posts stock movements in the same transaction. This is a clear tax configuration gate: no tax amount or tax treatment should be inferred.

## 5. Oil/olive purchases from custody owners

| Business event | Authoritative source | Financial facts | Posting design / gate |
|---|---|---|---|
| Customer-owned olive/oil purchase agreement | `commercial_oil_purchase_documents` | product kind, agreed amount, initial paid amount, outstanding amount, payment status, quantity and unit price | Confirm when title transfers from customer to mill. Only then recognize company inventory and supplier payable/consideration. |
| Initial payment | `commercial_oil_purchase_payments` | payment amount, date, method, reference, source movement | Payment event separate from purchase recognition. |
| Subsequent payment | `commercial_oil_purchase_payments` | amount, date, method, reference, purchase ID | Post payment delta against the payable. |
| Internal ownership movement | `commercial_internal_movements` plus `commercial_stock_movements` | source/destination owner, product, quantity, consideration type/amount | Ownership transfer must not be mistaken for physical stock receipt/consumption. Recognize financial impact only if transfer is a sale/purchase and title actually changes. |

The service supports both OLIVE and OIL product kinds. Quantity and unit-price fields differ by product. Keep units explicit: olive quantity in kg; oil quantity may be litres or kg depending on the schema/product path. Do not silently compare or aggregate incompatible units.

## 6. Customer custody and pressing

| Business event | Authoritative source | Financial facts | Posting design / gate |
|---|---|---|---|
| Customer olive custody receipt | `commercial_customer_custody_receipts` | customer owner, source load, olive lot, quantity, receipt date and location | Custody/quantity subledger only by default. Not company-owned inventory or purchase merely because it is received physically. |
| Customer custody release | `commercial_customer_custody_releases` | owner, lot, quantity, destination tank/location and release | Custody quantity reduction/transfer; no revenue/cash effect unless a separately documented service or sale event exists. |
| Traditional pressing invoice | `invoices` linked to load | pressing service amount and receipts | Service revenue and customer receivable; distinguish from ownership of olives/oil. |
| Customer-owned oil held in tanks | lot/stock balances by owner | physical quantity, location and ownership | Maintain owner-level stock records. Never include customer-owned balance in company inventory valuation/COGS. |

A pressing service may create revenue while the underlying oil remains customer property. The accounting engine must keep these economic events separate.

## 7. Production, stock and inventory valuation

| Business event | Authoritative source | Financial facts | Posting design / gate |
|---|---|---|---|
| Production run | `commercial_production_runs` | olive input quantity, actual oil output, run date, tank/output lot and traceability | Quantity/production record. Cost capitalization requires approved NC 04 policy and allocation of eligible conversion costs. |
| Olive consumption | `commercial_stock_movements` | lot, owner, quantity and source production run | Reduce the correct owner/product inventory subledger; customer-owned material is not mill inventory. |
| Oil output receipt | `commercial_stock_movements` + output lot | output quantity, lot, tank/location, owner | Add output to the correct ownership subledger; value using approved cost-layer method, not assumed extraction percentage. |
| Tank transfer / internal movement | `commercial_stock_movements` / `commercial_internal_movements` | movement kind, source/destination, lot, quantity, owner | Usually balance-sheet reclassification by location, not income/expense. Ownership change may have separate accounting only if title changes. |
| Stock adjustment / loss | stock adjustment/movement records | quantity, reason, approval and source | Require independent count/reason and approval; map to loss/claim only after policy confirmation. |

The current source has stock-ledger movement services and stock balances. The future GL must reconcile inventory valuation to quantity subledgers by lot, product, location and owner. A quantity movement must never create revenue merely because it changes a tank.

## 8. Other financial event families to register before GL build

The codebase includes separate source collections for:
- `commercial_buyer_credit_ledger`, `commercial_buyer_credit_applications`, `commercial_credit_notes`
- `commercial_payment_reversals`, `commercial_sale_payments`
- `commercial_supplier_olive_purchase_payments`, `commercial_oil_purchase_payments`
- `accounting_expenses`, `accounting_passive_incomes` (legacy operational entry endpoints; verify live data and lifecycle)
- fixed assets, payroll, bank statements and tax returns: no complete integrated subledger was identified in the reviewed accounting module.

Each family needs a dedicated source-event adapter, unique source ID, event type, event date, actor, currency, amount basis, reversal/void semantics and an approved journal template.

## 9. Manual passive income and expense entries

| Event | Authoritative source | Current behavior | Posting design / gate |
|---|---|---|---|
| Manual passive income | `accounting_passive_incomes` | Admin creates one season-scoped record with date, category, description, amount, payment method, notes and creator; DELETE physically removes it | Treat only as a manually entered source record after evidence/account classification. Determine whether it is income earned or cash received; current schema does not distinguish accrual from settlement. Replace delete with void/reversal and retain receipt evidence. |
| Manual operating expense | `accounting_expenses` | Admin creates season-scoped expense with date, category, amount, payment method, beneficiary, notes and creator; DELETE physically removes it | Determine expense recognition versus cash payment and supplier payable. Add counterparty/document evidence, payment reference and cash/bank account. Replace delete with void/reversal. |
| Manual other outflow | `accounting_expenses` (shared collection path) | The helper supports a supplier field for non-expense outflow types, but current mounted expense route uses the expense type path | Verify all callers and data shape before migration; do not assume the supplier branch is active or populated. |

These manual-entry endpoints are operational season-based records, not a double-entry subledger. They currently do not provide a separate accrual event and settlement event, a stable external receipt/document number, or an immutable correction lifecycle. Do not auto-post them to the GL until these fields and policies are designed.

## 10. Cross-cutting source-of-truth rules

1. Invoice revenue is posted from the invoice recognition event, not again from its payments.
2. Cash receipt is posted from the payment event, not from a cumulative paid snapshot.
3. Supplier payable is posted from approved purchase/ownership-transfer event; payment is separate.
4. Customer credit application is not cash and not revenue.
5. Payment reversal is not automatically a sales return or revenue reversal.
6. Stock movement changes inventory quantity/ownership/location; it is not itself revenue.
7. Customer custody remains off company-owned inventory unless legal title changes.
8. Production output is measured actual quantity; never infer it from an assumed yield.
9. Every source adapter must be idempotent on immutable source-event identity.
10. Every posted event must be traceable back to the source document and its audit trail.

## 11. Readiness blockers before accounting postings

- [ ] Traditional invoice repricing/deletion lifecycle replaced by credit/debit adjustments and reversals.
- [ ] Legacy `paid_amount` replacement API retired or restricted to controlled reconciliation.
- [ ] Traditional payment events receive stable immutable IDs and evidence fields.
- [ ] Decimal-safe quantity/money handling is consistent through traditional invoices and client statements.
- [ ] NC 03 revenue recognition and tax classification approved for pressing, oil sales and by-products.
- [ ] NC 04 inventory valuation and production conversion-cost allocation approved.
- [ ] Customer custody/title-transfer contracts and loss policy documented.
- [ ] All GS return/credit-note states mapped, including rejection and partial acceptance.
- [ ] Expense/passive-income deletion replaced with cancellation/reversal lifecycle and accrual-versus-payment semantics.
- [ ] Payment method mapped to explicit cash/bank accounts; cheque/transfer references and evidence retained.
- [ ] Fiscal year, opening balances and approved chart configured.
- [ ] Source-event adapters tested for retries, concurrency, reversal and duplicate posting.

## 12. Scope limitations

This register is based on static source inspection. It does not prove every endpoint, every legacy data shape, or every collection's live population. Before migration/posting, compare the register with live documents and all route/service writers, then validate each mapping with the Tunisian accountant. No GL collection or posting API is implemented by this document.
