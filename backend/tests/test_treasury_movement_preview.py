from accounting_foundation.treasury_preview import build_treasury_movement_preview


def account(account_id="cash-1", account_type="CASH", active=True, currency="TND"):
    return {"id": account_id, "name": "Main account", "account_type": account_type,
            "active": active, "currency": currency}


def supplier_purchase():
    return {"id": "purchase-1", "status": "APPROVED", "supplier_id": "supplier-1"}


def sale_payment(**overrides):
    row = {"id": "sale-pay-1", "document_number": "PAY-1", "amount_dt": "25.500",
           "payment_date": "2026-11-20", "method": "CASH", "treasury_allocation_status": "MAPPED",
           "treasury_account_id": "cash-1", "invoice_id": "invoice-1", "sale_id": "sale-1"}
    return {**row, **overrides}


def supplier_payment(**overrides):
    row = {"id": "supplier-pay-1", "document_number": "SP-1", "amount_tnd": "10.000",
           "payment_date": "2026-11-20", "method": "CASH", "treasury_allocation_status": "MAPPED",
           "treasury_account_id": "cash-1", "purchase_id": "purchase-1", "supplier_id": "supplier-1"}
    return {**row, **overrides}


def test_sale_receipt_proposes_inflow_without_creating_a_movement():
    result = build_treasury_movement_preview(sale_payments=[sale_payment()], sale_invoices=[{"id":"invoice-1","sale_id":"sale-1","buyer_id":"buyer-1"}], treasury_accounts=[account()])
    candidate = result["candidates"][0]
    assert candidate["direction"] == "IN"
    assert candidate["amount"] == "25.500"
    assert candidate["eligibility"] == "ELIGIBLE_FOR_REVIEW"
    assert result["movement_creation_enabled"] is True
    assert result["database_writes"] is False


def test_supplier_payment_proposes_outflow_not_a_second_expense():
    result = build_treasury_movement_preview(supplier_payments=[supplier_payment()], supplier_purchases=[supplier_purchase()], treasury_accounts=[account()])
    candidate = result["candidates"][0]
    assert candidate["direction"] == "OUT"
    assert candidate["source_type"] == "GS_SUPPLIER_PAYMENT"
    assert candidate["amount"] == "10.000"


def test_missing_or_inactive_or_wrong_type_account_is_blocked():
    missing = build_treasury_movement_preview(sale_payments=[sale_payment(treasury_account_id=None)], sale_invoices=[{"id":"invoice-1","sale_id":"sale-1"}])
    inactive = build_treasury_movement_preview(sale_payments=[sale_payment()], sale_invoices=[{"id":"invoice-1","sale_id":"sale-1"}], treasury_accounts=[account(active=False)])
    wrong = build_treasury_movement_preview(sale_payments=[sale_payment()], sale_invoices=[{"id":"invoice-1","sale_id":"sale-1"}], treasury_accounts=[account(account_type="BANK")])
    assert "TREASURY_ACCOUNT_NOT_ASSIGNED" in missing["candidates"][0]["blocking_reasons"]
    assert "TREASURY_ACCOUNT_INACTIVE" in inactive["candidates"][0]["blocking_reasons"]
    assert "TREASURY_ACCOUNT_TYPE_MISMATCH" in wrong["candidates"][0]["blocking_reasons"]


def test_bank_transfer_is_flagged_as_not_cleared():
    result = build_treasury_movement_preview(
        sale_payments=[sale_payment(method="BANK_TRANSFER")],
        sale_invoices=[{"id":"invoice-1","sale_id":"sale-1"}],
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
        sale_payments=[sale_payment(amount_dt=25.5)], sale_invoices=[{"id":"invoice-1","sale_id":"sale-1"}], treasury_accounts=[account()]
    )
    assert "AMOUNT_MISSING_OR_INVALID" in result["candidates"][0]["blocking_reasons"]


def test_malformed_calendar_date_is_blocked():
    result = build_treasury_movement_preview(
        sale_payments=[sale_payment(payment_date="2026-19-42")], sale_invoices=[{"id":"invoice-1","sale_id":"sale-1"}], treasury_accounts=[account()]
    )
    assert "PAYMENT_DATE_MISSING_OR_INVALID" in result["candidates"][0]["blocking_reasons"]


def test_payment_with_missing_source_document_is_blocked():
    result = build_treasury_movement_preview(sale_payments=[sale_payment()], treasury_accounts=[account()])
    assert "PAYMENT_INVOICE_NOT_FOUND" in result["candidates"][0]["blocking_reasons"]


