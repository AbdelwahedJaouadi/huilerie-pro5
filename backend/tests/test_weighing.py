from datetime import datetime, timezone
from decimal import Decimal

from bson import BSON

import pytest
from bson.decimal128 import Decimal128

from lib.weighing import derive_net_weight_kg, weight_measurement_audit_snapshot
from models.schemas import LoadCreate


@pytest.mark.parametrize(
    ("gross", "tare", "expected"),
    [
        ("12500.000", "4200.000", Decimal("8300.000")),
        ("12500.125", "4200.025", Decimal("8300.100")),
        (12500.5, 4200.25, Decimal("8300.250")),
        (Decimal("100.001"), Decimal("0.001"), Decimal("100.000")),
    ],
)
def test_net_weight_is_derived_exactly(gross, tare, expected):
    assert derive_net_weight_kg(gross, tare) == expected


@pytest.mark.parametrize(
    ("gross", "tare", "error"),
    [
        ("0", "1", "gross_weight_out_of_range"),
        ("100", "0", "tare_weight_out_of_range"),
        ("100", "100", "gross_must_exceed_tare"),
        ("99", "100", "gross_must_exceed_tare"),
        ("100.0001", "10", "gross_weight_invalid_precision"),
        ("NaN", "10", "gross_weight_invalid"),
        ("Infinity", "10", "gross_weight_invalid"),
        (True, "10", "gross_weight_invalid"),
        (None, "10", "gross_weight_invalid"),
        ("100", "1000001", "tare_weight_out_of_range"),
    ],
)
def test_invalid_weight_pairs_are_rejected(gross, tare, error):
    with pytest.raises(ValueError, match=error):
        derive_net_weight_kg(gross, tare)


def test_decimal_trailing_zeroes_do_not_cause_false_precision_error():
    assert derive_net_weight_kg("100.0000", "25.0000") == Decimal("75.000")



def test_traditional_intake_derives_olive_kg_from_gross_and_tare():
    command = LoadCreate(
        client_name="Test Client",
        phone="+21600000000",
        gross_weight_kg="12500.125",
        tare_weight_kg="4200.025",
    )
    assert command.olive_kg == 8300.1
    assert command.gross_weight_kg == Decimal("12500.125")
    assert command.tare_weight_kg == Decimal("4200.025")


def test_traditional_intake_preserves_decimal_scale_of_vehicle_readings():
    command = LoadCreate(
        client_name="Test Client",
        phone="+21600000000",
        gross_weight_kg="12500.000",
        tare_weight_kg="4200.000",
    )
    assert command.gross_weight_kg == Decimal("12500.000")
    assert command.tare_weight_kg == Decimal("4200.000")


def test_traditional_intake_accepts_redundant_trailing_decimal_zeroes():
    command = LoadCreate(
        client_name="Test Client",
        phone="+21600000000",
        gross_weight_kg="12500.0000",
        tare_weight_kg="4200.0000",
    )
    assert command.gross_weight_kg == Decimal("12500.0000")
    assert command.tare_weight_kg == Decimal("4200.0000")
    assert command.olive_kg == 8300.0


def test_traditional_intake_ignores_client_net_when_gross_and_tare_are_present():
    command = LoadCreate(
        client_name="Test Client",
        phone="+21600000000",
        olive_kg=999999,
        gross_weight_kg="12500.125",
        tare_weight_kg="4200.025",
    )
    assert command.olive_kg == 8300.1


def test_traditional_intake_rejects_boolean_scale_readings_before_float_coercion():
    with pytest.raises(Exception, match="gross_weight_invalid"):
        LoadCreate(
            client_name="Test Client",
            phone="+21600000000",
            gross_weight_kg=True,
            tare_weight_kg=10,
        )


def test_traditional_intake_keeps_legacy_net_only_payload_compatible():
    command = LoadCreate(
        client_name="Test Client",
        phone="+21600000000",
        olive_kg=8300.125,
    )
    assert command.olive_kg == 8300.125
    assert command.gross_weight_kg is None
    assert command.tare_weight_kg is None


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        ({"gross_weight_kg": 12000}, "gross_and_tare_must_be_provided_together"),
        ({"tare_weight_kg": 4000}, "gross_and_tare_must_be_provided_together"),
        ({}, "olive_kg_or_gross_and_tare_required"),
        ({"gross_weight_kg": 4000, "tare_weight_kg": 12000}, "gross_must_exceed_tare"),
    ],
)
def test_traditional_intake_rejects_incomplete_or_invalid_weight_evidence(payload, error):
    with pytest.raises(Exception, match=error):
        LoadCreate(client_name="Test Client", phone="+21600000000", **payload)



def test_weight_measurement_audit_snapshot_preserves_original_evidence():
    measured_at = datetime.now(timezone.utc)
    snapshot = weight_measurement_audit_snapshot({
        "gross_kg": Decimal128("12500.125"),
        "tare_kg": Decimal128("4200.025"),
        "net_kg": Decimal128("8300.100"),
        "measured_at": measured_at,
        "operator_user_id": "user-17",
        "operator_username": "scale.operator",
        "source": "manual",
        "correction_of": None,
    })

    assert snapshot == {
        "gross_kg": "12500.125",
        "tare_kg": "4200.025",
        "net_kg": "8300.100",
        "measured_at": measured_at,
        "operator_user_id": "user-17",
        "operator_username": "scale.operator",
        "source": "manual",
        "correction_of": None,
    }
    # The complete audit payload must be encodable by MongoDB's BSON serializer.
    BSON.encode({"details": snapshot})


def test_weight_measurement_audit_snapshot_handles_legacy_load_without_weighing():
    assert weight_measurement_audit_snapshot(None) is None



@pytest.mark.parametrize(
    ("olive_kg", "error"),
    [
        (True, "olive_weight_invalid"),
        ("8300.0001", "olive_weight_invalid_precision"),
        (1_000_001, "olive_weight_out_of_range"),
    ],
)
def test_legacy_net_only_intake_rejects_invalid_raw_weight_values(olive_kg, error):
    with pytest.raises(Exception, match=error):
        LoadCreate(
            client_name="Test Client",
            phone="+21600000000",
            olive_kg=olive_kg,
        )
