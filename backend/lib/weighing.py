"""Exact, server-side vehicle weighing arithmetic.

This module is deliberately independent from MongoDB and HTTP handlers so the
weight contract can be tested before it is wired into intake workflows.
"""
from decimal import Decimal, InvalidOperation
from typing import Any

WEIGHT_QUANTUM = Decimal("0.001")
MAX_VEHICLE_WEIGHT_KG = Decimal("1000000")


def _weight_decimal(value: Any, field_name: str) -> Decimal:
    """Parse a kg reading without binary-float arithmetic or silent rounding."""
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{field_name}_invalid")

    try:
        # str() avoids importing a float's binary representation into Decimal.
        parsed = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError, AttributeError):
        raise ValueError(f"{field_name}_invalid") from None

    if not parsed.is_finite():
        raise ValueError(f"{field_name}_invalid")
    if parsed <= 0 or parsed > MAX_VEHICLE_WEIGHT_KG:
        raise ValueError(f"{field_name}_out_of_range")

    try:
        quantized = parsed.quantize(WEIGHT_QUANTUM)
    except InvalidOperation:
        raise ValueError(f"{field_name}_invalid_precision") from None
    if quantized != parsed:
        raise ValueError(f"{field_name}_invalid_precision")

    return quantized


def validate_weight_kg(value: Any, field_name: str = "olive_weight") -> Decimal:
    """Validate a standalone kg reading without accepting booleans or rounding."""
    return _weight_decimal(value, field_name)


def derive_net_weight_kg(gross_weight: Any, tare_weight: Any) -> Decimal:
    """Return net kg from validated gross/tare readings; never accept client net."""
    gross = _weight_decimal(gross_weight, "gross_weight")
    tare = _weight_decimal(tare_weight, "tare_weight")
    if gross <= tare:
        raise ValueError("gross_must_exceed_tare")
    return (gross - tare).quantize(WEIGHT_QUANTUM)

def weight_measurement_audit_snapshot(measurement: dict | None) -> dict | None:
    """Return a BSON-safe, immutable audit snapshot of the original weigh-in."""
    if not measurement:
        return None

    def decimal_text(key: str) -> str | None:
        value = measurement.get(key)
        if value is None:
            return None
        to_decimal = getattr(value, "to_decimal", None)
        if callable(to_decimal):
            value = to_decimal()
        return str(value)

    return {
        "gross_kg": decimal_text("gross_kg"),
        "tare_kg": decimal_text("tare_kg"),
        "net_kg": decimal_text("net_kg"),
        "measured_at": measurement.get("measured_at"),
        "operator_user_id": measurement.get("operator_user_id"),
        "operator_username": measurement.get("operator_username"),
        "source": measurement.get("source"),
        "correction_of": measurement.get("correction_of"),
    }
