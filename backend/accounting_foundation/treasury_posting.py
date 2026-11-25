"""Explicit, idempotent recording of treasury movements from canonical GS payments."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import NAMESPACE_URL, uuid5

from bson.decimal128 import Decimal128

from .treasury_preview import build_treasury_movement_preview

SourceType = Literal["GS_SALE_PAYMENT", "GS_SUPPLIER_PAYMENT"]


def _stable_id(namespace: str, season_code: str, source_type: str, source_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"oroverde:treasury:{namespace}:{season_code}:{source_type}:{source_id}"))


def build_movement_document(
    candidate: dict[str, Any], *, season_code: str, actor_user_id: str,
    movement_id: str, recorded_at: datetime,
) -> dict[str, Any]:
    """Build an immutable operational movement; never mutate balances or source payments."""
    if candidate.get("eligibility") != "ELIGIBLE_FOR_REVIEW":
        raise ValueError("Treasury source payment is not eligible: " + ",".join(candidate.get("blocking_reasons") or []))
    method = candidate.get("payment_method")
    if method not in {"CASH", "BANK_TRANSFER", "CHEQUE"}:
        raise ValueError("Unsupported treasury payment method")
    status = {
        "CASH": "CASH_RECORDED",
        "BANK_TRANSFER": "PENDING_BANK_CONFIRMATION",
        "CHEQUE": "PENDING_CHEQUE_CLEARANCE",
    }[method]
    direction = candidate["direction"]
    return {
        "id": movement_id,
        "season_code": season_code,
        "source_type": candidate["source_type"],
        "source_id": candidate["source_id"],
        "source_document_number": candidate.get("source_document_number"),
        "source_party_id": candidate.get("party_id"),
        "movement_kind": "SOURCE_PAYMENT",
        "direction": direction,
        "movement_type": "RECEIPT" if direction == "IN" else "DISBURSEMENT",
        "account_id": candidate["account_id"],
        "account_name_snapshot": candidate.get("account_name"),
        "account_type": candidate.get("account_type"),
        "amount_tnd": Decimal128(candidate["amount"]),
        "currency": "TND",
        "movement_date": candidate["business_date"],
        "payment_method": method,
        "external_reference": candidate.get("reference"),
        "settlement_status": status,
        "reconciliation_status": "RECONCILED" if method == "CASH" else "UNRECONCILED",
        "opening_balance_applied": False,
        "gl_posting_status": "NOT_POSTED",
        "recorded_by": actor_user_id,
        "recorded_at": recorded_at,
    }


async def record_source_payment_movement(
    db: Any, *, source_type: SourceType, source_id: str, season_code: str,
    actor_user_id: str, recorded_at: datetime, session: Any,
) -> dict[str, Any]:
    """Record one explicit movement for one canonical payment, atomically with its audit event."""
    movement_collection = db["accounting_treasury_movements"]
    existing = await movement_collection.find_one(
        {"season_code": season_code, "source_type": source_type, "source_id": source_id}, {"_id": 0}, session=session
    )
    if existing:
        return existing

    if source_type == "GS_SALE_PAYMENT":
        source = await db["commercial_sale_payments"].find_one(
            {"id": source_id, "season_code": season_code}, {"_id": 0}, session=session
        )
        if not source:
            raise LookupError("GS sale payment not found in the active season")
        invoice = await db["commercial_sales_invoices"].find_one(
            {"id": source.get("invoice_id"), "season_code": season_code},
            {"_id": 0, "id": 1, "sale_id": 1, "buyer_id": 1}, session=session,
        )
        account = await db["accounting_treasury_accounts"].find_one(
            {"id": source.get("treasury_account_id")}, {"_id": 0}, session=session
        ) if source.get("treasury_account_id") else None
        preview = build_treasury_movement_preview(
            sale_payments=[source], sale_invoices=[invoice] if invoice else [],
            treasury_accounts=[account] if account else [],
        )
    else:
        source = await db["commercial_supplier_olive_purchase_payments"].find_one(
            {"id": source_id, "season_code": season_code}, {"_id": 0}, session=session
        )
        if not source:
            raise LookupError("GS supplier payment not found in the active season")
        purchase = await db["commercial_olive_purchases"].find_one(
            {"id": source.get("purchase_id"), "season_code": season_code},
            {"_id": 0, "id": 1, "status": 1, "supplier_id": 1}, session=session,
        )
        account = await db["accounting_treasury_accounts"].find_one(
            {"id": source.get("treasury_account_id")}, {"_id": 0}, session=session
        ) if source.get("treasury_account_id") else None
        preview = build_treasury_movement_preview(
            supplier_payments=[source], supplier_purchases=[purchase] if purchase else [],
            treasury_accounts=[account] if account else [],
        )

    candidates = preview["candidates"]
    if len(candidates) != 1:
        raise ValueError("Treasury proposal could not be composed safely")
    candidate = candidates[0]
    movement_id = _stable_id("movement", season_code, source_type, source_id)
    movement = build_movement_document(
        candidate, season_code=season_code, actor_user_id=actor_user_id,
        movement_id=movement_id, recorded_at=recorded_at,
    )
    movement["source_document_id"] = source.get("invoice_id") if source_type == "GS_SALE_PAYMENT" else source.get("purchase_id")
    await movement_collection.insert_one(movement, session=session)
    await db["accounting_treasury_movement_events"].insert_one({
        "id": _stable_id("event", season_code, source_type, source_id),
        "movement_id": movement_id,
        "source_type": source_type,
        "source_id": source_id,
        "account_id": movement["account_id"],
        "action": "SOURCE_PAYMENT_MOVEMENT_RECORDED",
        "actor_user_id": actor_user_id,
        "created_at": recorded_at,
        "details": {
            "direction": movement["direction"],
            "amount_tnd": movement["amount_tnd"],
            "currency": "TND",
            "payment_method": movement["payment_method"],
            "settlement_status": movement["settlement_status"],
            "reconciliation_status": movement["reconciliation_status"],
        },
    }, session=session)
    return movement
