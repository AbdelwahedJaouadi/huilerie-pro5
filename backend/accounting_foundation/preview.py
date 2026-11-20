"""Pure composition of read-only accounting source adapters into a preview."""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from .commercial import adapt_gs_olive_purchase, adapt_gs_supplier_payments
from .sales import adapt_gs_sales
from .normalization import source_fingerprint
from .traditional import adapt_traditional_invoice, adapt_traditional_invoice_payments


def build_reconciliation_preview(
    *,
    traditional_invoices: Iterable[dict[str, Any]] = (),
    gs_purchases: Iterable[dict[str, Any]] = (),
    supplier_payments: Iterable[dict[str, Any]] = (),
    lots: Iterable[dict[str, Any]] = (),
    stock_movements: Iterable[dict[str, Any]] = (),
    gs_sales_invoices: Iterable[dict[str, Any]] = (),
    gs_sale_payments: Iterable[dict[str, Any]] = (),
    gs_sale_reversals: Iterable[dict[str, Any]] = (),
    treasury_accounts: Iterable[dict[str, Any]] = (),
    check_gs_sale_payment_snapshots: bool = True,
) -> dict[str, Any]:
    """Compose source adapters without database access or persistence."""
    invoices = list(traditional_invoices)
    purchases = list(gs_purchases)
    payments = list(supplier_payments)
    lot_rows = list(lots)
    movement_rows = list(stock_movements)
    sale_invoices, sale_payments, sale_reversals = list(gs_sales_invoices), list(gs_sale_payments), list(gs_sale_reversals)

    candidate_events: list[dict[str, Any]] = []
    unresolved_items: list[dict[str, Any]] = []

    for invoice in invoices:
        invoice_id = str(invoice.get("_id") or invoice.get("id") or "")
        if not invoice_id:
            unresolved_items.append({
                "source_type": "TRADITIONAL_INVOICE",
                "reason": "INVOICE_IMMUTABLE_SOURCE_ID_MISSING",
                "source_fingerprint": source_fingerprint({
                    "number": invoice.get("number"),
                    "load_id": invoice.get("load_id"),
                    "day": invoice.get("day"),
                }),
            })
            continue
        candidate_events.append(adapt_traditional_invoice(invoice))
        result = adapt_traditional_invoice_payments(invoice)
        candidate_events.extend(result["candidate_events"])
        unresolved_items.extend(result["unresolved_items"])

    payments_by_purchase: dict[str, list[dict[str, Any]]] = {}
    for payment in payments:
        purchase_id = str(payment.get("purchase_id") or "")
        payments_by_purchase.setdefault(purchase_id, []).append(payment)

    lots_by_id = {
        str(item.get("_id") or item.get("id")): item
        for item in lot_rows if item.get("_id") is not None or item.get("id") is not None
    }
    movements_by_id = {
        str(item.get("_id") or item.get("id")): item
        for item in movement_rows if item.get("_id") is not None or item.get("id") is not None
    }

    for purchase in purchases:
        purchase_id = str(purchase.get("_id") or purchase.get("id") or "")
        if not purchase_id:
            unresolved_items.append({
                "source_type": "GS_OLIVE_PURCHASE",
                "reason": "PURCHASE_IMMUTABLE_SOURCE_ID_MISSING",
                "source_fingerprint": source_fingerprint({
                    "document_number": purchase.get("document_number"),
                    "purchase_date": purchase.get("purchase_date"),
                    "supplier_id": purchase.get("supplier_id"),
                }),
            })
            continue
        purchase_lots = [
            lots_by_id[str(item)]
            for item in purchase.get("lot_ids", [])
            if str(item) in lots_by_id
        ] if isinstance(purchase.get("lot_ids"), list) else []
        purchase_movements = [
            movements_by_id[str(item)]
            for item in purchase.get("receipt_movement_ids", [])
            if str(item) in movements_by_id
        ] if isinstance(purchase.get("receipt_movement_ids"), list) else []
        purchase_result = adapt_gs_olive_purchase(
            purchase, lots=purchase_lots, movements=purchase_movements
        )
        candidate_events.append(purchase_result["candidate_event"])
        payment_result = adapt_gs_supplier_payments(
            payments_by_purchase.get(purchase_id, []), purchase=purchase
        )
        candidate_events.extend(payment_result["candidate_events"])
        unresolved_items.extend(payment_result["unresolved_items"])

    sales_result = adapt_gs_sales(sale_invoices, sale_payments, sale_reversals, treasury_accounts=treasury_accounts, check_payment_snapshots=check_gs_sale_payment_snapshots)
    candidate_events.extend(sales_result["candidate_events"])
    unresolved_items.extend(sales_result["unresolved_items"])

    source_counts = Counter(event.get("source_type", "UNKNOWN") for event in candidate_events)
    candidate_keys = [
        event.get("candidate_key") for event in candidate_events
        if event.get("candidate_key")
    ]
    duplicate_keys = sorted(
        key for key, count in Counter(candidate_keys).items() if count > 1
    )
    for key in duplicate_keys:
        for event in candidate_events:
            if event.get("candidate_key") == key:
                event["eligibility"] = "BLOCKED"
                reasons = list(event.get("blocking_reasons") or [])
                if "DUPLICATE_CANDIDATE_EVENT_IDENTITY" not in reasons:
                    reasons.append("DUPLICATE_CANDIDATE_EVENT_IDENTITY")
                event["blocking_reasons"] = reasons
        unresolved_items.append({
            "source_type": "ACCOUNTING_PREVIEW",
            "reason": "DUPLICATE_CANDIDATE_EVENT_IDENTITY",
            "candidate_key": key,
            "observed_count": candidate_keys.count(key),
        })
    eligibility_counts = Counter(
        event.get("eligibility", "UNKNOWN") for event in candidate_events
    )
    unresolved_counts = Counter(
        item.get("reason", "UNKNOWN") for item in unresolved_items
    )

    return {
        "candidate_events": candidate_events,
        "unresolved_items": unresolved_items,
        "summary": {
            "candidate_event_count": len(candidate_events),
            "unresolved_item_count": len(unresolved_items),
            "eligibility_counts": dict(eligibility_counts),
            "source_counts": dict(source_counts),
            "unresolved_reason_counts": dict(unresolved_counts),
            "duplicate_candidate_key_count": len(duplicate_keys),
        },
        "read_only": True,
        "database_writes": False,
        "posting_enabled": False,
        "accounting_basis": "READ_ONLY_SOURCE_RECONCILIATION_PREVIEW",
    }
