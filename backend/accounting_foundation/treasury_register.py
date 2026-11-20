"""Validated, season-scoped filters for the read-only treasury movement register."""
from __future__ import annotations

from datetime import date
from typing import Any


ALLOWED_DIRECTIONS = frozenset({"IN", "OUT"})
ALLOWED_SETTLEMENT_STATUSES = frozenset({
    "CASH_RECORDED",
    "PENDING_BANK_CONFIRMATION",
    "PENDING_CHEQUE_CLEARANCE",
})


def _iso_day(value: str | None, field: str) -> str | None:
    if value is None or value == "":
        return None
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must use YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{field} must use YYYY-MM-DD")
    return value


def build_movement_register_filter(
    *, season_code: str, account_id: str | None = None,
    direction: str | None = None, settlement_status: str | None = None,
    start_date: str | None = None, end_date: str | None = None,
) -> dict[str, Any]:
    """Build a bounded active-season Mongo filter; never infer balances or include other seasons."""
    if not season_code or not season_code.strip():
        raise ValueError("Active season is required")
    query: dict[str, Any] = {"season_code": season_code}
    if account_id:
        normalized_account = account_id.strip()
        if not normalized_account or len(normalized_account) > 120:
            raise ValueError("Invalid account_id")
        query["account_id"] = normalized_account
    if direction is not None:
        if direction not in ALLOWED_DIRECTIONS:
            raise ValueError("Unsupported movement direction")
        query["direction"] = direction
    if settlement_status is not None:
        if settlement_status not in ALLOWED_SETTLEMENT_STATUSES:
            raise ValueError("Unsupported settlement status")
        query["settlement_status"] = settlement_status
    start_day = _iso_day(start_date, "start_date")
    end_day = _iso_day(end_date, "end_date")
    if start_day and end_day and start_day > end_day:
        raise ValueError("start_date must not be after end_date")
    if start_day or end_day:
        date_filter: dict[str, str] = {}
        if start_day:
            date_filter["$gte"] = start_day
        if end_day:
            date_filter["$lte"] = end_day
        query["movement_date"] = date_filter
    return query
