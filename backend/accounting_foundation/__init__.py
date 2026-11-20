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
from .commercial import (
    adapt_gs_olive_purchase,
    adapt_gs_supplier_payments,
)
from .sales import adapt_gs_sales

__all__ = [
    "adapt_gs_olive_purchase",
    "adapt_gs_supplier_payments",
    "adapt_gs_sales",
    "adapt_traditional_invoice",
    "adapt_traditional_invoice_payments",
    "build_candidate_envelope",
    "build_reconciliation_preview",
    "canonical_decimal",
    "candidate_key",
    "source_fingerprint",
]

from .preview import build_reconciliation_preview
