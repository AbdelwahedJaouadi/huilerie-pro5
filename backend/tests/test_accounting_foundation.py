from datetime import datetime, timezone
from decimal import Decimal

import pytest

from accounting_foundation import (
    build_candidate_envelope,
    candidate_key,
    canonical_decimal,
    source_fingerprint,
)


def test_canonical_decimal_is_exact_and_normalized():
    assert canonical_decimal(Decimal("0012.3400")) == "12.34"
    assert canonical_decimal("0.000") == "0"
    assert canonical_decimal(17) == "17"


@pytest.mark.parametrize("value", [True, 1.25, float("nan"), float("inf")])
def test_canonical_decimal_rejects_binary_float_and_bool(value):
    with pytest.raises(TypeError):
        canonical_decimal(value)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_canonical_decimal_rejects_non_finite_strings(value):
    with pytest.raises(ValueError):
        canonical_decimal(value)


def test_candidate_key_is_stable_and_child_event_sensitive():
    first = candidate_key("TRADITIONAL_RECEIPT", "inv-1", "PAYMENT_RECEIVED", 1, "pay-1")
    same = candidate_key("TRADITIONAL_RECEIPT", "inv-1", "PAYMENT_RECEIVED", 1, "pay-1")
    other_child = candidate_key("TRADITIONAL_RECEIPT", "inv-1", "PAYMENT_RECEIVED", 1, "pay-2")
    assert first == same
    assert first != other_child


def test_source_fingerprint_ignores_mapping_order_but_not_values():
    left = {"amount": Decimal("10.00"), "date": "2026-11-20"}
    right = {"date": "2026-11-20", "amount": Decimal("10")}
    changed = {"date": "2026-11-20", "amount": Decimal("11")}
    assert source_fingerprint(left) == source_fingerprint(right)
    assert source_fingerprint(left) != source_fingerprint(changed)


def test_source_fingerprint_accepts_naive_and_aware_datetimes_distinctly():
    naive = datetime(2026, 11, 20)
    aware = datetime(2026, 11, 20, tzinfo=timezone.utc)

    naive_fingerprint = source_fingerprint({"created_at": naive})
    assert naive_fingerprint == source_fingerprint({"created_at": naive})
    assert naive_fingerprint != source_fingerprint({"created_at": aware})
    assert naive_fingerprint != source_fingerprint({
        "created_at": naive.isoformat()
    })


def test_envelope_is_read_only_candidate_and_preserves_explicit_blocker():
    event = build_candidate_envelope(
        source_type="TRADITIONAL_RECEIPT",
        source_id="invoice-1",
        child_event_id=None,
        event_type="PAYMENT_RECEIVED",
        source_facts={"amount": Decimal("12.500"), "paid_amount": "12.500"},
        eligibility="LEGACY_UNRESOLVED",
        amount=Decimal("12.500"),
        currency="TND",
        business_date=None,
        warnings=["PAYMENT_CHILD_ID_MISSING"],
    )
    assert event["amount"] == "12.5"
    assert event["currency"] == "TND"
    assert event["business_date"] is None
    assert event["eligibility"] == "LEGACY_UNRESOLVED"
    assert event["warnings"] == ["PAYMENT_CHILD_ID_MISSING"]
    assert len(event["candidate_key"]) == 64
    assert len(event["source_fingerprint"]) == 64


def test_blocked_candidate_requires_reason():
    with pytest.raises(ValueError):
        build_candidate_envelope(
            source_type="GS_PURCHASE",
            source_id="purchase-1",
            event_type="PURCHASE_RECOGNIZED",
            source_facts={},
            eligibility="BLOCKED",
        )


def test_envelope_rejects_amount_without_currency_and_quantity_without_unit():
    base = {
        "source_type": "GS_PURCHASE",
        "source_id": "purchase-1",
        "event_type": "PURCHASE_RECOGNIZED",
        "source_facts": {},
        "eligibility": "INFORMATIONAL_ONLY",
    }
    with pytest.raises(ValueError):
        build_candidate_envelope(**base, amount="5.000")
    with pytest.raises(ValueError):
        build_candidate_envelope(**base, quantity="10.000")
