"""Read-only building blocks for the Oro Verde accounting foundation.

This package deliberately contains no database client and performs no writes.
"""
from .normalization import (
    build_candidate_envelope,
    canonical_decimal,
    candidate_key,
    source_fingerprint,
)
from .traditional import (
    adapt_traditional_invoice,
    adapt_traditional_invoice_payments,
)

__all__ = [
    "adapt_traditional_invoice",
    "adapt_traditional_invoice_payments",
    "build_candidate_envelope",
    "canonical_decimal",
    "candidate_key",
    "source_fingerprint",
]
