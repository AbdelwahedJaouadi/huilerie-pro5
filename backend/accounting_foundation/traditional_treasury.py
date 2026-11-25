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
        "reconciliation_status": "RECONCILED" if method == "CASH" else "UNRECONCILED", "opening_balance_applied": False,
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
                    "settlement_status": settlement,
                    "reconciliation_status": movement["reconciliation_status"]},
    }, session=session)
    return movement


async def confirm_traditional_cheque_encashment(
    db: Any, *, movement_id: str, season_code: str, encashment_date: str,
    bank_reference: str, actor_user_id: str, confirmed_at: datetime, session: Any,
) -> dict:
    """Confirm a cheque already verified on the bank statement; update its original movement once."""
    from datetime import date
    from uuid import uuid4

    try:
        normalized_date = date.fromisoformat(str(encashment_date)).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid cheque encashment date") from exc
    reference = str(bank_reference or "").strip()
    if not reference or len(reference) > 120:
        raise ValueError("A valid bank statement reference is required")

    movement = await db.accounting_treasury_movements.find_one(
        {"id": movement_id, "season_code": season_code}, {"_id": 0}, session=session,
    )
    if not movement:
        raise LookupError("Treasury movement not found in the active season")
    if (movement.get("source_type") not in {"TRADITIONAL_RECEIPT", "GS_SALE_PAYMENT"}
            or movement.get("payment_method") != "CHEQUE"
            or movement.get("direction") != "IN"
            or movement.get("account_type") != "BANK"):
        raise ValueError("Only an incoming traditional or GS sale cheque linked to a bank account can be confirmed")
    if movement.get("settlement_status") != "PENDING_CHEQUE_CLEARANCE":
        if (movement.get("settlement_status") == "CHEQUE_CLEARED"
                and movement.get("bank_statement_reference") == reference
                and movement.get("cheque_encashment_date") == normalized_date):
            return movement
        raise ValueError("Cheque is not pending clearance or was already confirmed differently")

    update = await db.accounting_treasury_movements.update_one(
        {"id": movement_id, "season_code": season_code,
         "source_type": movement.get("source_type"), "payment_method": "CHEQUE",
         "direction": "IN", "settlement_status": "PENDING_CHEQUE_CLEARANCE"},
        {"$set": {
            "settlement_status": "CHEQUE_CLEARED",
            "reconciliation_status": "RECONCILED",
            "cheque_received_date": movement.get("movement_date"),
            "movement_date": normalized_date,
            "cheque_encashment_date": normalized_date,
            "bank_statement_reference": reference,
            "cheque_encashment_confirmed_by": actor_user_id,
            "cheque_encashment_confirmed_at": confirmed_at,
        }}, session=session,
    )
    if update.matched_count != 1:
        raise ValueError("Cheque status changed concurrently; refresh and verify the movement")

    await db.accounting_treasury_movement_events.insert_one({
        "id": str(uuid4()), "movement_id": movement_id,
        "source_type": movement.get("source_type"), "source_id": movement.get("source_id"),
        "account_id": movement.get("account_id"),
        "action": "CHEQUE_ENCASHMENT_CONFIRMED",
        "actor_user_id": actor_user_id, "created_at": confirmed_at,
        "details": {
            "previous_settlement_status": "PENDING_CHEQUE_CLEARANCE",
            "new_settlement_status": "CHEQUE_CLEARED",
            "previous_reconciliation_status": movement.get("reconciliation_status", "UNRECONCILED"),
            "new_reconciliation_status": "RECONCILED",
            "previous_movement_date": movement.get("movement_date"),
            "new_movement_date": normalized_date,
            "cheque_encashment_date": normalized_date,
            "bank_statement_reference": reference,
        },
    }, session=session)
    return {**movement, "settlement_status": "CHEQUE_CLEARED",
            "reconciliation_status": "RECONCILED",
            "cheque_received_date": movement.get("movement_date"),
            "movement_date": normalized_date,
            "cheque_encashment_date": normalized_date,
            "bank_statement_reference": reference,
            "cheque_encashment_confirmed_by": actor_user_id,
            "cheque_encashment_confirmed_at": confirmed_at}
