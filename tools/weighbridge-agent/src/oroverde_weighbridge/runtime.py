"""Frame-to-reading orchestration. Transport and OS service are separate layers."""

from __future__ import annotations

from datetime import datetime, timedelta

from .models import StableWeight
from .registry import DriverRegistry
from .stability import StableReadingGate


class WeighbridgeCore:
    def __init__(
        self,
        *,
        registry: DriverRegistry,
        protocol_id: str,
        required_samples: int,
        max_age: timedelta = timedelta(seconds=3),
    ) -> None:
        self.driver = registry.create(protocol_id)
        self.gate = StableReadingGate(
            required_samples=required_samples,
            max_age=max_age,
        )

    def process_frame(self, frame: bytes, *, received_at: datetime) -> StableWeight | None:
        sample = self.driver.decode_frame(frame, received_at=received_at)
        if sample is None:
            return None
        return self.gate.feed(sample, now=received_at)
