# Inventory Valuation and Industrial Cost Accounting Audit

Project: huilerie-pro5  
Base: main at `c9ae192c853a7d1a52422d2c4bbd72880c01005a`  
Method: static source inspection; no production data changed.

## 1. Executive finding

The commercial module has a strong **quantity and ownership stock ledger**, but the inspected implementation does not yet provide an integrated **monetary inventory valuation or production-cost ledger**. It can prove how many kilograms of a lot moved, between which locations and owners, and which source document caused the movement. It cannot yet derive a defensible TND cost per kilogram of olive or oil, a production-run cost, or cost of goods sold from those stock movements.

This is a material gap for the stated target of full accounting and industrial cost accounting. Quantity reconciliation is necessary, but it is not monetary valuation.

## 2. What source currently proves

### 2.1 Olive purchase

- `commercial/services/purchases.py` stores purchase-line `quantity_kg`, `unit_price_dt`, `line_total_dt`, and purchase `total_amount_dt` as Decimal128.
- `commercial/services/purchase_approval.py` creates one olive lot per purchase line and posts a `RECEIPT` stock movement.
- The created lot stores quantity, variety, source purchase, supplier, owner, quality and status. The inspected lot document does **not** copy the purchase-line unit price, line cost, freight/handling allocation, or a carrying-value amount.
- The stock movement schema and stock-ledger service record quantity, product, lot, owner, location, source document and audit/idempotency evidence. The movement has no monetary amount or unit-cost field.

Consequently, the purchase document knows the acquisition price, but the lot/balance layer does not carry a monetary value through subsequent movements.

### 2.2 Production

- `commercial/services/production.py` records selected olive-lot input quantities, total olive input, actual oil output and extraction rate.
- It posts olive `CONSUMPTION` movements and an oil `RECEIPT` movement atomically.
- The production run and resulting oil lot carry quantities and traceability links, but the inspected documents do not carry input carrying value, conversion costs, output cost, by-product value, or a cost-allocation calculation.
- The existing extraction-rate calculation is a physical yield measure, not a cost calculation.

Therefore production currently transforms stock quantities and traceability, not inventory value.

### 2.3 Wholesale sale

- Sale approval allocates stock from available lots using FIFO dispatch allocation and posts stock dispatch movements.
- The payment ledger reconciles paid amounts, reversals, credits and receivable snapshots.
- The inspected stock movement and sale flow does not calculate or post the monetary carrying cost of dispatched oil as cost of goods sold (COGS).

FIFO quantity allocation must not be mistaken for FIFO cost valuation. A physical/traceability allocation and a valuation cost formula are separate controls, even if the business ultimately chooses FIFO for both.

### 2.4 Customer-owned custody

- The stock model explicitly distinguishes `owner.kind = MILL` from `owner.kind = CUSTOMER`.
- Customer-owned olives/oil held for pressing or custody are physical custody balances, not automatically company-owned inventory.
- A purchase/ownership transfer from a customer creates a purchase document and payable/payment evidence; only from the legally effective ownership-transfer point should the acquired product enter company-owned inventory valuation.
- Custody receipt, release, transfer between locations, or processing of customer-owned product must not be booked as the mill purchasing its own inventory merely because the product is on site.

## 3. Confirmed accounting gaps

1. **No lot carrying value:** acquisition prices remain on purchase lines; no inspected lot-level cost basis is propagated.
2. **No valued stock balance:** the stock ledger updates quantities, not TND value.
3. **No production cost sheet:** no input-cost roll-up or conversion-cost allocation is stored against a production run.
4. **No output valuation:** produced oil lots have quantity but no derived cost per kg / carrying value.
5. **No COGS event:** sale dispatch reduces quantity, but no corresponding inventory-cost relief is calculated from a valuation layer.
6. **No by-product cost treatment:** pomace/olive cake, waste, process loss and any recoverable by-products are not represented in the inspected production-cost calculation.
7. **No cost-centre allocation:** labour, electricity, fuel, water, maintenance, depreciation and other eligible conversion overheads are not assigned to production runs or periods.
8. **No reconciliation between inventory subledger and GL:** no monetary stock control account / inventory valuation subledger was found in the inspected accounting architecture.

## 4. Required target model

Keep the existing quantity stock ledger as the physical/ownership source of truth. Add a separate append-only valuation and cost subledger; do not overload physical movement quantities with accounting calculations.

Minimum records:

