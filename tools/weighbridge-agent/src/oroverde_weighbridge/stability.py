"""Fail-closed validation and stable-sample gate."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Deque

from .errors import InvalidScaleSampleError
from .models import ScaleSample, StableWeight

_TO_KG = {
    "kg": Decimal("1"),
    "g": Decimal("0.001"),
    "lb": Decimal("0.45359237"),
}


class StableReadingGate:
    """Accept only N consecutive device-confirmed stable, fresh samples.

    The gate deliberately does not infer stability from numeric similarity.
    A model-specific driver must decode the indicator's actual stable/motion
    status. Any unstable or invalid sample resets the consecutive count.
    """

    def __init__(self, *, required_samples: int, max_age: timedelta) -> None:
        if required_samples < 1:
            raise ValueError("required_samples must be at least 1")
        if max_age <= timedelta(0):
            raise ValueError("max_age must be positive")
        self.required_samples = required_samples
        self.max_age = max_age
        self._samples: Deque[ScaleSample] = deque(maxlen=required_samples)

    def reset(self) -> None:
        self._samples.clear()

    def feed(self, sample: ScaleSample, *, now: datetime | None = None) -> StableWeight | None:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or sample.received_at.tzinfo is None:
            self.reset()
            raise InvalidScaleSampleError("timestamps must be timezone-aware")
        if not sample.value.is_finite():
            self.reset()
            raise InvalidScaleSampleError("weight must be a finite decimal")
        if sample.unit not in _TO_KG:
            self.reset()
            raise InvalidScaleSampleError(f"unsupported unit: {sample.unit}")
        if sample.received_at > current or current - sample.received_at > self.max_age:
            self.reset()
            raise InvalidScaleSampleError("scale sample is stale or future-dated")
        if not sample.raw_frame_hex or len(sample.raw_frame_hex) > 4096:
            self.reset()
            raise InvalidScaleSampleError("raw frame evidence is missing or too large")
        if not sample.stable:
            self.reset()
            return None

        self._samples.append(sample)
        if len(self._samples) < self.required_samples:
            return None

        latest = self._samples[-1]
        return StableWeight(
            value_kg=latest.value * _TO_KG[latest.unit],
            captured_at=latest.received_at.astimezone(timezone.utc),
            sample_count=len(self._samples),
            raw_unit=latest.unit,
            raw_value=latest.value,
            raw_frame_hex=latest.raw_frame_hex,
        )
