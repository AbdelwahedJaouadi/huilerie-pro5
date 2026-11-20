import ast
from pathlib import Path

from accounting_foundation import build_reconciliation_preview


def test_preview_composes_traditional_invoice_and_itemized_receipt_candidates():
    result = build_reconciliation_preview(
        traditional_invoices=[{
            "id": "invoice-1",
            "number": "FAC-001",
            "load_id": "load-1",
            "day": "2026-11-20",
            "total": "100.000",
            "currency": "TND",
            "payments": [{
                "id": "payment-1",
                "amount": "40.000",
                "currency": "TND",
                "at": "2026-11-20",
            }],
            "paid_amount": "40.000",
        }]
    )
    assert result["read_only"] is True
    assert result["database_writes"] is False
    assert result["posting_enabled"] is False
    assert result["summary"]["candidate_event_count"] == 2
    assert result["summary"]["eligibility_counts"] == {
        "LEGACY_UNRESOLVED": 1,
        "ELIGIBLE_FOR_REVIEW": 1,
    }


def test_preview_composes_approved_gs_purchase_and_supplier_payment():
    purchase = {
        "id": "purchase-1",
        "season_code": "2627",
        "document_number": "ACH-0001",
        "status": "APPROVED",
        "supplier_id": "supplier-1",
        "purchase_date": "2026-11-20",
        "lines": [{
            "variety_id": "CHEMLALI",
            "quantity_kg": "100.000",
            "unit_price_dt": "2.500",
            "line_total_dt": "250.000",
        }],
        "total_quantity_kg": "100.000",
        "total_amount_dt": "250.000",
        "lot_ids": ["lot-1"],
        "receipt_movement_ids": ["movement-1"],
        "receiving_location_id": "receiving-1",
        "paid_amount_dt": "50.000",
        "outstanding_amount_dt": "200.000",
    }
    lots = [{
        "id": "lot-1", "source_purchase_id": "purchase-1",
        "product_kind": "OLIVE", "supplier_id": "supplier-1",
        "owner": {"kind": "MILL"}, "variety_id": "CHEMLALI",
        "quantity_received_kg": "100.000",
    }]
    movements = [{
        "id": "movement-1", "source_document_type": "ACH",
        "source_document_id": "purchase-1", "movement_kind": "RECEIPT",
        "product_kind": "OLIVE", "lot_id": "lot-1",
        "destination_owner": {"kind": "MILL"},
        "destination_location_id": "receiving-1", "quantity_kg": "100.000",
    }]
    payments = [{
        "id": "payment-1", "purchase_id": "purchase-1",
        "supplier_id": "supplier-1", "amount_tnd": "50.000",
        "payment_date": "2026-11-20", "currency": "TND",
    }]
    result = build_reconciliation_preview(
        gs_purchases=[purchase], supplier_payments=payments,
        lots=lots, stock_movements=movements,
    )
    events = {event["event_type"]: event for event in result["candidate_events"]}
    assert events["PURCHASE_RECOGNIZED"]["eligibility"] == "ELIGIBLE_FOR_REVIEW"
    assert events["PAYMENT_MADE"]["eligibility"] == "ELIGIBLE_FOR_REVIEW"
    assert result["summary"]["candidate_event_count"] == 2
    assert result["summary"]["unresolved_item_count"] == 0


def test_preview_reports_duplicate_candidate_identity_without_posting():
    invoice = {
        "id": "invoice-1",
        "payments": [
            {"id": "same-payment", "amount": "10", "currency": "TND", "at": "2026-11-20"},
            {"id": "same-payment", "amount": "10", "currency": "TND", "at": "2026-11-20"},
        ],
        "paid_amount": "20",
    }
    result = build_reconciliation_preview(traditional_invoices=[invoice])
    assert result["summary"]["duplicate_candidate_key_count"] == 1
    assert result["summary"]["unresolved_reason_counts"]["DUPLICATE_CANDIDATE_EVENT_IDENTITY"] == 1
    assert all(event["eligibility"] == "BLOCKED" for event in result["candidate_events"] if event["event_type"] == "PAYMENT_RECEIVED")
    assert result["summary"]["eligibility_counts"]["BLOCKED"] == 2
    assert result["posting_enabled"] is False


