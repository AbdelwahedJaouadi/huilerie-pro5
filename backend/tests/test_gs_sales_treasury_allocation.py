from accounting_foundation.sales import adapt_gs_sales


def invoice(paid="40"):
    return {
        "id": "invoice-1", "season_code": "2627", "document_number": "2627F0001",
        "sale_id": "sale-1", "buyer_id": "buyer-1", "sale_date": "2026-11-20",
        "total_amount_dt": "100", "credited_amount_dt": "0", "net_amount_dt": "100",
        "paid_amount_dt": paid,
    }


def payment(account_id="cash-1", method="CASH"):
    return {
        "id": "payment-1", "season_code": "2627", "document_number": "PAY-1",
        "invoice_id": "invoice-1", "sale_id": "sale-1", "amount_dt": "50",
        "payment_date": "2026-11-20", "method": method,
        "reference": "TRX-001" if method != "CASH" else None,
        "treasury_account_id": account_id,
    }


def test_gs_sale_receipt_without_treasury_account_is_blocked():
    result = adapt_gs_sales(
        [invoice(paid="50")], [payment(account_id=None)],
        treasury_accounts=[{"id": "cash-1", "account_type": "CASH", "currency": "TND"}],
    )
    event = result["candidate_events"][1]
    assert event["eligibility"] == "BLOCKED"
    assert "TREASURY_ACCOUNT_NOT_ASSIGNED" in event["blocking_reasons"]


def test_gs_sale_receipt_requires_account_type_matching_payment_method():
    result = adapt_gs_sales(
        [invoice(paid="50")], [payment(account_id="bank-1", method="CASH")],
        treasury_accounts=[{"id": "bank-1", "account_type": "BANK", "currency": "TND"}],
    )
    event = result["candidate_events"][1]
    assert event["eligibility"] == "BLOCKED"
    assert "TREASURY_ACCOUNT_TYPE_MISMATCH" in event["blocking_reasons"]


def test_mapped_sale_receipt_and_reversal_retain_same_treasury_account():
    result = adapt_gs_sales(
        [invoice(paid="40")],
        [payment()],
        [{
            "id": "reversal-1", "season_code": "2627", "document_number": "REV-1",
            "payment_id": "payment-1", "invoice_id": "invoice-1", "buyer_id": "buyer-1",
            "amount_dt": "10", "reversal_date": "2026-11-20",
            "payment_method": "CASH", "treasury_account_id": "cash-1",
        }],
        treasury_accounts=[{"id": "cash-1", "account_type": "CASH", "currency": "TND"}],
    )
    payment_event = next(x for x in result["candidate_events"] if x["source_type"] == "GS_SALE_PAYMENT")
    reversal_event = next(x for x in result["candidate_events"] if x["source_type"] == "GS_SALE_PAYMENT_REVERSAL")
    assert payment_event["eligibility"] == "ELIGIBLE_FOR_REVIEW"
    assert "TREASURY_ACCOUNT_MAPPED" in payment_event["warnings"]
    assert reversal_event["eligibility"] == "ELIGIBLE_FOR_REVIEW"
    assert "TREASURY_ACCOUNT_MAPPED" in reversal_event["warnings"]


def test_reversal_cannot_be_assigned_to_a_different_treasury_account():
    result = adapt_gs_sales(
        [invoice(paid="40")], [payment()],
        [{
            "id": "reversal-1", "payment_id": "payment-1", "invoice_id": "invoice-1",
            "amount_dt": "10", "reversal_date": "2026-11-20",
            "payment_method": "CASH", "treasury_account_id": "other-cash",
        }],
        treasury_accounts=[
            {"id": "cash-1", "account_type": "CASH", "currency": "TND"},
            {"id": "other-cash", "account_type": "CASH", "currency": "TND"},
        ],
    )
    event = next(x for x in result["candidate_events"] if x["source_type"] == "GS_SALE_PAYMENT_REVERSAL")
    assert event["eligibility"] == "BLOCKED"
    assert "REVERSAL_TREASURY_ACCOUNT_LINK_MISMATCH" in event["blocking_reasons"]
