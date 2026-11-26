"""Deterministic, read-only primitives for financial source-event adapters.

No MongoDB imports, persistence, journal posting, tax logic, or policy inference
belong in this module. Source adapters must supply facts and explicit blockers.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable


ELIGIBILITY_VALUES = {
    "ELIGIBLE_FOR_REVIEW",
    "BLOCKED",
    "INFORMATIONAL_ONLY",
    "LEGACY_UNRESOLVED",
}


def canonical_decimal(value: Any) -> str:
    """Return an exact, non-exponent decimal string; reject binary floats.

    Financial source adapters must not silently convert a Python float into an
    apparently exact monetary value. Callers should pass Decimal or a source
    string/int. Trailing fractional zeroes are normalized without rounding.
    """
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError("Financial decimals must not be supplied as bool or float")
    if not isinstance(value, (Decimal, str, int)):
        raise TypeError("Expected Decimal, string, or integer")
    try:
        number = value if isinstance(value, Decimal) else Decimal(value)
    except (InvalidOperation, ValueError):
        raise ValueError("Invalid decimal value") from None
    if not number.is_finite():
        raise ValueError("Decimal value must be finite")
    if number == 0:
        return "0"
    normalized = number.normalize()
    return format(normalized, "f")


def _canonical_value(value: Any) -> Any:
    """Convert supported values to a stable JSON representation."""
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return value
    if isinstance(value, float):
        raise TypeError("Fingerprint inputs must not contain binary floats")
    if isinstance(value, Decimal):
        return {"$decimal": canonical_decimal(value)}
    if isinstance(value, datetime):
        # Preserve the source's exact wall-clock representation when no
        # timezone is present. Do not guess UTC or local time: naive and
        # timezone-aware values must remain distinct fingerprint inputs.
        if value.tzinfo is None or value.utcoffset() is None:
            return {"$datetime_naive": value.isoformat()}
        return {"$datetime": value.isoformat()}
    if isinstance(value, date):
        return {"$date": value.isoformat()}
    if isinstance(value, dict):
        return {
            str(key): _canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    raise TypeError(f"Unsupported fingerprint value: {type(value).__name__}")


def _digest(value: Any) -> str:
    payload = json.dumps(
        _canonical_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def candidate_key(
    source_type: str,
    source_id: str,
    event_type: str,
    event_version: int = 1,
    child_event_id: str | None = None,
) -> str:
    """Build a stable key from the immutable identity of one economic event."""
    parts = (source_type, source_id, event_type)
    if any(not isinstance(part, str) or not part.strip() for part in parts):
        raise ValueError("source_type, source_id and event_type are required")
    if child_event_id is not None and (
        not isinstance(child_event_id, str) or not child_event_id.strip()
    ):
        raise ValueError("child_event_id must be null or a non-empty string")
    if isinstance(event_version, bool) or not isinstance(event_version, int) or event_version < 1:
        raise ValueError("event_version must be a positive integer")
    identity = {
        "source_type": source_type,
        "source_id": source_id,
        "child_event_id": child_event_id,
        "event_type": event_type,
        "event_version": event_version,
    }
    return _digest(identity)


def source_fingerprint(source_facts: dict[str, Any]) -> str:
    """Hash canonical source facts; this is comparison evidence, not event identity."""
    if not isinstance(source_facts, dict):
        raise TypeError("source_facts must be a dictionary")
    return _digest(source_facts)


def build_candidate_envelope(
    *,
    source_type: str,
    source_id: str,
    event_type: str,
    source_facts: dict[str, Any],
    eligibility: str,
    blocking_reasons: Iterable[str] = (),
    child_event_id: str | None = None,
    event_version: int = 1,
    adapter_version: str = "0.1.0",
    source_document_number: str | None = None,
    business_date: str | None = None,
    recorded_at: str | None = None,
    actor_id: str | None = None,
    party_ref: dict[str, Any] | None = None,
    currency: str | None = None,
    amount: Any | None = None,
    quantity: Any | None = None,
    unit: str | None = None,
    ownership: dict[str, Any] | None = None,
    dimensions: dict[str, Any] | None = None,
    source_links: Iterable[dict[str, Any]] = (),
    warnings: Iterable[str] = (),
) -> dict[str, Any]:
    """Create a versioned candidate envelope without persisting or posting it."""
    if eligibility not in ELIGIBILITY_VALUES:
        raise ValueError("Unknown candidate eligibility")
    blockers = list(blocking_reasons)
    if eligibility == "BLOCKED" and not blockers:
        raise ValueError("BLOCKED candidates require at least one blocking reason")
    if eligibility != "BLOCKED" and blockers:
        raise ValueError("Blocking reasons require BLOCKED eligibility")
    if business_date is not None:
        date.fromisoformat(business_date)
    if recorded_at is not None:
        # Require an explicit timezone so UTC/local meaning is never guessed.
        parsed = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("recorded_at must include a timezone")
    if amount is not None and not currency:
        raise ValueError("A monetary amount requires an explicit currency")
    if quantity is not None and not unit:
        raise ValueError("A quantity requires an explicit unit")

    envelope = {
        "adapter_version": adapter_version,
        "source_type": source_type,
        "source_id": source_id,
        "child_event_id": child_event_id,
        "event_type": event_type,
        "event_version": event_version,
        "candidate_key": candidate_key(
            source_type, source_id, event_type, event_version, child_event_id
        ),
        "source_document_number": source_document_number,
        "business_date": business_date,
        "recorded_at": recorded_at,
        "actor_id": actor_id,
        "party_ref": party_ref,
        "currency": currency,
        "amount": canonical_decimal(amount) if amount is not None else None,
        "quantity": canonical_decimal(quantity) if quantity is not None else None,
        "unit": unit,
        "ownership": ownership,
        "dimensions": dimensions or {},
        "source_fingerprint": source_fingerprint(source_facts),
        "eligibility": eligibility,
        "blocking_reasons": blockers,
        "source_links": list(source_links),
        "warnings": list(warnings),
    }
    return envelope
