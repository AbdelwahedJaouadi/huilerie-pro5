"""Pure validation for immutable physical cash-count evidence."""
from __future__ import annotations

from decimal import Decimal

# TND denominations represented in millimes, including notes and coins.
DENOMINATION_MILLIMES = {
    "50.000": 50000, "20.000": 20000, "10.000": 10000, "5.000": 5000,
    "2.000": 2000, "1.000": 1000, "0.500": 500, "0.200": 200,
    "0.100": 100, "0.050": 50, "0.020": 20, "0.010": 10, "0.005": 5,
}


def calculate_cash_count(denomination_counts: dict[str, int]) -> tuple[dict[str, int], Decimal]:
    """Validate denomination quantities and return normalized counts and exact TND total."""
    if not isinstance(denomination_counts, dict) or not denomination_counts:
        raise ValueError("At least one denomination count is required")
    unknown = set(denomination_counts) - set(DENOMINATION_MILLIMES)
    if unknown:
        raise ValueError("Unsupported TND denomination")
    normalized: dict[str, int] = {}
    total_millimes = 0
    for denomination, count in denomination_counts.items():
        if isinstance(count, bool) or not isinstance(count, int) or count < 0 or count > 1_000_000:
            raise ValueError("Denomination counts must be whole non-negative integers")
        normalized[denomination] = count
        total_millimes += DENOMINATION_MILLIMES[denomination] * count
    if total_millimes > 10**12:
        raise ValueError("Cash count total exceeds the supported limit")
    return normalized, (Decimal(total_millimes) / Decimal(1000)).quantize(Decimal("0.001"))