- **Cost layer:** product kind, lot, owner, source purchase/production, received quantity, remaining quantity, acquisition/conversion cost, currency TND, unit cost, effective date, valuation method, and source-event identity.
- **Valuation movement:** receipt, consumption, transfer, ownership acquisition/disposal, production input/output, dispatch, return, write-down and approved adjustment; each references its physical stock movement and monetary value.
- **Production cost sheet:** production run, input lot layers consumed, direct labour, energy/fuel, water, consumables, eligible overhead, by-products/recoverable outputs, process loss, allocation method, total output cost and unit cost.
- **COGS layer relief:** each dispatch allocation must identify the corresponding cost layer(s), quantity relieved and TND value; returns must restore or revalue cost consistently with the original sale/return event.
- **Reconciliation:** quantity by lot/owner/location must match the physical ledger; monetary value by company-owned product must match inventory valuation control accounts; customer custody must remain outside mill-owned inventory value.

All financial arithmetic must use Decimal/Decimal128 or an equivalent exact decimal representation. Never use binary float for inventory cost or TND amounts.

## 5. Valuation-policy decisions — do not silently assume

Before posting monetary values, the Tunisian accountant must approve the applicable NC 04 policy and document at least:

- Cost formula for interchangeable inventory (for example FIFO or weighted average), including whether it is applied consistently by product/lot/category.
- Which directly attributable acquisition costs are included in olive/oil inventory cost (transport, loading, handling, non-recoverable taxes and other eligible costs).
- Which conversion costs are included in finished-oil cost, and the normal-capacity / overhead allocation basis where relevant.
- Treatment of by-products (including pomace/olive cake), normal process loss, abnormal waste and recoverable residuals.
- Required net-realizable-value / impairment review and write-down/reversal process under the applicable Tunisian standard.
- Cost treatment for customer-owned pressing/custody, toll processing, and customer-to-mill ownership purchases.
- Cost treatment for oil returns, quality rejection, stock loss, tank mixing and transfers.

Do not infer that sales FIFO dispatch automatically establishes the statutory inventory valuation formula. Do not select weighted average or FIFO for accounting solely because the physical system uses FIFO to allocate shipments.

## 6. Operational design constraints

- Preserve one traceability code through purchase, lot, quality, production, oil lot, tank and sale; monetary valuation must not create a new operational identity.
- Tank mixing may combine physical stock from multiple lots. Preserve cost-layer identity beneath the tank balance so a sale can relieve the correct valuation layers without claiming physical source certainty that mixing removes.
- Customer-owned and mill-owned quantities must remain separate even when physically in the same facility or tank.
- A customer-to-mill purchase changes ownership and starts the mill's acquisition cost basis; it is not a second physical receipt if the stock already exists in custody.
- Transfers between mill locations/tanks move carrying value without creating revenue or expense.
- Production consumes olive carrying value and transfers eligible cost into output oil/by-product valuation; it must not expense the same olive purchase a second time.
- Sale revenue/receivable and cash receipt remain separate events from inventory cost relief/COGS.
- Every valuation event must be idempotent, append-only after posting, source-linked, auditable and reversible through explicit correction/reversal events.

## 7. Acceptance tests before cost accounting go-live

1. Purchase 1,000 kg olives at TND 2.000/kg: source purchase total TND 2,000.000 and the corresponding company-owned olive cost layer reconciles to TND 2,000.000 plus only approved attributable acquisition costs.
2. Consume 500 kg from that layer in a production run: consumed quantity and relieved input value match the selected valuation method; remaining olive quantity/value reconcile.
3. Produce oil and by-products: allocated output values plus any recognized residual/by-product value reconcile to input cost plus eligible conversion cost, subject to the approved allocation policy.
4. Dispatch 100 kg oil from a mixed tank: quantity FIFO dispatch and monetary valuation layers are independently identified and reconciled under the approved cost formula.
5. Return accepted oil: restore stock and valuation consistently with the linked original dispatch and credit note; rejected returns do not silently create saleable inventory.
6. Customer-owned custody: receipt and pressing do not create mill-owned inventory value; ownership purchase creates a new acquisition layer exactly once.
7. Tank transfer/mixing: quantity and value are conserved; no income/expense is created by an internal transfer.
8. Duplicate request/retry: no duplicate valuation layer, production cost, COGS or journal posting.
9. Legacy lots without reliable acquisition cost remain explicitly `UNVALUED_LEGACY`; never fabricate unit cost from current prices or current season averages.
10. Inventory valuation subledger total reconciles to the GL inventory control account at each fiscal-period close.

## 8. Scope and evidence limits

This is a static code audit, not a live valuation of current MongoDB stock. It does not establish the current acquisition cost of existing lots, and no live lot, stock balance, invoice or financial record was changed. The applicable valuation method and cost inclusion rules require confirmation under current Tunisian accounting standards by the company's accountant before runtime implementation.
