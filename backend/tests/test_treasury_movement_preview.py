from accounting_foundation.treasury_preview import build_treasury_movement_preview


def account(account_id="cash-1", account_type="CASH", active=True, currency="TND"):
    return {"id": account_id, "name": "Main account", "account_type": account_type,
            "active": active, "currency": currency}


def sale_payment(**overrides):
    row = {"id": "sale-pay-1", "document_number": "PAY-1", "amount_dt": "25.500",
           "payment_date": "2026-11-20", "method": "CASH",
           "treasury_account_id": "cash-1", "buyer_id": "buyer-1"}
    return {**row, **overrides}


def supplier_payment(**overrides):
    row = {"id": "supplier-pay-1", "document_number": "SP-1", "amount_tnd": "10.000",
           "payment_date": "2026-11-20", "method": "CASH",
           "treasury_account_id": "cash-1", "supplier_id": "supplier-1"}
    return {**row, **overrides}


def test_sale_receipt_proposes_inflow_without_creating_a_movement():
    result = build_treasury_movement_preview(sale_payments=[sale_payment()], treasury_accounts=[account()])
    candidate = result["candidates"][0]
    assert candidate["direction"] == "IN"
    assert candidate["amount"] == "25.500"
    assert candidate["eligibility"] == "ELIGIBLE_FOR_REVIEW"
    assert result["movement_creation_enabled"] is False
    assert result["database_writes"] is False


def test_supplier_payment_proposes_outflow_not_a_second_expense():
    result = build_treasury_movement_preview(supplier_payments=[supplier_payment()], treasury_accounts=[account()])
    candidate = result["candidates"][0]
    assert candidate["direction"] == "OUT"
    assert candidate["source_type"] == "GS_SUPPLIER_PAYMENT"
    assert candidate["amount"] == "10.000"


def test_missing_or_inactive_or_wrong_type_account_is_blocked():
    missing = build_treasury_movement_preview(sale_payments=[sale_payment(treasury_account_id=None)])
    inactive = build_treasury_movement_preview(sale_payments=[sale_payment()], treasury_accounts=[account(active=False)])
    wrong = build_treasury_movement_preview(sale_payments=[sale_payment()], treasury_accounts=[account(account_type="BANK")])
    assert "TREASURY_ACCOUNT_NOT_ASSIGNED" in missing["candidates"][0]["blocking_reasons"]
    assert "TREASURY_ACCOUNT_INACTIVE" in inactive["candidates"][0]["blocking_reasons"]
    assert "TREASURY_ACCOUNT_TYPE_MISMATCH" in wrong["candidates"][0]["blocking_reasons"]


def test_bank_transfer_is_flagged_as_not_cleared():
    result = build_treasury_movement_preview(
        sale_payments=[sale_payment(method="BANK_TRANSFER")],
        treasury_accounts=[account(account_type="BANK")],
    )
    assert "BANK_CLEARANCE_NOT_VERIFIED" in result["candidates"][0]["warnings"]


def test_reversal_does_not_create_a_cash_outflow_proposal():
    result = build_treasury_movement_preview(sale_reversals=[{"id": "rev-1", "amount_dt": "5.000"}])
    assert result["candidates"] == []
    assert result["unresolved_items"][0]["reason"] == "EXTERNAL_REFUND_NOT_CONFIRMED"


def test_duplicate_source_identity_is_blocked():
    result = build_treasury_movement_preview(
        sale_payments=[sale_payment(), sale_payment()],
        treasury_accounts=[account()],
    )
    assert all(item["eligibility"] == "BLOCKED" for item in result["candidates"])
    assert all("DUPLICATE_SOURCE_EVENT_IDENTITY" in item["blocking_reasons"] for item in result["candidates"])


def test_float_amount_is_rejected_not_silently_rounded():
    result = build_treasury_movement_preview(
        sale_payments=[sale_payment(amount_dt=25.5)], treasury_accounts=[account()]
    )
    assert "AMOUNT_MISSING_OR_INVALID" in result["candidates"][0]["blocking_reasons"]


def test_malformed_calendar_date_is_blocked():
    result = build_treasury_movement_preview(
        sale_payments=[sale_payment(payment_date="2026-19-42")], treasury_accounts=[account()]
    )
    assert "PAYMENT_DATE_MISSING_OR_INVALID" in result["candidates"][0]["blocking_reasons"]
