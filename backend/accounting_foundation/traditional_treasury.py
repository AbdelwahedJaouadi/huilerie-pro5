"""Explicit treasury movement recording for newly-created traditional invoice receipts.

Historical invoice payment children are deliberately not backfilled or inferred.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from bson.decimal128 import Decimal128


def _identity(kind: str, season_code: str, payment_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"oroverde:treasury:{kind}:{season_code}:TRADITIONAL_RECEIPT:{payment_id}"))


async def record_traditional_receipt_movement(
    db: Any, *, invoice: dict, payment: dict, account: dict,
    season_code: str, actor_user_id: str, recorded_at: datetime, session: Any,
) -> dict:
    """Insert one immutable cash/bank receipt movement in the caller's transaction."""
    payment_id = str(payment.get("id") or "").strip()
    if not payment_id:
        raise ValueError("Traditional receipt requires a stable payment ID")
    method = str(payment.get("method") or "").upper()
    expected_type = "CASH" if method == "CASH" else "BANK"
    if method not in {"CASH", "BANK_TRANSFER", "CHEQUE"}:
        raise ValueError("Unsupported payment method")
    if account.get("active") is not True or account.get("currency") != "TND" or account.get("account_type") != expected_type:
        raise ValueError("Treasury account is inactive or incompatible")
    if str(payment.get("currency") or "TND").upper() != "TND":
        raise ValueError("Traditional receipt currency must be TND")
    amount = payment.get("amount")
    if hasattr(amount, "to_decimal"):
        amount = amount.to_decimal()
    from decimal import Decimal
    amount = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    if not amount.is_finite() or amount <= 0 or amount.quantize(Decimal("0.001")) != amount:
        raise ValueError("Invalid traditional receipt amount")
    payment_date = payment.get("at")
    if isinstance(payment_date, datetime):
        payment_date = payment_date.date().isoformat()
    else:
        payment_date = str(payment_date or "")[:10]
    from datetime import date
    date.fromisoformat(payment_date)

    movement_id = _identity("movement", season_code, payment_id)
    existing = await db.accounting_treasury_movements.find_one(
        {"season_code": season_code, "source_type": "TRADITIONAL_RECEIPT", "source_id": payment_id},
        {"_id": 0}, session=session,
    )
    if existing:
        return existing

    settlement = {
        "CASH": "CASH_RECORDED",
        "BANK_TRANSFER": "PENDING_BANK_CONFIRMATION",
        "CHEQUE": "PENDING_CHEQUE_CLEARANCE",
    }[method]
    movement = {
        "id": movement_id, "season_code": season_code,
        "source_type": "TRADITIONAL_RECEIPT", "source_id": payment_id,
        "source_document_id": invoice.get("id"),
        "source_document_number": invoice.get("number"),
        "source_party_id": invoice.get("client_id"),
        "movement_kind": "SOURCE_PAYMENT", "direction": "IN", "movement_type": "RECEIPT",
        "account_id": account["id"], "account_name_snapshot": account.get("name"),
        "account_type": account.get("account_type"), "amount_tnd": Decimal128(amount),
        "currency": "TND", "movement_date": payment_date, "payment_method": method,
        "external_reference": payment.get("reference"), "settlement_status": settlement,
        "reconciliation_status": "UNRECONCILED", "opening_balance_applied": False,
        "gl_posting_status": "NOT_POSTED", "recorded_by": actor_user_id,
        "recorded_at": recorded_at,
    }
    await db.accounting_treasury_movements.insert_one(movement, session=session)
    await db.accounting_treasury_movement_events.insert_one({
        "id": _identity("event", season_code, payment_id), "movement_id": movement_id,
        "source_type": "TRADITIONAL_RECEIPT", "source_id": payment_id,
        "account_id": account["id"], "action": "SOURCE_PAYMENT_MOVEMENT_RECORDED",
        "actor_user_id": actor_user_id, "created_at": recorded_at,
        "details": {"direction": "IN", "amount_tnd": Decimal128(amount),
                    "currency": "TND", "payment_method": method,
                    "settlement_status": settlement},
    }, session=session)
    return movement