def test_preview_preserves_unresolved_legacy_paid_aggregate():
    result = build_reconciliation_preview(
        traditional_invoices=[{
            "id": "invoice-1",
            "payments": [],
            "paid_amount": "90.000",
            "history": [{"action": "updated", "at": "2026-11-20"}],
        }]
    )
    reasons = {item["reason"] for item in result["unresolved_items"]}
    assert "LEGACY_PAID_AGGREGATE_WITHOUT_ITEMIZED_RECEIPTS" in reasons
    assert "INVOICE_HISTORY_IS_AUDIT_EVIDENCE_NOT_RECEIPTS" in reasons
    assert result["candidate_events"][0]["event_type"] == "INVOICE_RECOGNIZED"


def test_read_only_preview_route_is_registered_under_accounting():
    source_path = Path(__file__).parents[1] / "routers" / "accounting.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    endpoint = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "accounting_reconciliation_preview"
    )
    decorator = endpoint.decorator_list[0]
    assert isinstance(decorator, ast.Call)
    assert isinstance(decorator.func, ast.Attribute)
    assert decorator.func.attr == "get"
    assert decorator.args[0].value == "/reconciliation-preview"


def test_gs_sales_receipt_and_reversal_are_reconciled_without_posting():
    result=build_reconciliation_preview(
      gs_sales_invoices=[{"id":"i1","season_code":"2627","document_number":"2627F0001","sale_id":"s1","buyer_id":"b1","sale_date":"2026-11-20","total_amount_dt":"100","credited_amount_dt":"0","net_amount_dt":"100","paid_amount_dt":"40"}],
      gs_sale_payments=[{"id":"p1","season_code":"2627","document_number":"PAY-1","invoice_id":"i1","sale_id":"s1","amount_dt":"50","payment_date":"2026-11-20","method":"CASH","treasury_account_id":"cash-1"}],
      gs_sale_reversals=[{"id":"r1","season_code":"2627","document_number":"REV-1","payment_id":"p1","invoice_id":"i1","buyer_id":"b1","amount_dt":"10","reversal_date":"2026-11-20","payment_method":"CASH","treasury_account_id":"cash-1"}],
      treasury_accounts=[{"id":"cash-1","account_type":"CASH","currency":"TND"}])
    by_source={x["source_type"]:x for x in result["candidate_events"]}
    assert by_source["GS_SALE_INVOICE"]["eligibility"]=="INFORMATIONAL_ONLY"
    assert by_source["GS_SALE_PAYMENT"]["eligibility"]=="ELIGIBLE_FOR_REVIEW"
    assert by_source["GS_SALE_PAYMENT_REVERSAL"]["eligibility"]=="ELIGIBLE_FOR_REVIEW"
    assert result["posting_enabled"] is False and result["database_writes"] is False


def test_gs_sales_paid_snapshot_mismatch_blocks_payment_candidate():
    result=build_reconciliation_preview(
      gs_sales_invoices=[{"id":"i1","sale_id":"s1","sale_date":"2026-11-20","total_amount_dt":"100","credited_amount_dt":"0","net_amount_dt":"100","paid_amount_dt":"40"}],
      gs_sale_payments=[{"id":"p1","invoice_id":"i1","sale_id":"s1","amount_dt":"50","payment_date":"2026-11-20","method":"CASH","treasury_account_id":"cash-1"}], treasury_accounts=[{"id":"cash-1","account_type":"CASH","currency":"TND"}])
    payment=next(x for x in result["candidate_events"] if x["source_type"]=="GS_SALE_PAYMENT")
    assert payment["eligibility"]=="BLOCKED"
    assert "INVOICE_PAID_SNAPSHOT_MISMATCH" in payment["blocking_reasons"]


def test_gs_payment_reversal_cannot_exceed_original_payment():
    result=build_reconciliation_preview(
      gs_sales_invoices=[{"id":"i1","sale_id":"s1","sale_date":"2026-11-20","total_amount_dt":"100","credited_amount_dt":"0","net_amount_dt":"100","paid_amount_dt":"0"}],
      gs_sale_payments=[{"id":"p1","invoice_id":"i1","sale_id":"s1","amount_dt":"50","payment_date":"2026-11-20","method":"CASH","treasury_account_id":"cash-1"}],
      gs_sale_reversals=[{"id":"r1","payment_id":"p1","invoice_id":"i1","amount_dt":"60","reversal_date":"2026-11-20","payment_method":"CASH","treasury_account_id":"cash-1"}], treasury_accounts=[{"id":"cash-1","account_type":"CASH","currency":"TND"}])
    reversal=next(x for x in result["candidate_events"] if x["source_type"]=="GS_SALE_PAYMENT_REVERSAL")
    assert reversal["eligibility"]=="BLOCKED"
    assert "REVERSALS_EXCEED_ORIGINAL_PAYMENT" in reversal["blocking_reasons"]
