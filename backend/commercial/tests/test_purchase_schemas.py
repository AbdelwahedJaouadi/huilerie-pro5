from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from commercial.schemas.purchases import OlivePurchaseDraft, OliveReceptionPurchaseLine


def test_olive_purchase_accepts_multiple_varieties_and_decimal_values():
    draft = OlivePurchaseDraft(
        supplier_id="supplier-1",
        purchase_date=date(2026, 11, 2),
        lines=[
            {"variety_id": "chemlali", "quantity_kg": "1250.500", "unit_price_dt": "1.250"},
            {"variety_id": "chetoui", "quantity_kg": "500", "unit_price_dt": "1.400"},
        ],
        idempotency_key="purchase-request-0001",
    )
    assert draft.lines[0].quantity_kg == Decimal("1250.500")
    assert len(draft.lines) == 2


def test_olive_purchase_rejects_client_supplied_total():
    with pytest.raises(ValidationError):
        OlivePurchaseDraft(
            supplier_id="supplier-1",
            purchase_date=date(2026, 11, 2),
            lines=[{"variety_id": "chemlali", "quantity_kg": "100", "unit_price_dt": "1.200"}],
            total_dt="120.000",
            idempotency_key="purchase-request-0002",
        )


def test_olive_purchase_rejects_zero_or_negative_quantity():
    with pytest.raises(ValidationError):
        OlivePurchaseDraft(
            supplier_id="supplier-1",
            purchase_date=date(2026, 11, 2),
            lines=[{"variety_id": "chemlali", "quantity_kg": "0", "unit_price_dt": "1.200"}],
            idempotency_key="purchase-request-0003",
        )


def test_olive_purchase_rejects_excess_decimal_precision():
    with pytest.raises(ValidationError):
        OlivePurchaseDraft(
            supplier_id="supplier-1",
            purchase_date=date(2026, 11, 2),
            lines=[{"variety_id": "chemlali", "quantity_kg": "10.1234", "unit_price_dt": "1.200"}],
            idempotency_key="purchase-request-0004",
        )

from commercial.schemas.purchases import ApproveOlivePurchaseCommand


def test_purchase_approval_requires_receiving_location_and_version():
    command = ApproveOlivePurchaseCommand(
        expected_version=1,
        receiving_location_id="olive-yard-01",
        idempotency_key="approve-purchase-0001",
    )
    assert command.receiving_location_id == "olive-yard-01"


def test_purchase_approval_rejects_missing_receiving_location():
    with pytest.raises(ValidationError):
        ApproveOlivePurchaseCommand(
            expected_version=1,
            idempotency_key="approve-purchase-0002",
        )



def test_reception_price_is_entered_in_millimes_and_converted_to_dinars():
    line = OliveReceptionPurchaseLine(
        variety_id="chemlali",
        quantity_kg="1000",
        unit_price_millimes="1500",
    )
    assert line.unit_price_millimes == Decimal("1500")
    assert line.quantity_kg * (line.unit_price_millimes / Decimal("1000")) == Decimal("1500")


def test_reception_price_rejects_fractional_millime():
    with pytest.raises(ValidationError):
        OliveReceptionPurchaseLine(
            variety_id="chemlali",
            quantity_kg="1000",
            unit_price_millimes="1500.5",
        )



def test_olive_purchase_accepts_gross_tare_and_exact_net_quantity():
    draft = OlivePurchaseDraft(
        supplier_id="supplier-1",
        purchase_date=date(2026, 11, 2),
        lines=[{"variety_id": "chemlali", "quantity_kg": "8300.000", "unit_price_dt": "1.500"}],
        gross_weight_kg="12500.000",
        tare_weight_kg="4200.000",
        idempotency_key="purchase-weight-request-01",
    )
    assert draft.gross_weight_kg == Decimal("12500.000")
    assert draft.tare_weight_kg == Decimal("4200.000")
    assert draft.lines[0].quantity_kg == Decimal("8300.000")


def test_olive_purchase_rejects_partial_vehicle_weight_pair():
    with pytest.raises(ValidationError, match="gross_and_tare_must_be_provided_together"):
        OlivePurchaseDraft(
            supplier_id="supplier-1",
            purchase_date=date(2026, 11, 2),
            lines=[{"variety_id": "chemlali", "quantity_kg": "8300.000", "unit_price_dt": "1.500"}],
            gross_weight_kg="12500.000",
            idempotency_key="purchase-weight-request-02",
        )


def test_olive_purchase_rejects_net_quantity_not_matching_gross_minus_tare():
    with pytest.raises(ValidationError, match="purchase_quantity_must_match_vehicle_net_weight"):
        OlivePurchaseDraft(
            supplier_id="supplier-1",
            purchase_date=date(2026, 11, 2),
            lines=[{"variety_id": "chemlali", "quantity_kg": "8299.000", "unit_price_dt": "1.500"}],
            gross_weight_kg="12500.000",
            tare_weight_kg="4200.000",
            idempotency_key="purchase-weight-request-03",
        )


def test_vehicle_weight_is_not_accepted_for_multiple_purchase_lines():
    with pytest.raises(ValidationError, match="vehicle_weight_requires_single_purchase_line"):
        OlivePurchaseDraft(
            supplier_id="supplier-1",
            purchase_date=date(2026, 11, 2),
            lines=[
                {"variety_id": "chemlali", "quantity_kg": "5000.000", "unit_price_dt": "1.500"},
                {"variety_id": "chetoui", "quantity_kg": "3300.000", "unit_price_dt": "1.400"},
            ],
            gross_weight_kg="12500.000",
            tare_weight_kg="4200.000",
            idempotency_key="purchase-weight-request-04",
        )



@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("gross_weight_kg", True, "gross_weight_invalid"),
        ("tare_weight_kg", False, "tare_weight_invalid"),
        ("gross_weight_kg", "12500.0001", "gross_weight_invalid_precision"),
        ("tare_weight_kg", "1000001", "tare_weight_out_of_range"),
    ],
)
def test_vehicle_weight_rejects_invalid_raw_readings(field, value, error):
    payload = {
        "supplier_id": "supplier-1",
        "purchase_date": date(2026, 11, 2),
        "lines": [{"variety_id": "chemlali", "quantity_kg": "8300.000", "unit_price_dt": "1.500"}],
        "gross_weight_kg": "12500.000",
        "tare_weight_kg": "4200.000",
        "idempotency_key": "purchase-weight-raw-check",
    }
    payload[field] = value
    with pytest.raises(ValidationError, match=error):
        OlivePurchaseDraft(**payload)
