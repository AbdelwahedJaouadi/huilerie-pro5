from decimal import Decimal

import pytest

from lib.weighing import derive_net_weight_kg


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
