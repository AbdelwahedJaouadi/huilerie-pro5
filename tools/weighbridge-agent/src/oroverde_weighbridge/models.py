"""Typed data contracts shared by device-specific scale drivers and the gate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

ScaleUnit = Literal["kg", "g", "lb"]


@dataclass(frozen=True, slots=True)
class ScaleSample:
    """One decoded device sample. Stability must come from the device protocol."""

    value: Decimal
    unit: ScaleUnit
    stable: bool
    received_at: datetime
    raw_frame_hex: str
    device_status: str | None = None


@dataclass(frozen=True, slots=True)
class StableWeight:
    """A validated, normalized weight ready for a future authenticated transport."""

    value_kg: Decimal
    captured_at: datetime
    sample_count: int
    raw_unit: ScaleUnit
    raw_value: Decimal
    raw_frame_hex: str
