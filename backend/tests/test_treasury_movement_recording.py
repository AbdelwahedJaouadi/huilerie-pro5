from datetime import datetime, timezone
from decimal import Decimal

from bson.decimal128 import Decimal128

from accounting_foundation.treasury_posting import build_movement_document


def candidate(method="CASH", direction="IN"):
    return {
        "eligibility": "ELIGIBLE_FOR_REVIEW",
        "source_type": "GS_SALE_PAYMENT",
        "source_id": "payment-1",
        "source_document_number": "PAY-0001",
        "party_id": "buyer-1",
        "direction": direction,
        "account_id": "cash-1",
        "account_name": "Main cash",
        "account_type": "CASH" if method == "CASH" else "BANK",
        "amount": "25.500",
        "business_date": "2026-11-20",
        "payment_method": method,
        "reference": "REF-123" if method != "CASH" else None,
    }


def test_cash_receipt_is_recorded_without_balance_or_gl_posting():
    row = build_movement_document(
        candidate(), season_code="2627", actor_user_id="admin-1",
        movement_id="movement-1", recorded_at=datetime(2026, 11, 20, tzinfo=timezone.utc),
    )
    assert row["movement_type"] == "RECEIPT"
    assert row["direction"] == "IN"
    assert row["amount_tnd"].to_decimal() == Decimal("25.500")
    assert row["settlement_status"] == "CASH_RECORDED"
    assert row["opening_balance_applied"] is False
    assert row["gl_posting_status"] == "NOT_POSTED"
    assert "balance" not in row


def test_supplier_payment_is_disbursement_and_bank_payment_stays_pending():
    row = build_movement_document(
        candidate(method="BANK_TRANSFER", direction="OUT"), season_code="2627",
        actor_user_id="admin-1", movement_id="movement-2",
        recorded_at=datetime(2026, 11, 20, tzinfo=timezone.utc),
    )
    assert row["movement_type"] == "DISBURSEMENT"
    assert row["settlement_status"] == "PENDING_BANK_CONFIRMATION"
    assert row["external_reference"] == "REF-123"


def test_cheque_is_not_treated_as_cleared():
    row = build_movement_document(
        candidate(method="CHEQUE"), season_code="2627", actor_user_id="admin-1",
        movement_id="movement-3", recorded_at=datetime(2026, 11, 20, tzinfo=timezone.utc),
    )
    assert row["settlement_status"] == "PENDING_CHEQUE_CLEARANCE"


def test_blocked_candidate_cannot_be_recorded():
    row = candidate()
    row["eligibility"] = "BLOCKED"
    row["blocking_reasons"] = ["TREASURY_ACCOUNT_NOT_ASSIGNED"]
    try:
        build_movement_document(
            row, season_code="2627", actor_user_id="admin-1",
            movement_id="movement-4", recorded_at=datetime(2026, 11, 20, tzinfo=timezone.utc),
        )
    except ValueError as exc:
        assert "TREASURY_ACCOUNT_NOT_ASSIGNED" in str(exc)
    else:
        raise AssertionError("Blocked movement candidate must never be recorded")
