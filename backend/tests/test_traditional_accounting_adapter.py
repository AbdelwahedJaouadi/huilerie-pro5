from decimal import Decimal

import pytest

from accounting_foundation import (
    adapt_traditional_invoice,
    adapt_traditional_invoice_payments,
)


def test_invoice_candidate_never_auto_approves_recognition_or_tariff_basis():
    candidate = adapt_traditional_invoice({
        "id": "invoice-1",
        "number": "FAC-001",
        "load_id": "load-1",
        "day": "2026-11-20",
        "total": "125.000",
        "client_id": "client-1",
        "currency": "TND",
    })
    assert candidate["source_id"] == "invoice-1"
    assert candidate["amount"] == "125"
    assert candidate["currency"] == "TND"
    assert candidate["eligibility"] == "LEGACY_UNRESOLVED"
    assert "TARIFF_BASIS_NOT_APPROVED" in candidate["warnings"]
    assert "INVOICE_RECOGNITION_POLICY_NOT_APPROVED" in candidate["warnings"]


def test_invoice_amount_without_explicit_currency_is_not_normalized_as_money():
    candidate = adapt_traditional_invoice({
        "id": "invoice-2",
        "total": "125.000",
        "day": "2026-11-20",
    })
    assert candidate["amount"] is None
    assert candidate["currency"] is None
    assert "INVOICE_CURRENCY_NOT_EXPLICIT" in candidate["warnings"]


def test_invoice_requires_immutable_source_id():
    with pytest.raises(ValueError):
        adapt_traditional_invoice({"number": "FAC-001", "total": "5"})


def test_invalid_calendar_date_is_not_accepted():
    candidate = adapt_traditional_invoice({
        "id": "invoice-3",
        "day": "2026-99-99",
    })
    assert candidate["business_date"] is None
    assert "INVOICE_BUSINESS_DATE_INVALID_OR_UNSUPPORTED" in candidate["warnings"]


def test_stable_itemized_payment_is_candidate_for_review_only():
    result = adapt_traditional_invoice_payments({
        "id": "invoice-1",
        "number": "FAC-001",
        "client_id": "client-1",
        "payments": [{
            "id": "payment-1",
            "amount": "30.000",
            "currency": "TND",
            "at": "2026-11-20T10:30:00+01:00",
            "by": "employee-1",
        }],
        "paid_amount": "30.000",
    })
    assert len(result["candidate_events"]) == 1
    event = result["candidate_events"][0]
    assert event["child_event_id"] == "payment-1"
    assert event["candidate_key"]
    assert event["amount"] == "30"
    assert event["eligibility"] == "ELIGIBLE_FOR_REVIEW"
    assert result["unresolved_items"] == []
    assert result["history_used_as_receipts"] is False


def test_missing_payment_child_id_is_not_replaced_by_synthetic_identity():
    result = adapt_traditional_invoice_payments({
        "id": "invoice-1",
        "payments": [{"amount": "30.000", "currency": "TND", "at": "2026-11-20"}],
        "paid_amount": "30.000",
    })
    assert result["candidate_events"] == []
    assert result["unresolved_items"][0]["reason"] == "PAYMENT_CHILD_ID_MISSING"
    assert "candidate_key" not in result["unresolved_items"][0]
    assert result["itemized_payment_total"] is None


def test_aggregate_paid_amount_without_itemized_receipts_is_not_a_receipt():
    result = adapt_traditional_invoice_payments({
        "id": "invoice-1",
        "payments": [],
        "paid_amount": "70.000",
        "history": [{"at": "2026-11-20", "amount": "70.000"}],
    })
    reasons = {item["reason"] for item in result["unresolved_items"]}
    assert "LEGACY_PAID_AGGREGATE_WITHOUT_ITEMIZED_RECEIPTS" in reasons
    assert "INVOICE_HISTORY_IS_AUDIT_EVIDENCE_NOT_RECEIPTS" in reasons
    assert result["candidate_events"] == []
    assert result["history_used_as_receipts"] is False


def test_itemized_payment_sum_mismatch_is_reported_without_adjusting_amounts():
    result = adapt_traditional_invoice_payments({
        "id": "invoice-1",
        "payments": [
            {"id": "p1", "amount": "20", "currency": "TND", "at": "2026-11-20"},
            {"id": "p2", "amount": "30", "currency": "TND", "at": "2026-11-21"},
        ],
        "paid_amount": "55",
    })
    mismatch = next(
        item for item in result["unresolved_items"]
        if item["reason"] == "ITEMIZED_PAYMENTS_DO_NOT_RECONCILE_TO_PAID_SNAPSHOT"
    )
    assert mismatch["observed_amount"] == "5"
    assert len(result["candidate_events"]) == 2


def test_history_never_creates_additional_payment_candidates():
    result = adapt_traditional_invoice_payments({
        "id": "invoice-1",
        "payments": [{"id": "p1", "amount": "20", "currency": "TND", "at": "2026-11-20"}],
        "history": [{"type": "payment", "amount": "20", "at": "2026-11-20"}],
        "paid_amount": "20",
    })
    assert len(result["candidate_events"]) == 1
    assert len(result["unresolved_items"]) == 1
    assert result["unresolved_items"][0]["reason"] == "INVOICE_HISTORY_IS_AUDIT_EVIDENCE_NOT_RECEIPTS"


def test_payment_without_currency_or_date_remains_unresolved():
    result = adapt_traditional_invoice_payments({
        "id": "invoice-1",
        "payments": [{"id": "p1", "amount": "20"}],
        "paid_amount": "20",
    })
    event = result["candidate_events"][0]
    assert event["eligibility"] == "LEGACY_UNRESOLVED"
    assert event["amount"] is None
    assert "PAYMENT_CURRENCY_NOT_EXPLICIT" in event["warnings"]
    assert "PAYMENT_DATE_MISSING" in event["warnings"]


def test_payment_float_is_not_accepted_as_exact_financial_amount():
    result = adapt_traditional_invoice_payments({
        "id": "invoice-1",
        "payments": [{"id": "p1", "amount": 20.5, "currency": "TND", "at": "2026-11-20"}],
    })
    event = result["candidate_events"][0]
    assert event["amount"] is None
    assert event["eligibility"] == "LEGACY_UNRESOLVED"
    assert "PAYMENT_AMOUNT_INVALID" in event["warnings"]


def test_missing_child_id_does_not_allow_false_paid_snapshot_reconciliation():
    result = adapt_traditional_invoice_payments({
        "id": "invoice-1",
        "payments": [
            {"amount": "20", "currency": "TND", "at": "2026-11-20"},
            {"id": "p2", "amount": "30", "currency": "TND", "at": "2026-11-21"},
        ],
        "paid_amount": "50",
    })
    assert result["itemized_payment_total"] is None
    assert not any(
        item["reason"] == "ITEMIZED_PAYMENTS_DO_NOT_RECONCILE_TO_PAID_SNAPSHOT"
        for item in result["unresolved_items"]
    )
