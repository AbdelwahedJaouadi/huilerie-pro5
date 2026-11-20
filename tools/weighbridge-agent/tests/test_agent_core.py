from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from oroverde_weighbridge import (
    DriverRegistry,
    ScaleSample,
    StableReadingGate,
    UnsupportedProtocolError,
)
from oroverde_weighbridge.errors import InvalidScaleSampleError


NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)


def sample(value="1250.5", *, unit="kg", stable=True, received_at=NOW):
    return ScaleSample(
        value=Decimal(value),
        unit=unit,
        stable=stable,
        received_at=received_at,
        raw_frame_hex="30313233",
    )


def test_unknown_protocol_fails_closed_without_guessing():
    registry = DriverRegistry()
    with pytest.raises(UnsupportedProtocolError, match="unsupported_protocol"):
        registry.create("unknown-vendor-protocol")


def test_gate_waits_for_required_consecutive_stable_samples():
    gate = StableReadingGate(required_samples=3, max_age=timedelta(seconds=3))
    assert gate.feed(sample(), now=NOW) is None
    assert gate.feed(sample(), now=NOW) is None
    result = gate.feed(sample(), now=NOW)
    assert result is not None
    assert result.value_kg == Decimal("1250.5")
    assert result.sample_count == 3


def test_unstable_sample_resets_consecutive_count():
    gate = StableReadingGate(required_samples=2, max_age=timedelta(seconds=3))
    assert gate.feed(sample(), now=NOW) is None
    assert gate.feed(sample(stable=False), now=NOW) is None
    assert gate.feed(sample(), now=NOW) is None
    result = gate.feed(sample(), now=NOW)
    assert result is not None
    assert result.sample_count == 2


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        ("1000", "g", Decimal("1.000")),
        ("10", "kg", Decimal("10")),
        ("10", "lb", Decimal("4.53592370")),
    ],
)
def test_unit_normalization(value, unit, expected):
    gate = StableReadingGate(required_samples=1, max_age=timedelta(seconds=3))
    assert gate.feed(sample(value, unit=unit), now=NOW).value_kg == expected


def test_stale_and_future_samples_are_rejected():
    gate = StableReadingGate(required_samples=1, max_age=timedelta(seconds=3))
    with pytest.raises(InvalidScaleSampleError, match="stale or future-dated"):
        gate.feed(sample(received_at=NOW - timedelta(seconds=4)), now=NOW)
    with pytest.raises(InvalidScaleSampleError, match="stale or future-dated"):
        gate.feed(sample(received_at=NOW + timedelta(seconds=1)), now=NOW)


def test_non_finite_values_are_rejected():
    gate = StableReadingGate(required_samples=1, max_age=timedelta(seconds=3))
    with pytest.raises(InvalidScaleSampleError, match="finite decimal"):
        gate.feed(sample("NaN"), now=NOW)


def test_stability_gate_does_not_infer_stability_from_identical_values():
    gate = StableReadingGate(required_samples=2, max_age=timedelta(seconds=3))
    assert gate.feed(sample(stable=False), now=NOW) is None
    assert gate.feed(sample(stable=False), now=NOW) is None
