import pytest

from accounting_foundation.treasury_register import build_movement_register_filter


def test_register_is_always_scoped_to_active_season():
    assert build_movement_register_filter(season_code="2627") == {"season_code": "2627"}


def test_register_combines_account_direction_status_and_inclusive_dates():
    result = build_movement_register_filter(
        season_code="2627", account_id=" cash-1 ", direction="OUT",
        settlement_status="PENDING_BANK_CONFIRMATION",
        start_date="2026-11-01", end_date="2026-11-20",
    )
    assert result == {
        "season_code": "2627",
        "account_id": "cash-1",
        "direction": "OUT",
        "settlement_status": "PENDING_BANK_CONFIRMATION",
        "movement_date": {"$gte": "2026-11-01", "$lte": "2026-11-20"},
    }


@pytest.mark.parametrize("start,end", [
    ("2026-11-21", "2026-11-20"),
    ("20261101", None),
    ("not-a-date", None),
])
def test_register_rejects_invalid_date_ranges(start, end):
    with pytest.raises(ValueError):
        build_movement_register_filter(season_code="2627", start_date=start, end_date=end)


def test_register_rejects_unsupported_direction_and_status():
    with pytest.raises(ValueError, match="direction"):
        build_movement_register_filter(season_code="2627", direction="SIDEWAYS")
    with pytest.raises(ValueError, match="status"):
        build_movement_register_filter(season_code="2627", settlement_status="CLEARED")


def test_register_rejects_missing_season_and_invalid_account():
    with pytest.raises(ValueError, match="season"):
        build_movement_register_filter(season_code="")
    with pytest.raises(ValueError, match="account"):
        build_movement_register_filter(season_code="2627", account_id=" ")


def test_register_date_filters_are_open_ended_when_only_one_bound_is_given():
    assert build_movement_register_filter(
        season_code="2627", start_date="2026-11-01"
    )["movement_date"] == {"$gte": "2026-11-01"}
    assert build_movement_register_filter(
        season_code="2627", end_date="2026-11-20"
    )["movement_date"] == {"$lte": "2026-11-20"}
