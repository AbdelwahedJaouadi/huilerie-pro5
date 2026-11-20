"""Read-only GS olive-purchase and supplier-payment source adapters.

Purchase recognition is eligible for accountant review only after approved
purchase, line, lot, and stock-receipt evidence reconcile. Supplier settlements
are separate PAYMENT_MADE events and are never purchase-expense events.
"""
from __future__ import annotations

from datetime import date, datetime
from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable

from .normalization import build_candidate_envelope, canonical_decimal, source_fingerprint


def _decimal(value: Any) -> Decimal:
    if hasattr(value, "to_decimal"):
        value = value.to_decimal()
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError("Binary floats and booleans are not valid financial values")
    if not isinstance(value, (Decimal, str, int)):
        raise TypeError("Unsupported decimal value")
    number = value if isinstance(value, Decimal) else Decimal(value)
    if not number.is_finite():
        raise ValueError("Decimal must be finite")
    return number


def _id(document: dict[str, Any]) -> str | None:
    value = document.get("_id")
    if value is None:
        value = document.get("id")
    return str(value) if value is not None and str(value).strip() else None


def _day(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        if len(raw) == 10:
            return date.fromisoformat(raw).isoformat()
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def _recorded_at(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat() if value.tzinfo is not None else None
    if not isinstance(value, str) or "T" not in value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if parsed.tzinfo is not None else None


def _sum(values: Iterable[Any]) -> Decimal:
    return sum((_decimal(value) for value in values), Decimal("0"))


def _finding(source_type: str, source_id: str, reason: str, facts: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_type": source_type,
        "source_id": source_id,
        "reason": reason,
        "source_fingerprint": source_fingerprint(facts),
    }


def adapt_gs_olive_purchase(
    purchase: dict[str, Any],
    *,
    lots: Iterable[dict[str, Any]] = (),
    movements: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Build a purchase candidate and reconciliation findings from supplied documents."""
    if not isinstance(purchase, dict):
        raise TypeError("purchase must be a dictionary")
    purchase_id = _id(purchase)
    if not purchase_id:
        raise ValueError("GS olive purchase requires an immutable source ID")

    status = purchase.get("status")
    purchase_date = _day(purchase.get("purchase_date"))
    lines = purchase.get("lines") if isinstance(purchase.get("lines"), list) else []
    warnings: list[str] = []
    blockers: list[str] = []

    if status != "APPROVED":
        eligibility = "INFORMATIONAL_ONLY" if status in {"DRAFT", "CANCELLED"} else "LEGACY_UNRESOLVED"
        warnings.append("PURCHASE_NOT_APPROVED_NO_RECOGNIZED_STOCK_EVENT")
        if status not in {"DRAFT", "CANCELLED"}:
            warnings.append("PURCHASE_STATUS_UNRECOGNIZED")
        raw_amount = raw_quantity = None
        try:
            if purchase.get("total_amount_dt") is not None:
                raw_amount = _decimal(purchase.get("total_amount_dt"))
            if purchase.get("total_quantity_kg") is not None:
                raw_quantity = _decimal(purchase.get("total_quantity_kg"))
        except (TypeError, ValueError, InvalidOperation):
            warnings.append("PURCHASE_TOTALS_INVALID")
        return {
            "candidate_event": build_candidate_envelope(
                source_type="GS_OLIVE_PURCHASE",
                source_id=purchase_id,
                event_type="PURCHASE_RECOGNIZED",
                source_facts={
                    "purchase_id": purchase_id,
                    "status": status,
                    "document_number": purchase.get("document_number"),
                    "purchase_date": purchase.get("purchase_date"),
                    "total_amount_dt": canonical_decimal(raw_amount) if raw_amount is not None else None,
                    "total_quantity_kg": canonical_decimal(raw_quantity) if raw_quantity is not None else None,
                },
                eligibility=eligibility,
                source_document_number=str(purchase.get("document_number")) if purchase.get("document_number") else None,
                business_date=purchase_date,
                recorded_at=_recorded_at(purchase.get("created_at")),
                party_ref={"type": "COMMERCIAL_SUPPLIER", "id": str(purchase.get("supplier_id"))} if purchase.get("supplier_id") else None,
                currency="TND" if raw_amount is not None else None,
                amount=raw_amount,
                quantity=raw_quantity,
                unit="kg" if raw_quantity is not None else None,
                dimensions={"season_code": str(purchase.get("season_code"))} if purchase.get("season_code") else {},
                warnings=warnings,
            ),
            "blocking_reasons": [],
            "read_only": True,
        }

    if not purchase_date:
        blockers.append("PURCHASE_DATE_MISSING_OR_INVALID")
    if not purchase.get("supplier_id"):
        blockers.append("PURCHASE_SUPPLIER_MISSING")
    if not purchase.get("receiving_location_id"):
        blockers.append("PURCHASE_RECEIVING_LOCATION_MISSING")
    if not lines:
        blockers.append("PURCHASE_LINES_MISSING")

    try:
        declared_quantity = _decimal(purchase.get("total_quantity_kg"))
        declared_amount = _decimal(purchase.get("total_amount_dt"))
    except (TypeError, ValueError, InvalidOperation):
        declared_quantity = Decimal("0")
        declared_amount = Decimal("0")
        blockers.append("PURCHASE_TOTALS_INVALID")

    line_quantity = Decimal("0")
    line_amount = Decimal("0")
    line_facts = []
    for index, line in enumerate(lines):
        if not isinstance(line, dict):
            blockers.append("PURCHASE_LINE_INVALID")
            continue
        try:
            quantity = _decimal(line.get("quantity_kg"))
            unit_price = _decimal(line.get("unit_price_dt"))
            stored_line_total = _decimal(line.get("line_total_dt"))
            expected_line_total = (quantity * unit_price).quantize(
                Decimal("0.001"), rounding=ROUND_HALF_UP
            )
            if quantity <= 0 or unit_price < 0 or stored_line_total != expected_line_total:
                blockers.append("PURCHASE_LINE_AMOUNT_OR_QUANTITY_MISMATCH")
            line_quantity += quantity
            line_amount += stored_line_total
            line_facts.append({
                "index": index,
                "variety_id": line.get("variety_id"),
                "quantity_kg": canonical_decimal(quantity),
                "unit_price_dt": canonical_decimal(unit_price),
                "line_total_dt": canonical_decimal(stored_line_total),
            })
        except (TypeError, ValueError, InvalidOperation):
            blockers.append("PURCHASE_LINE_NUMERIC_VALUE_INVALID")

    if line_quantity != declared_quantity:
        blockers.append("PURCHASE_LINES_DO_NOT_RECONCILE_TO_PURCHASE_QUANTITY")
    if line_amount != declared_amount:
        blockers.append("PURCHASE_LINES_DO_NOT_RECONCILE_TO_PURCHASE_AMOUNT")

    lot_rows = list(lots)
    movement_rows = list(movements)
    lot_ids = purchase.get("lot_ids") if isinstance(purchase.get("lot_ids"), list) else []
    movement_ids = purchase.get("receipt_movement_ids") if isinstance(purchase.get("receipt_movement_ids"), list) else []
    if not lot_ids or len(lot_ids) != len(lines):
        blockers.append("PURCHASE_LOT_LINKS_MISSING_OR_INCOMPLETE")
    if not movement_ids or len(movement_ids) != len(lines):
        blockers.append("PURCHASE_RECEIPT_MOVEMENT_LINKS_MISSING_OR_INCOMPLETE")

    lots_by_id = {_id(item): item for item in lot_rows if isinstance(item, dict) and _id(item)}
    movements_by_id = {_id(item): item for item in movement_rows if isinstance(item, dict) and _id(item)}
    if len(lots_by_id) != len(lot_rows):
        blockers.append("DUPLICATE_OR_INVALID_PURCHASE_LOT_DOCUMENT_ID")
    if len(movements_by_id) != len(movement_rows):
        blockers.append("DUPLICATE_OR_INVALID_PURCHASE_MOVEMENT_DOCUMENT_ID")
    lot_quantity = Decimal("0")
    movement_quantity = Decimal("0")
    matched_lot_ids: set[str] = set()
    matched_movement_ids: set[str] = set()

    for index, line in enumerate(lines):
        if index >= len(lot_ids) or index >= len(movement_ids) or not isinstance(line, dict):
            continue
        lot_id = str(lot_ids[index])
        movement_id = str(movement_ids[index])
        lot = lots_by_id.get(lot_id)
        movement = movements_by_id.get(movement_id)
        if not lot:
            blockers.append("PURCHASE_LOT_DOCUMENT_MISSING")
            continue
        if not movement:
            blockers.append("PURCHASE_RECEIPT_MOVEMENT_MISSING")
            continue
        matched_lot_ids.add(lot_id)
        matched_movement_ids.add(movement_id)

        try:
            received = _decimal(lot.get("quantity_received_kg"))
            moved = _decimal(movement.get("quantity_kg"))
            expected_line_quantity = _decimal(line.get("quantity_kg"))
            lot_quantity += received
            movement_quantity += moved
            if (
                lot.get("source_purchase_id") != purchase_id
                or lot.get("product_kind") != "OLIVE"
                or lot.get("supplier_id") != purchase.get("supplier_id")
                or (lot.get("owner") or {}).get("kind") != "MILL"
                or lot.get("variety_id") != line.get("variety_id")
                or received != expected_line_quantity
            ):
                blockers.append("PURCHASE_LOT_SOURCE_OWNER_OR_QUANTITY_MISMATCH")
            if (
                movement.get("source_document_type") != "ACH"
                or movement.get("source_document_id") != purchase_id
                or movement.get("movement_kind") != "RECEIPT"
                or movement.get("product_kind") != "OLIVE"
                or movement.get("lot_id") != lot_id
                or (movement.get("destination_owner") or {}).get("kind") != "MILL"
                or movement.get("destination_location_id") != purchase.get("receiving_location_id")
                or moved != expected_line_quantity
            ):
                blockers.append("PURCHASE_STOCK_MOVEMENT_SOURCE_OWNER_LOCATION_OR_QUANTITY_MISMATCH")
        except (TypeError, ValueError, InvalidOperation):
            blockers.append("PURCHASE_LOT_OR_MOVEMENT_QUANTITY_INVALID")

    if lot_quantity != declared_quantity:
        blockers.append("PURCHASE_LOT_RECEIPTS_DO_NOT_RECONCILE_TO_PURCHASE_QUANTITY")
    if movement_quantity != declared_quantity:
        blockers.append("PURCHASE_STOCK_MOVEMENTS_DO_NOT_RECONCILE_TO_PURCHASE_QUANTITY")
    if len(lot_ids) != len(set(str(item) for item in lot_ids)) or len(matched_lot_ids) != len(set(str(item) for item in lot_ids)):
        blockers.append("PURCHASE_LOT_LINKS_DUPLICATED_OR_UNRESOLVED")
    if len(movement_ids) != len(set(str(item) for item in movement_ids)) or len(matched_movement_ids) != len(set(str(item) for item in movement_ids)):
        blockers.append("PURCHASE_MOVEMENT_LINKS_DUPLICATED_OR_UNRESOLVED")

    source_facts = {
        "purchase_id": purchase_id,
        "status": status,
        "season_code": purchase.get("season_code"),
        "supplier_id": purchase.get("supplier_id"),
        "document_number": purchase.get("document_number"),
        "purchase_date": purchase.get("purchase_date"),
        "lines": line_facts,
        "total_quantity_kg": canonical_decimal(declared_quantity),
        "total_amount_dt": canonical_decimal(declared_amount),
        "lot_ids": [str(item) for item in lot_ids],
        "receipt_movement_ids": [str(item) for item in movement_ids],
        "receiving_location_id": purchase.get("receiving_location_id"),
        "batch_code": purchase.get("batch_code"),
    }
    eligibility = "BLOCKED" if blockers else "ELIGIBLE_FOR_REVIEW"
    candidate = build_candidate_envelope(
        source_type="GS_OLIVE_PURCHASE",
        source_id=purchase_id,
        event_type="PURCHASE_RECOGNIZED",
        source_facts=source_facts,
        eligibility=eligibility,
        blocking_reasons=blockers,
        source_document_number=str(purchase.get("document_number")) if purchase.get("document_number") else None,
        business_date=purchase_date,
        recorded_at=_recorded_at(purchase.get("created_at")),
        actor_id=str(purchase.get("approved_by")) if purchase.get("approved_by") else None,
        party_ref={"type": "COMMERCIAL_SUPPLIER", "id": str(purchase.get("supplier_id"))} if purchase.get("supplier_id") else None,
        currency="TND",
        amount=declared_amount,
        quantity=declared_quantity,
        unit="kg",
        ownership={"owner_kind": "MILL"},
        dimensions={
            "season_code": str(purchase.get("season_code")) if purchase.get("season_code") else None,
            "receiving_location_id": str(purchase.get("receiving_location_id")) if purchase.get("receiving_location_id") else None,
            "batch_code": str(purchase.get("batch_code")) if purchase.get("batch_code") else None,
        },
        source_links=(
            [{"type": "LOT", "id": str(item)} for item in lot_ids]
            + [{"type": "STOCK_MOVEMENT", "id": str(item)} for item in movement_ids]
        ),
        warnings=["VALUATION_POLICY_NOT_APPROVED_COST_LAYER_NOT_CREATED"],
    )
    return {"candidate_event": candidate, "blocking_reasons": blockers, "read_only": True}


def adapt_gs_supplier_payments(
    payments: Iterable[dict[str, Any]],
    *,
    purchase: dict[str, Any],
) -> dict[str, Any]:
    """Emit immutable supplier settlement candidates and reconcile the payable snapshot."""
    if not isinstance(purchase, dict) or not _id(purchase):
        raise ValueError("Supplier payment adapter requires its source purchase")
    purchase_id = _id(purchase)
    supplier_id = str(purchase.get("supplier_id") or "")
    purchase_status = purchase.get("status")
    purchase_total = _decimal(purchase.get("total_amount_dt", "0"))
    purchase_paid = _decimal(purchase.get("paid_amount_dt", "0"))
    outstanding = _decimal(purchase.get("outstanding_amount_dt", purchase_total - purchase_paid))
    payment_rows = list(payments)
    payment_id_counts = Counter(
        _id(item) for item in payment_rows
        if isinstance(item, dict) and _id(item)
    )
    candidates: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    paid_total = Decimal("0")
    all_payment_amounts_complete = True

    for payment in payment_rows:
        if not isinstance(payment, dict):
            unresolved.append(_finding("GS_SUPPLIER_PAYMENT", purchase_id, "PAYMENT_DOCUMENT_INVALID", {"value": str(payment)}))
            all_payment_amounts_complete = False
            continue
        payment_id = _id(payment)
        amount_value = payment.get("amount_tnd")
        payment_amount = None
        try:
            payment_amount = _decimal(amount_value)
            paid_total += payment_amount
            if payment_amount <= 0:
                raise ValueError("Payment must be positive")
        except (TypeError, ValueError, InvalidOperation):
            all_payment_amounts_complete = False
        payment_day = _day(payment.get("payment_date"))
        currency = str(payment.get("currency") or "TND").upper()
        warnings = ["TREASURY_ACCOUNT_NOT_MAPPED"]
        blockers = []
        if not payment_id:
            unresolved.append(_finding(
                "GS_SUPPLIER_PAYMENT", purchase_id, "PAYMENT_DOCUMENT_ID_MISSING",
                {"purchase_id": payment.get("purchase_id"), "amount_tnd": str(amount_value), "payment_date": payment.get("payment_date")},
            ))
            all_payment_amounts_complete = False
            continue
        if payment_id_counts.get(payment_id, 0) > 1:
            blockers.append("DUPLICATE_SUPPLIER_PAYMENT_ID")
        if payment.get("purchase_id") != purchase_id:
            blockers.append("PAYMENT_PURCHASE_LINK_MISMATCH")
        if not supplier_id or payment.get("supplier_id") != supplier_id:
            blockers.append("PAYMENT_SUPPLIER_LINK_MISMATCH")
        if purchase_status != "APPROVED":
            blockers.append("PAYMENT_LINKED_PURCHASE_NOT_APPROVED")
        if payment_amount is None or payment_amount <= 0:
            blockers.append("PAYMENT_AMOUNT_INVALID")
        if not payment_day:
            blockers.append("PAYMENT_DATE_MISSING_OR_INVALID")
        if currency != "TND":
            blockers.append("PAYMENT_CURRENCY_NOT_TND")
        eligible = not blockers
        candidates.append(build_candidate_envelope(
            source_type="GS_SUPPLIER_PAYMENT",
            source_id=payment_id,
            event_type="PAYMENT_MADE",
            source_facts={
                "payment_id": payment_id,
                "purchase_id": payment.get("purchase_id"),
                "supplier_id": payment.get("supplier_id"),
                "document_number": payment.get("document_number"),
                "amount_tnd": str(amount_value) if amount_value is not None else None,
                "payment_date": payment.get("payment_date"),
                "method": payment.get("method"),
                "reference": payment.get("reference"),
            },
            eligibility="ELIGIBLE_FOR_REVIEW" if eligible else "BLOCKED",
            blocking_reasons=blockers,
            source_document_number=str(payment.get("document_number")) if payment.get("document_number") else None,
            business_date=payment_day,
            recorded_at=_recorded_at(payment.get("created_at")),
            actor_id=str(payment.get("created_by")) if payment.get("created_by") else None,
            party_ref={"type": "COMMERCIAL_SUPPLIER", "id": supplier_id} if supplier_id else None,
            currency="TND" if currency == "TND" and payment_amount is not None else None,
            amount=payment_amount if currency == "TND" and payment_amount is not None else None,
            dimensions={"season_code": str(payment.get("season_code"))} if payment.get("season_code") else {},
            source_links=[{"type": "GS_OLIVE_PURCHASE", "id": purchase_id}],
            warnings=warnings,
        ))

    if all_payment_amounts_complete:
        if paid_total != purchase_paid:
            unresolved.append(_finding(
                "GS_OLIVE_PURCHASE", purchase_id, "SUPPLIER_PAYMENT_LEDGER_DOES_NOT_MATCH_PAID_SNAPSHOT",
                {"purchase_paid_amount_dt": canonical_decimal(purchase_paid), "payment_ledger_total": canonical_decimal(paid_total)},
            ))
        if outstanding != purchase_total - purchase_paid:
            unresolved.append(_finding(
                "GS_OLIVE_PURCHASE", purchase_id, "SUPPLIER_OUTSTANDING_SNAPSHOT_INVALID",
                {
                    "total_amount_dt": canonical_decimal(purchase_total),
                    "paid_amount_dt": canonical_decimal(purchase_paid),
                    "outstanding_amount_dt": canonical_decimal(outstanding),
                },
            ))
        if paid_total > purchase_total:
            unresolved.append(_finding(
                "GS_OLIVE_PURCHASE", purchase_id, "SUPPLIER_PAYMENT_LEDGER_EXCEEDS_PURCHASE_TOTAL",
                {"purchase_total": canonical_decimal(purchase_total), "payment_ledger_total": canonical_decimal(paid_total)},
            ))
    else:
        unresolved.append(_finding(
            "GS_OLIVE_PURCHASE", purchase_id, "SUPPLIER_PAYMENT_LEDGER_INCOMPLETE",
            {"payment_count": len(payment_rows)},
        ))

    return {
        "candidate_events": candidates,
        "unresolved_items": unresolved,
        "payment_ledger_total": canonical_decimal(paid_total) if all_payment_amounts_complete else None,
        "purchase_paid_snapshot": canonical_decimal(purchase_paid),
        "read_only": True,
        "payments_are_purchase_expenses": False,
    }
