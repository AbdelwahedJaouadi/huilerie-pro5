"""Read-only building blocks for the Oro Verde accounting foundation.

This package deliberately contains no database client and performs no writes.
"""
from .normalization import (
    build_candidate_envelope,
    canonical_decimal,
    candidate_key,
    source_fingerprint,
)

__all__ = [
    "build_candidate_envelope",
    "canonical_decimal",
    "candidate_key",
    "source_fingerprint",
]