def test_supplier_payment_requires_approved_matching_purchase():
    result = build_treasury_movement_preview(
        supplier_payments=[supplier_payment()], supplier_purchases=[{**supplier_purchase(), "status": "DRAFT"}],
        treasury_accounts=[account()],
    )
    assert "SUPPLIER_PURCHASE_LINK_INVALID" in result["candidates"][0]["blocking_reasons"]


def test_payment_requires_explicit_mapped_allocation_status():
    result = build_treasury_movement_preview(
        sale_payments=[sale_payment(treasury_allocation_status="UNALLOCATED")],
        sale_invoices=[{"id":"invoice-1","sale_id":"sale-1"}], treasury_accounts=[account()],
    )
    assert "TREASURY_ALLOCATION_STATUS_INVALID" in result["candidates"][0]["blocking_reasons"]


def test_amount_with_excess_precision_is_blocked():
    result = build_treasury_movement_preview(
        sale_payments=[sale_payment(amount_dt="25.5001")],
        sale_invoices=[{"id":"invoice-1","sale_id":"sale-1"}], treasury_accounts=[account()],
    )
    assert "AMOUNT_MISSING_OR_INVALID" in result["candidates"][0]["blocking_reasons"]


def test_bank_payment_requires_reference():
    result = build_treasury_movement_preview(
        sale_payments=[sale_payment(method="BANK_TRANSFER", reference=None)],
        sale_invoices=[{"id":"invoice-1","sale_id":"sale-1"}], treasury_accounts=[account(account_type="BANK")],
    )
    assert "BANK_OR_CHEQUE_REFERENCE_MISSING" in result["candidates"][0]["blocking_reasons"]


def test_sale_payment_requires_nonempty_matching_sale_identity():
    result = build_treasury_movement_preview(
        sale_payments=[sale_payment(sale_id=None)],
        sale_invoices=[{"id":"invoice-1","sale_id":None}],
        treasury_accounts=[account()],
    )
    assert "PAYMENT_SALE_LINK_MISMATCH" in result["candidates"][0]["blocking_reasons"]


def test_supplier_payment_requires_nonempty_matching_supplier_identity():
    result = build_treasury_movement_preview(
        supplier_payments=[supplier_payment(supplier_id=None)],
        supplier_purchases=[{**supplier_purchase(), "supplier_id": None}],
        treasury_accounts=[account()],
    )
    assert "PAYMENT_SUPPLIER_LINK_MISMATCH" in result["candidates"][0]["blocking_reasons"]


def test_traditional_receipt_with_stable_id_is_proposed_as_inflow():
    payment = {
        "id": "traditional-payment-1", "invoice_id": "invoice-trad-1",
        "invoice_number": "FAC-2026-01", "amount": "12.500",
        "at": "2026-11-20T10:00:00+01:00", "method": "CASH",
        "currency": "TND", "treasury_account_id": "cash-1",
        "treasury_allocation_status": "MAPPED",
    }
    result = build_treasury_movement_preview(
        traditional_receipts=[payment], treasury_accounts=[account()],
    )
    candidate = result["candidates"][0]
    assert candidate["source_type"] == "TRADITIONAL_RECEIPT"
    assert candidate["source_id"] == "traditional-payment-1"
    assert candidate["direction"] == "IN"
    assert candidate["amount"] == "12.500"
    assert candidate["business_date"] == "2026-11-20"
    assert candidate["eligibility"] == "ELIGIBLE_FOR_REVIEW"
    assert candidate["blocking_reasons"] == []


def test_traditional_legacy_receipt_without_id_is_unresolved_not_synthesized():
    result = build_treasury_movement_preview(
        traditional_receipts=[{"invoice_id": "legacy-invoice", "amount": "12.500", "at": "2026-11-20"}],
        treasury_accounts=[account()],
    )
    assert result["candidates"] == []
    assert result["unresolved_items"][0]["reason"] == "PAYMENT_CHILD_ID_MISSING"


def test_traditional_bank_receipt_requires_reference_and_bank_account():
    payment = {
        "id": "traditional-payment-2", "amount": "12.500", "at": "2026-11-20",
        "method": "BANK_TRANSFER", "currency": "TND", "treasury_account_id": "bank-1",
        "treasury_allocation_status": "MAPPED",
    }
    result = build_treasury_movement_preview(
        traditional_receipts=[payment],
        treasury_accounts=[account("bank-1", "BANK")],
    )
    assert "BANK_OR_CHEQUE_REFERENCE_MISSING" in result["candidates"][0]["blocking_reasons"]
