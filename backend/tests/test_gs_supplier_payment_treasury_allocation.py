from accounting_foundation.commercial import adapt_gs_supplier_payments


def supplier_purchase():
    return {
        "id": "purchase-1", "status": "APPROVED", "supplier_id": "supplier-1",
        "total_amount_dt": "100.000", "paid_amount_dt": "20.000",
        "outstanding_amount_dt": "80.000",
    }


def supplier_payment(account_id=None, allocation="MAPPED", method="CASH"):
    return {
        "id": "supplier-payment-1", "purchase_id": "purchase-1",
        "supplier_id": "supplier-1", "amount_tnd": "20.000",
        "payment_date": "2026-11-20", "currency": "TND",
        "method": method, "treasury_account_id": account_id,
        "treasury_allocation_status": allocation,
    }


def supplier_event(payment_doc, accounts=()):
    result = adapt_gs_supplier_payments(
        [payment_doc], purchase=supplier_purchase(), treasury_accounts=accounts
    )
    return result["candidate_events"][0]


def test_supplier_payment_without_accounts_keeps_legacy_unallocated_compatibility():
    event = supplier_event(supplier_payment(account_id=None, allocation="UNALLOCATED"))
    assert event["eligibility"] == "ELIGIBLE_FOR_REVIEW"
    assert "LEGACY_TREASURY_ALLOCATION_NOT_CONFIGURED" in event["warnings"]


def test_supplier_payment_is_blocked_when_treasury_directory_exists_but_account_missing():
    event = supplier_event(
        supplier_payment(account_id=None, allocation="UNALLOCATED"),
        [{"id": "cash-1", "account_type": "CASH", "currency": "TND", "active": True}],
    )
    assert event["eligibility"] == "BLOCKED"
    assert "TREASURY_ACCOUNT_NOT_ASSIGNED" in event["blocking_reasons"]


def test_supplier_payment_requires_matching_active_tnd_account():
    event = supplier_event(
        supplier_payment(account_id="bank-1", method="CASH"),
        [{"id": "bank-1", "account_type": "BANK", "currency": "TND", "active": True}],
    )
    assert event["eligibility"] == "BLOCKED"
    assert "TREASURY_ACCOUNT_TYPE_MISMATCH" in event["blocking_reasons"]


def test_supplier_payment_rejects_inactive_or_non_tnd_treasury_account():
    inactive = supplier_event(
        supplier_payment(account_id="cash-1"),
        [{"id": "cash-1", "account_type": "CASH", "currency": "TND", "active": False}],
    )
    non_tnd = supplier_event(
        supplier_payment(account_id="cash-1"),
        [{"id": "cash-1", "account_type": "CASH", "currency": "EUR", "active": True}],
    )
    assert "TREASURY_ACCOUNT_INACTIVE" in inactive["blocking_reasons"]
    assert "TREASURY_ACCOUNT_CURRENCY_NOT_TND" in non_tnd["blocking_reasons"]


def test_supplier_payment_with_valid_account_is_eligible_for_review():
    event = supplier_event(
        supplier_payment(account_id="cash-1"),
        [{"id": "cash-1", "account_type": "CASH", "currency": "TND", "active": True}],
    )
    assert event["eligibility"] == "ELIGIBLE_FOR_REVIEW"
    assert "TREASURY_ACCOUNT_MAPPED" in event["warnings"]
