from routers.accounting import _sum_pipeline


def test_accounting_sum_converts_amounts_to_decimal_before_aggregation():
    pipeline = _sum_pipeline("net_amount_dt")

    assert pipeline[0] == {
        "$group": {
            "_id": None,
            "total": {
                "$sum": {
                    "$convert": {
                        "input": "$net_amount_dt",
                        "to": "decimal",
                        "onError": 0,
                        "onNull": 0,
                    }
                }
            },
        }
    }
    assert pipeline[1] == {
        "$project": {"_id": 0, "total": {"$toString": "$total"}}
    }


def test_accounting_sum_applies_source_document_filters_before_grouping():
    match = {
        "status": "APPROVED",
        "movement_kind": "OWNERSHIP_TRANSFER",
        "product_kind": "OLIVE",
        "consideration.type": "SALE",
    }
    pipeline = _sum_pipeline("consideration.agreed_amount", match)

    assert pipeline[0] == {"$match": match}
    assert pipeline[1]["$group"]["total"]["$sum"]["$convert"]["input"] == (
        "$consideration.agreed_amount"
    )


from datetime import datetime, timezone
from decimal import Decimal

from routers.accounting import _accounting_day, _accounting_decimal, _daily_event


def test_accounting_day_uses_tunis_business_timezone_for_timestamps():
    timestamp = datetime(2026, 11, 12, 23, 30, tzinfo=timezone.utc)
    assert _accounting_day(timestamp) == "2026-11-13"


def test_accounting_day_preserves_explicit_business_date():
    assert _accounting_day("2026-11-12") == "2026-11-12"


def test_daily_event_keeps_millime_precision_without_float_rounding():
    events = []
    _daily_event(
        events, day="2026-11-12", category="Prestation",
        label="Facture", reference="FAC-1", amount="1999.800",
        kind="revenue",
    )
    assert events == [{
        "date": "2026-11-12", "category": "Prestation",
        "label": "Facture", "reference": "FAC-1",
        "amount": "1999.800", "kind": "revenue", "detail": "",
    }]


def test_accounting_decimal_handles_decimal_and_invalid_values():
    assert _accounting_decimal("1.250") == Decimal("1.250")
    assert _accounting_decimal("not-a-number") == Decimal("0.000")

def test_traditional_invoice_itemized_payment_is_not_counted_again_from_history():
    from routers.accounting import _accounting_decimal, _accounting_day, _daily_event

    invoice = {
        "number": "FAC-TEST-1",
        "client_name": "Client test",
        "paid_amount": "100.000",
        "payments": [{"amount": "100.000", "at": "2026-11-20T10:00:00+01:00"}],
        "history": [{
            "action": "updated",
            "at": "2026-11-20T10:00:00+01:00",
            "before": {"paid_amount": "0.000"},
            "after": {"paid_amount": "100.000"},
        }],
    }
    events = []
    known_paid = Decimal("0.000")
    for payment in invoice["payments"]:
        amount = _accounting_decimal(payment.get("amount"))
        payment_day = _accounting_day(payment.get("at") or payment.get("date"))
        if amount > 0 and payment_day:
            _daily_event(events, day=payment_day, category="Prestation",
                         label="Encaissement facture", reference=invoice["number"],
                         amount=amount, kind="receipt", detail=invoice["client_name"])
            known_paid += amount

    unallocated = max(Decimal("0"), _accounting_decimal(invoice["paid_amount"]) - known_paid)
    assert len(events) == 1
    assert events[0]["amount"] == "100.000"
    assert sum((Decimal(row["amount"]) for row in events), Decimal("0")) == Decimal("100.000")
    assert unallocated == Decimal("0.000")


def test_traditional_invoice_legacy_paid_amount_without_itemized_payment_is_unallocated():
    from routers.accounting import _accounting_decimal

    invoice = {"paid_amount": "75.000", "payments": [], "history": [{
        "action": "updated",
        "at": "2026-11-20T10:00:00+01:00",
        "before": {"paid_amount": "0.000"},
        "after": {"paid_amount": "75.000"},
    }]}
    known_paid = Decimal("0.000")
    unallocated = max(Decimal("0"), _accounting_decimal(invoice["paid_amount"]) - known_paid)

    assert unallocated == Decimal("75.000")


def test_traditional_invoice_partial_itemized_payments_leave_legacy_remainder_unallocated():
    from routers.accounting import _accounting_decimal

    invoice = {"paid_amount": "100.000", "payments": [{"amount": "60.000"}]}
    known_paid = sum((_accounting_decimal(row["amount"]) for row in invoice["payments"]), Decimal("0.000"))
    unallocated = max(Decimal("0"), _accounting_decimal(invoice["paid_amount"]) - known_paid)

    assert known_paid == Decimal("60.000")
    assert unallocated == Decimal("40.000")

