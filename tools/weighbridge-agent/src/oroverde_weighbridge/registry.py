"""Explicit protocol-to-driver registry; unknown protocols fail closed."""

from __future__ import annotations

from typing import Callable

from .drivers.base import ScaleDriver
from .errors import UnsupportedProtocolError


DriverFactory = Callable[[], ScaleDriver]


class DriverRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, DriverFactory] = {}

    def register(self, protocol_id: str, factory: DriverFactory) -> None:
        key = protocol_id.strip()
        if not key:
            raise ValueError("protocol_id is required")
        if key in self._factories:
            raise ValueError(f"Driver already registered for protocol: {key}")
        self._factories[key] = factory

    def create(self, protocol_id: str) -> ScaleDriver:
        key = protocol_id.strip()
        factory = self._factories.get(key)
        if factory is None:
            raise UnsupportedProtocolError(f"unsupported_protocol: {key or '(empty)'}")
        driver = factory()
        if driver.protocol_id != key:
            raise ValueError("Driver factory returned a mismatched protocol identifier")
        return driver

    @property
    def supported_protocols(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))
