"""Read-only proposals for cash/bank movements from canonical GS payment events.

This module never writes to MongoDB and never changes receivable/payable balances.
A payment reversal is not evidence that money physically returned to the company.
"""
from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable


def _amount(value: Any) -> Decimal:
    if hasattr(value, "to_decimal"):
        value = value.to_decimal()
    if isinstance(value, (bool, float)) or not isinstance(value, (Decimal, str, int)):
        raise TypeError("Financial amount must be a Decimal, Decimal128, string, or integer")
    result = value if isinstance(value, Decimal) else Decimal(value)
    if not result.is_finite() or result <= 0:
        raise ValueError("Financial amount must be finite and greater than zero")
    normalized = result.quantize(Decimal("0.001"))
    if normalized != result:
        raise ValueError("Financial amount has more than three decimal places")
    return normalized


def _candidate(
    *, source_type: str, source: dict[str, Any], amount_field: str,
    date_field: str, direction: str, party_field: str, accounts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    source_id = str(source.get("id") or "").strip()
    blockers: list[str] = []
    warnings: list[str] = []
    if not source_id:
        source_id = "MISSING"
        blockers.append("SOURCE_ID_MISSING")

    try:
        amount = _amount(source.get(amount_field))
    except (TypeError, ValueError, InvalidOperation):
        amount = None
        blockers.append("AMOUNT_MISSING_OR_INVALID")

    raw_date = source.get(date_field)
    business_date = str(raw_date or "")[:10]
    try:
        date.fromisoformat(business_date)
    except (TypeError, ValueError):
        business_date = ""
        blockers.append("PAYMENT_DATE_MISSING_OR_INVALID")

    method = str(source.get("method") or source.get("payment_method") or "").upper()
    if method not in {"CASH", "BANK_TRANSFER", "CHEQUE"}:
        blockers.append("PAYMENT_METHOD_UNSUPPORTED")
    expected_type = "CASH" if method == "CASH" else "BANK"
    account_id = str(source.get("treasury_account_id") or "").strip()
    account = accounts.get(account_id) if account_id else None
    if not account_id:
        blockers.append("TREASURY_ACCOUNT_NOT_ASSIGNED")
    elif not account:
        blockers.append("TREASURY_ACCOUNT_UNKNOWN")
    else:
        if account.get("active") is not True:
            blockers.append("TREASURY_ACCOUNT_INACTIVE")
        if account.get("currency") != "TND":
            blockers.append("TREASURY_ACCOUNT_CURRENCY_NOT_TND")
        if account.get("account_type") != expected_type:
            blockers.append("TREASURY_ACCOUNT_TYPE_MISMATCH")

    if source.get("treasury_allocation_status") != "MAPPED":
        blockers.append("TREASURY_ALLOCATION_STATUS_INVALID")
    currency = str(source.get("currency") or "TND").upper()
    if currency != "TND":
        blockers.append("PAYMENT_CURRENCY_NOT_TND")
    if method in {"BANK_TRANSFER", "CHEQUE"}:
        if not str(source.get("reference") or "").strip():
            blockers.append("BANK_OR_CHEQUE_REFERENCE_MISSING")
        warnings.append("BANK_CLEARANCE_NOT_VERIFIED")

    fingerprint_material = f"{source_type}:{source_id}:MONEY_MOVEMENT"
    candidate_key = hashlib.sha256(fingerprint_material.encode("utf-8")).hexdigest()
    return {
        "candidate_key": candidate_key,
        "source_type": source_type,
        "source_id": source_id,
        "source_document_number": source.get("document_number") or source.get("payment_number"),
        "business_date": business_date or None,
        "direction": direction,
        "account_id": account_id or None,
        "account_name": account.get("name") if account else None,
        "account_type": account.get("account_type") if account else None,
        "payment_method": method or None,
        "reference": str(source.get("reference") or "").strip() or None,
        "currency": "TND" if amount is not None else None,
        "amount": format(amount, ".3f") if amount is not None else None,
        "party_id": str(source.get(party_field)) if source.get(party_field) else None,
        "eligibility": "BLOCKED" if blockers else "ELIGIBLE_FOR_REVIEW",
        "blocking_reasons": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "proposal_status": "PREVIEW_ONLY",
    }


def build_treasury_movement_preview(
    *, sale_payments: Iterable[dict[str, Any]] = (),
    supplier_payments: Iterable[dict[str, Any]] = (),
    sale_reversals: Iterable[dict[str, Any]] = (),
    sale_invoices: Iterable[dict[str, Any]] = (),
    supplier_purchases: Iterable[dict[str, Any]] = (),
    treasury_accounts: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Compose bounded source rows into non-posting treasury movement proposals."""
    account_rows = list(treasury_accounts)
    accounts = {str(row.get("id")): row for row in account_rows if row.get("id")}
    candidates: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    invoices_by_id = {str(row.get("id")): row for row in sale_invoices if row.get("id")}
    purchases_by_id = {str(row.get("id")): row for row in supplier_purchases if row.get("id")}

    for row in sale_payments:
        candidate = _candidate(
            source_type="GS_SALE_PAYMENT", source=row, amount_field="amount_dt",
            date_field="payment_date", direction="IN", party_field="buyer_id", accounts=accounts,
        )
        invoice = invoices_by_id.get(str(row.get("invoice_id") or ""))
        if not invoice:
            candidate["blocking_reasons"].append("PAYMENT_INVOICE_NOT_FOUND")
        elif not row.get("sale_id") or not invoice.get("sale_id") or row.get("sale_id") != invoice.get("sale_id"):
            candidate["blocking_reasons"].append("PAYMENT_SALE_LINK_MISMATCH")
        elif invoice.get("buyer_id"):
            candidate["party_id"] = str(invoice["buyer_id"])
        if candidate["blocking_reasons"]:
            candidate["blocking_reasons"] = sorted(set(candidate["blocking_reasons"]))
            candidate["eligibility"] = "BLOCKED"
        candidates.append(candidate)

    for row in supplier_payments:
        candidate = _candidate(
            source_type="GS_SUPPLIER_PAYMENT", source=row, amount_field="amount_tnd",
            date_field="payment_date", direction="OUT", party_field="supplier_id", accounts=accounts,
        )
        purchase = purchases_by_id.get(str(row.get("purchase_id") or ""))
        if not purchase or purchase.get("status") != "APPROVED":
            candidate["blocking_reasons"].append("SUPPLIER_PURCHASE_LINK_INVALID")
        elif not row.get("supplier_id") or not purchase.get("supplier_id") or row.get("supplier_id") != purchase.get("supplier_id"):
            candidate["blocking_reasons"].append("PAYMENT_SUPPLIER_LINK_MISMATCH")
        if candidate["blocking_reasons"]:
            candidate["blocking_reasons"] = sorted(set(candidate["blocking_reasons"]))
            candidate["eligibility"] = "BLOCKED"
        candidates.append(candidate)
    for row in sale_reversals:
        source_id = str(row.get("id") or "MISSING")
        unresolved.append({
            "source_type": "GS_SALE_PAYMENT_REVERSAL",
            "source_id": source_id,
            "source_document_number": row.get("document_number"),
            "reason": "EXTERNAL_REFUND_NOT_CONFIRMED",
            "detail": "A receivable reversal does not prove that cash or bank funds were returned.",
        })

    identities: dict[tuple[str, str], int] = {}
    for item in candidates:
        identity = (item["source_type"], item["source_id"])
        identities[identity] = identities.get(identity, 0) + 1
    for item in candidates:
        if identities[(item["source_type"], item["source_id"])] > 1:
            item["eligibility"] = "BLOCKED"
            item["blocking_reasons"] = sorted(set(item["blocking_reasons"] + ["DUPLICATE_SOURCE_EVENT_IDENTITY"]))

    eligible = sum(item["eligibility"] == "ELIGIBLE_FOR_REVIEW" for item in candidates)
    blocked = len(candidates) - eligible
    return {
        "candidates": candidates,
        "unresolved_items": unresolved,
        "summary": {
            "candidate_count": len(candidates),
            "eligible_for_review": eligible,
            "blocked": blocked,
            "unresolved_count": len(unresolved),
        },
        "read_only": True,
        "database_writes": False,
        "movement_creation_enabled": True,
        "opening_balances_used": False,
        "currency": "TND",
        "basis": "GS_PAYMENT_DOCUMENTS_ONLY",
    }
