from accounting_foundation import adapt_gs_olive_purchase, adapt_gs_supplier_payments


def approved_purchase():
    return {
        "id": "purchase-1",
        "season_code": "2627",
        "document_number": "ACH-0001",
        "status": "APPROVED",
        "supplier_id": "supplier-1",
        "purchase_date": "2026-11-20",
        "created_at": "2026-11-20T10:00:00+01:00",
        "approved_by": "employee-1",
        "lines": [{
            "variety_id": "CHEMLALI",
            "quantity_kg": "100.000",
            "unit_price_dt": "2.500",
            "line_total_dt": "250.000",
        }],
        "total_quantity_kg": "100.000",
        "total_amount_dt": "250.000",
        "batch_code": "2627A0001",
        "lot_ids": ["lot-1"],
        "receipt_movement_ids": ["movement-1"],
        "receiving_location_id": "receiving-1",
        "paid_amount_dt": "50.000",
        "outstanding_amount_dt": "200.000",
    }


def matching_stock_evidence():
    lots = [{
        "id": "lot-1",
        "source_purchase_id": "purchase-1",
        "product_kind": "OLIVE",
        "supplier_id": "supplier-1",
        "owner": {"kind": "MILL"},
        "variety_id": "CHEMLALI",
        "quantity_received_kg": "100.000",
    }]
    movements = [{
        "id": "movement-1",
        "source_document_type": "ACH",
        "source_document_id": "purchase-1",
        "movement_kind": "RECEIPT",
        "product_kind": "OLIVE",
        "lot_id": "lot-1",
        "destination_owner": {"kind": "MILL"},
        "destination_location_id": "receiving-1",
        "quantity_kg": "100.000",
    }]
    return lots, movements


def test_draft_purchase_is_informational_and_not_a_recognized_stock_event():
    purchase = approved_purchase()
    purchase["status"] = "DRAFT"
    result = adapt_gs_olive_purchase(purchase)
    assert result["candidate_event"]["eligibility"] == "INFORMATIONAL_ONLY"
    assert result["candidate_event"]["amount"] == "250"
    assert result["candidate_event"]["quantity"] == "100"
    assert "PURCHASE_NOT_APPROVED_NO_RECOGNIZED_STOCK_EVENT" in result["candidate_event"]["warnings"]


def test_approved_purchase_is_reviewable_only_after_line_lot_and_movement_reconciliation():
    lots, movements = matching_stock_evidence()
    result = adapt_gs_olive_purchase(approved_purchase(), lots=lots, movements=movements)
    event = result["candidate_event"]
    assert event["eligibility"] == "ELIGIBLE_FOR_REVIEW"
    assert event["source_type"] == "GS_OLIVE_PURCHASE"
    assert event["event_type"] == "PURCHASE_RECOGNIZED"
    assert event["currency"] == "TND"
    assert event["amount"] == "250"
    assert event["quantity"] == "100"
    assert event["ownership"] == {"owner_kind": "MILL"}
    assert event["warnings"] == ["VALUATION_POLICY_NOT_APPROVED_COST_LAYER_NOT_CREATED"]


def test_purchase_missing_receipt_evidence_is_blocked():
    result = adapt_gs_olive_purchase(approved_purchase())
    assert result["candidate_event"]["eligibility"] == "BLOCKED"
    assert "PURCHASE_LOT_DOCUMENT_MISSING" in result["blocking_reasons"]
    assert "PURCHASE_RECEIPT_MOVEMENT_MISSING" in result["blocking_reasons"]


def test_purchase_stock_quantity_mismatch_is_blocked():
    lots, movements = matching_stock_evidence()
    movements[0]["quantity_kg"] = "99.000"
    result = adapt_gs_olive_purchase(approved_purchase(), lots=lots, movements=movements)
    assert result["candidate_event"]["eligibility"] == "BLOCKED"
    assert "PURCHASE_STOCK_MOVEMENT_SOURCE_OWNER_LOCATION_OR_QUANTITY_MISMATCH" in result["blocking_reasons"]


def test_purchase_wrong_owner_or_location_is_blocked():
    lots, movements = matching_stock_evidence()
    lots[0]["owner"] = {"kind": "CUSTOMER"}
    movements[0]["destination_location_id"] = "wrong-location"
    result = adapt_gs_olive_purchase(approved_purchase(), lots=lots, movements=movements)
    assert result["candidate_event"]["eligibility"] == "BLOCKED"
    assert "PURCHASE_LOT_SOURCE_OWNER_OR_QUANTITY_MISMATCH" in result["blocking_reasons"]
    assert "PURCHASE_STOCK_MOVEMENT_SOURCE_OWNER_LOCATION_OR_QUANTITY_MISMATCH" in result["blocking_reasons"]


def test_purchase_line_amount_mismatch_is_blocked():
    purchase = approved_purchase()
    purchase["lines"][0]["line_total_dt"] = "249.000"
    lots, movements = matching_stock_evidence()
    result = adapt_gs_olive_purchase(purchase, lots=lots, movements=movements)
    assert result["candidate_event"]["eligibility"] == "BLOCKED"
    assert "PURCHASE_LINE_AMOUNT_OR_QUANTITY_MISMATCH" in result["blocking_reasons"]


