"""Read-only adapters for traditional pressing invoices and itemized receipts.

The adapter consumes already-read source documents. It has no database handle,
does not mutate source records, and never creates a journal or a cash event from
a cumulative paid snapshot or invoice history.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from datetime import date, datetime
from typing import Any

from .normalization import build_candidate_envelope, canonical_decimal, source_fingerprint


_PAYMENT_DATE_FIELDS = ("at", "payment_date", "paid_at")
_CURRENCY_FIELDS = ("currency", "currency_code")


def _source_id(document: dict[str, Any]) -> str | None:
    value = document.get("_id")
    if value is None:
        value = document.get("id")
    if value is None or not str(value).strip():
        return None
    return str(value)


def _as_decimal(value: Any) -> Decimal:
    if hasattr(value, "to_decimal"):
        value = value.to_decimal()
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError("Binary floats and booleans are not valid financial amounts")
    if not isinstance(value, (Decimal, str, int)):
        raise TypeError("Unsupported financial amount type")
    amount = value if isinstance(value, Decimal) else Decimal(value)
    if not amount.is_finite():
        raise ValueError("Financial amount must be finite")
    return amount


def _business_date(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        # Date-only source values retain their calendar date.
        if len(raw) == 10:
            return date.fromisoformat(raw).isoformat()
        # Preserve the date written by the source; do not convert between
        # local time and UTC in this read-only adapter.
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def _recorded_at(value: Any) -> str | None:
    if not isinstance(value, str) or "T" not in value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if parsed.tzinfo is not None else None


def _currency(document: dict[str, Any]) -> str | None:
    for field in _CURRENCY_FIELDS:
        value = document.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip().upper()
    return None


def _date_value(document: dict[str, Any]) -> Any:
    return next((document.get(field) for field in _PAYMENT_DATE_FIELDS if document.get(field)), None)


def adapt_traditional_invoice(invoice: dict[str, Any]) -> dict[str, Any]:
    """Emit an unresolved invoice candidate until lifecycle and tariff policy exist."""
    if not isinstance(invoice, dict):
        raise TypeError("invoice must be a dictionary")
    invoice_id = _source_id(invoice)
    if not invoice_id:
        raise ValueError("Traditional invoice requires an immutable source ID")

    warnings = [
        "INVOICE_RECOGNITION_POLICY_NOT_APPROVED",
        "TARIFF_BASIS_NOT_APPROVED",
    ]
    amount = None
    currency = _currency(invoice)
    try:
        if invoice.get("total") is not None and currency:
            amount = _as_decimal(invoice["total"])
        elif invoice.get("total") is not None:
            warnings.append("INVOICE_CURRENCY_NOT_EXPLICIT")
    except (TypeError, ValueError, InvalidOperation):
        warnings.append("INVOICE_TOTAL_INVALID")

    business_date = _business_date(invoice.get("day"))
    if invoice.get("day") and not business_date:
        warnings.append("INVOICE_BUSINESS_DATE_INVALID_OR_UNSUPPORTED")

    facts = {
        "invoice_id": invoice_id,
        "number": invoice.get("number"),
        "load_id": invoice.get("load_id"),
        "day": invoice.get("day"),
        "total": str(invoice.get("total")) if invoice.get("total") is not None else None,
        "status": invoice.get("status"),
        "payments_count": len(invoice.get("payments", [])) if isinstance(invoice.get("payments"), list) else 0,
    }
    return build_candidate_envelope(
        source_type="TRADITIONAL_INVOICE",
        source_id=invoice_id,
        event_type="INVOICE_RECOGNIZED",
        source_facts=facts,
        eligibility="LEGACY_UNRESOLVED",
        source_document_number=str(invoice.get("number")) if invoice.get("number") is not None else None,
        business_date=business_date,
        recorded_at=_recorded_at(invoice.get("created_at")),
        actor_id=str(invoice.get("created_by")) if invoice.get("created_by") is not None else None,
        party_ref={"type": "TRADITIONAL_CLIENT", "id": str(invoice.get("client_id"))} if invoice.get("client_id") is not None else None,
        currency=currency,
        amount=amount,
        dimensions={"load_id": str(invoice.get("load_id"))} if invoice.get("load_id") is not None else {},
        source_links=[{"type": "LOAD", "id": str(invoice.get("load_id"))}] if invoice.get("load_id") is not None else [],
        warnings=warnings,
    )


def adapt_traditional_invoice_payments(invoice: dict[str, Any]) -> dict[str, Any]:
    """Adapt only stable itemized payment children; return legacy gaps separately."""
    if not isinstance(invoice, dict):
        raise TypeError("invoice must be a dictionary")
    invoice_id = _source_id(invoice)
    if not invoice_id:
        raise ValueError("Traditional invoice requires an immutable source ID")

    raw_payments = invoice.get("payments")
    payments = raw_payments if isinstance(raw_payments, list) else []
    candidates: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    itemized_total = Decimal("0")
    itemized_total_complete = True

    for index, payment in enumerate(payments):
        if not isinstance(payment, dict):
            unresolved.append({
                "source_type": "TRADITIONAL_RECEIPT",
                "source_id": invoice_id,
                "source_document_number": str(invoice.get("number")) if invoice.get("number") is not None else None,
                "reason": "PAYMENT_CHILD_NOT_AN_OBJECT",
                "source_fingerprint": source_fingerprint({"value": str(payment)}),
            })
            itemized_total_complete = False
            continue

        payment_id = _source_id(payment)
        amount_value = payment.get("amount")
        amount = None
        warnings: list[str] = []
        try:
            if amount_value is not None:
                amount = _as_decimal(amount_value)
                itemized_total += amount
            else:
                warnings.append("PAYMENT_AMOUNT_MISSING")
                itemized_total_complete = False
        except (TypeError, ValueError, InvalidOperation):
            warnings.append("PAYMENT_AMOUNT_INVALID")
            itemized_total_complete = False

        payment_currency = _currency(payment)
        if amount is not None and not payment_currency:
            warnings.append("PAYMENT_CURRENCY_NOT_EXPLICIT")

        payment_date_value = _date_value(payment)
        business_date = _business_date(payment_date_value)
        if payment_date_value and not business_date:
            warnings.append("PAYMENT_DATE_INVALID_OR_UNSUPPORTED")
        if not payment_date_value:
            warnings.append("PAYMENT_DATE_MISSING")

        if not payment_id:
            itemized_total_complete = False
            # Do not invent a durable payment ID from list position, amount or time.
            unresolved.append({
                "source_type": "TRADITIONAL_RECEIPT",
                "source_id": invoice_id,
                "source_document_number": str(invoice.get("number")) if invoice.get("number") is not None else None,
                "reason": "PAYMENT_CHILD_ID_MISSING",
                "observed_index": index,
                "source_fingerprint": source_fingerprint({
                    "invoice_id": invoice_id,
                    "payment": {
                        "amount": str(amount_value) if amount_value is not None else None,
                        "date": payment_date_value,
                        "by": payment.get("by"),
                        "currency": payment_currency,
                    },
                }),
            })
            continue

        eligible = amount is not None and payment_currency is not None and business_date is not None
        if not eligible:
            itemized_total_complete = False
        candidates.append(build_candidate_envelope(
            source_type="TRADITIONAL_RECEIPT",
            source_id=invoice_id,
            child_event_id=payment_id,
            event_type="PAYMENT_RECEIVED",
            source_facts={
                "invoice_id": invoice_id,
                "payment_id": payment_id,
                "amount": str(amount_value) if amount_value is not None else None,
                "currency": payment_currency,
                "payment_date": payment_date_value,
                "by": payment.get("by"),
            },
            eligibility="ELIGIBLE_FOR_REVIEW" if eligible else "LEGACY_UNRESOLVED",
            source_document_number=str(invoice.get("number")) if invoice.get("number") is not None else None,
            business_date=business_date,
            recorded_at=_recorded_at(payment.get("created_at")),
            actor_id=str(payment.get("by")) if payment.get("by") is not None else None,
            party_ref={"type": "TRADITIONAL_CLIENT", "id": str(invoice.get("client_id"))} if invoice.get("client_id") is not None else None,
            currency=payment_currency,
            amount=amount if payment_currency else None,
            source_links=[{"type": "INVOICE", "id": invoice_id}],
            warnings=warnings,
        ))

    # A cumulative invoice snapshot is a reconciliation control, never a receipt.
    aggregate = None
    if invoice.get("paid_amount") is not None:
        try:
            aggregate = _as_decimal(invoice["paid_amount"])
        except (TypeError, ValueError, InvalidOperation):
            unresolved.append({
                "source_type": "TRADITIONAL_INVOICE",
                "source_id": invoice_id,
                "source_document_number": str(invoice.get("number")) if invoice.get("number") is not None else None,
                "reason": "PAID_AMOUNT_SNAPSHOT_INVALID",
                "source_fingerprint": source_fingerprint({"paid_amount": str(invoice.get("paid_amount"))}),
            })

    if not payments and aggregate is not None and aggregate > 0:
        unresolved.append({
            "source_type": "TRADITIONAL_INVOICE",
            "source_id": invoice_id,
            "reason": "LEGACY_PAID_AGGREGATE_WITHOUT_ITEMIZED_RECEIPTS",
            "observed_amount": canonical_decimal(aggregate),
            "source_fingerprint": source_fingerprint({
                "invoice_id": invoice_id,
                "paid_amount": canonical_decimal(aggregate),
                "history_count": len(invoice.get("history", [])) if isinstance(invoice.get("history"), list) else 0,
            }),
        })
    elif payments and aggregate is not None and itemized_total_complete:
        difference = aggregate - itemized_total
        if difference != 0:
            unresolved.append({
                "source_type": "TRADITIONAL_INVOICE",
                "source_id": invoice_id,
                "source_document_number": str(invoice.get("number")) if invoice.get("number") is not None else None,
                "reason": "ITEMIZED_PAYMENTS_DO_NOT_RECONCILE_TO_PAID_SNAPSHOT",
                "observed_amount": canonical_decimal(difference),
                "source_fingerprint": source_fingerprint({
                    "invoice_id": invoice_id,
                    "paid_amount": canonical_decimal(aggregate),
                    "itemized_total": canonical_decimal(itemized_total),
                }),
            })

    history = invoice.get("history")
    if isinstance(history, list) and history:
        unresolved.append({
            "source_type": "TRADITIONAL_INVOICE",
            "source_id": invoice_id,
            "reason": "INVOICE_HISTORY_IS_AUDIT_EVIDENCE_NOT_RECEIPTS",
            "observed_count": len(history),
            "source_fingerprint": source_fingerprint({"invoice_id": invoice_id, "history_count": len(history)}),
        })

    return {
        "candidate_events": candidates,
        "unresolved_items": unresolved,
        "itemized_payment_total": canonical_decimal(itemized_total) if itemized_total_complete else None,
        "paid_amount_snapshot": canonical_decimal(aggregate) if aggregate is not None else None,
        "history_used_as_receipts": False,
        "read_only": True,
    }
