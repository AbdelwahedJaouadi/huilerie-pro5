import pytest

from accounting_foundation.cash_count import calculate_cash_count


def test_cash_count_uses_exact_tnd_denominations_and_millimes():
    counts, total = calculate_cash_count({"50.000": 2, "1.000": 3, "0.005": 1})
    assert counts == {"50.000": 2, "1.000": 3, "0.005": 1}
    assert total == __import__("decimal").Decimal("103.005")


@pytest.mark.parametrize("counts", [
    {}, {"0.003": 1}, {"1.000": -1}, {"1.000": True},
    {"1.000": 1.5}, {"1.000": 1_000_001},
])
def test_cash_count_rejects_invalid_denominations_or_quantities(counts):
    with pytest.raises(ValueError):
        calculate_cash_count(counts)


def test_cash_count_rejects_non_mapping_payload():
    with pytest.raises(ValueError):
        calculate_cash_count(None)