def test_purchase_duplicate_stock_links_are_blocked():
    purchase = approved_purchase()
    purchase["lines"].append({
        "variety_id": "CHEMLALI",
        "quantity_kg": "100.000",
        "unit_price_dt": "2.500",
        "line_total_dt": "250.000",
    })
    purchase["total_quantity_kg"] = "200.000"
    purchase["total_amount_dt"] = "500.000"
    purchase["lot_ids"] = ["lot-1", "lot-1"]
    purchase["receipt_movement_ids"] = ["movement-1", "movement-1"]
    lots, movements = matching_stock_evidence()
    result = adapt_gs_olive_purchase(purchase, lots=lots, movements=movements)
    assert result["candidate_event"]["eligibility"] == "BLOCKED"
    assert "PURCHASE_LOT_LINKS_DUPLICATED_OR_UNRESOLVED" in result["blocking_reasons"]
    assert "PURCHASE_MOVEMENT_LINKS_DUPLICATED_OR_UNRESOLVED" in result["blocking_reasons"]


def test_supplier_payment_is_a_settlement_not_a_purchase_expense():
    purchase = approved_purchase()
    payment = {
        "id": "payment-1",
        "season_code": "2627",
        "document_number": "RFS-0001",
        "purchase_id": "purchase-1",
        "purchase_number": "ACH-0001",
        "supplier_id": "supplier-1",
        "amount_tnd": "50.000",
        "payment_date": "2026-11-20",
        "currency": "TND",
        "method": "CASH",
        "created_by": "employee-1",
        "created_at": "2026-11-20T12:00:00+01:00",
    }
    result = adapt_gs_supplier_payments([payment], purchase=purchase)
    event = result["candidate_events"][0]
    assert event["eligibility"] == "ELIGIBLE_FOR_REVIEW"
    assert event["event_type"] == "PAYMENT_MADE"
    assert event["amount"] == "50"
    assert event["currency"] == "TND"
    assert event["source_links"] == [{"type": "GS_OLIVE_PURCHASE", "id": "purchase-1"}]
    assert result["payments_are_purchase_expenses"] is False
    assert result["unresolved_items"] == []


def test_supplier_payment_snapshot_mismatch_is_reported():
    purchase = approved_purchase()
    payment = {
        "id": "payment-1",
        "purchase_id": "purchase-1",
        "supplier_id": "supplier-1",
        "amount_tnd": "45.000",
        "payment_date": "2026-11-20",
    }
    result = adapt_gs_supplier_payments([payment], purchase=purchase)
    assert any(
        item["reason"] == "SUPPLIER_PAYMENT_LEDGER_DOES_NOT_MATCH_PAID_SNAPSHOT"
        for item in result["unresolved_items"]
    )


def test_supplier_payment_wrong_purchase_is_blocked():
    purchase = approved_purchase()
    payment = {
        "id": "payment-1",
        "purchase_id": "other-purchase",
        "supplier_id": "supplier-1",
        "amount_tnd": "50.000",
        "payment_date": "2026-11-20",
    }
    result = adapt_gs_supplier_payments([payment], purchase=purchase)
    assert result["candidate_events"][0]["eligibility"] == "BLOCKED"
    assert "PAYMENT_PURCHASE_LINK_MISMATCH" in result["candidate_events"][0]["blocking_reasons"]


def test_supplier_payment_missing_id_is_not_given_synthetic_identity():
    purchase = approved_purchase()
    payment = {
        "purchase_id": "purchase-1",
        "supplier_id": "supplier-1",
        "amount_tnd": "50.000",
        "payment_date": "2026-11-20",
    }
    result = adapt_gs_supplier_payments([payment], purchase=purchase)
    assert result["candidate_events"] == []
    assert result["unresolved_items"][0]["reason"] == "PAYMENT_DOCUMENT_ID_MISSING"


def test_duplicate_supplier_payment_ids_are_blocked():
    purchase = approved_purchase()
    payment = {
        "id": "payment-1",
        "purchase_id": "purchase-1",
        "supplier_id": "supplier-1",
        "amount_tnd": "25.000",
        "payment_date": "2026-11-20",
    }
    result = adapt_gs_supplier_payments([payment, dict(payment)], purchase=purchase)
    assert len(result["candidate_events"]) == 2
    assert all(event["eligibility"] == "BLOCKED" for event in result["candidate_events"])
    assert all("DUPLICATE_SUPPLIER_PAYMENT_ID" in event["blocking_reasons"] for event in result["candidate_events"])


def test_supplier_payment_currency_and_date_gaps_block_review():
    purchase = approved_purchase()
    payment = {
        "id": "payment-1",
        "purchase_id": "purchase-1",
        "supplier_id": "supplier-1",
        "amount_tnd": "50.000",
        "currency": "EUR",
        "payment_date": "not-a-date",
    }
    result = adapt_gs_supplier_payments([payment], purchase=purchase)
    reasons = set(result["candidate_events"][0]["blocking_reasons"])
    assert "PAYMENT_CURRENCY_NOT_TND" in reasons
    assert "PAYMENT_DATE_MISSING_OR_INVALID" in reasons
