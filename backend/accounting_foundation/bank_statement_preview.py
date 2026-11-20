"""Strict CSV preview and conservative candidate classification for bank statements."""
from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

REQUIRED_COLUMNS = frozenset({"transaction_date", "amount", "direction"})
OPTIONAL_COLUMNS = frozenset({"value_date", "reference", "description"})
MAX_STATEMENT_ROWS = 100
MAX_AMOUNT_SCALE = 3


def parse_bank_statement_csv(raw: bytes) -> list[dict[str, Any]]:
    if not raw:
        raise ValueError("The uploaded CSV is empty")
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded") from exc
    reader = csv.DictReader(io.StringIO(decoded))
    if not reader.fieldnames:
        raise ValueError("CSV header row is required")
    normalized = [str(name or "").strip().lower() for name in reader.fieldnames]
    if len(normalized) != len(set(normalized)):
        raise ValueError("CSV contains duplicate column names")
    missing = REQUIRED_COLUMNS - set(normalized)
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(sorted(missing)))
    rows: list[dict[str, Any]] = []
    for line_number, raw_row in enumerate(reader, start=2):
        if len(rows) >= MAX_STATEMENT_ROWS:
            raise ValueError(f"CSV cannot contain more than {MAX_STATEMENT_ROWS} data rows")
        row = {str(key or "").strip().lower(): (value or "").strip() for key, value in raw_row.items()}
        if not any(row.values()):
            continue
        try:
            transaction_date = date.fromisoformat(row.get("transaction_date", ""))
            value_date_raw = row.get("value_date", "")
            value_date = date.fromisoformat(value_date_raw) if value_date_raw else None
        except ValueError as exc:
            raise ValueError(f"Invalid ISO date on CSV line {line_number}") from exc
        if transaction_date.isoformat() != row.get("transaction_date"):
            raise ValueError(f"transaction_date must use YYYY-MM-DD on CSV line {line_number}")
        if value_date and value_date.isoformat() != value_date_raw:
            raise ValueError(f"value_date must use YYYY-MM-DD on CSV line {line_number}")
        amount_raw = row.get("amount", "")
        if not re.fullmatch(r"\d+(?:\.\d{1,3})?", amount_raw):
            raise ValueError(f"Amount must use plain decimal notation on CSV line {line_number}")
        try:
            amount = Decimal(amount_raw)
        except InvalidOperation as exc:
            raise ValueError(f"Invalid amount on CSV line {line_number}") from exc
        if not amount.is_finite() or amount <= 0 or max(0, -amount.as_tuple().exponent) > MAX_AMOUNT_SCALE:
            raise ValueError(f"Amount must be positive TND with at most 3 decimals on CSV line {line_number}")
        direction = row.get("direction", "").upper()
        if direction not in {"IN", "OUT"}:
            raise ValueError(f"direction must be IN or OUT on CSV line {line_number}")
        reference = row.get("reference", "")
        description = row.get("description", "")
        if len(reference) > 160 or len(description) > 500:
            raise ValueError(f"Reference or description is too long on CSV line {line_number}")
        fingerprint_source = "|".join([
            transaction_date.isoformat(), value_date.isoformat() if value_date else "",
            format(amount, "f"), direction, reference,
        ])
        rows.append({
            "line_number": line_number,
            "transaction_date": transaction_date.isoformat(),
            "value_date": value_date.isoformat() if value_date else None,
            "amount_tnd": format(amount, ".3f"),
            "direction": direction,
            "reference": reference or None,
            "description": description or None,
            "fingerprint": hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest(),
        })
    if not rows:
        raise ValueError("CSV contains no statement lines")
    return rows


def classify_statement_line(line: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    reference = (line.get("reference") or "").strip()
    if reference:
        exact = [row for row in candidates if (row.get("external_reference") or "").strip() == reference]
        if len(exact) == 1:
            status = "REFERENCE_CANDIDATE"
            selected = exact
        elif len(exact) > 1:
            status = "AMBIGUOUS_REFERENCE"
            selected = exact
        elif candidates:
            status = "REFERENCE_MISMATCH"
            selected = candidates
        else:
            status = "UNMATCHED"
            selected = []
    elif len(candidates) == 1:
        status = "POSSIBLE_MATCH"
        selected = candidates
    elif len(candidates) > 1:
        status = "AMBIGUOUS"
        selected = candidates
    else:
        status = "UNMATCHED"
        selected = []
    return {
        "match_status": status,
        "candidate_count": len(selected),
        "candidates": selected[:10],
        "automatic_match": False,
    }


def movement_date_window(transaction_date: str, days: int = 7) -> tuple[str, str]:
    day = date.fromisoformat(transaction_date)
    return ((day - timedelta(days=days)).isoformat(), (day + timedelta(days=days)).isoformat())
