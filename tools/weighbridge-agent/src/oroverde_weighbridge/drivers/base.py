"""Interface every model-specific indicator driver must implement."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ..models import ScaleSample


class ScaleDriver(Protocol):
    protocol_id: str

    def decode_frame(self, frame: bytes, *, received_at: datetime) -> ScaleSample | None:
        """Decode exactly one protocol frame, or return None for an incomplete frame.

        Implementations must validate frame boundaries, status flags, units,
        sign, and checksums where the vendor protocol defines them. They must
        never infer a weight by searching arbitrary text for a numeric token.
        """
        ...
