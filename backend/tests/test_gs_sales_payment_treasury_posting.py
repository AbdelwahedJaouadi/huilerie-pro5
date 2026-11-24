from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from bson.decimal128 import Decimal128

from commercial.schemas.sales import SalePaymentDraft
from commercial.services import sales as sales_service


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, limit):
        return self.rows[:limit]


class FakeCollection:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    async def find_one(self, query, projection=None, **kwargs):
        for row in self.rows:
            if all(row.get(key) == value for key, value in query.items()):
                return dict(row)
        return None

    def find(self, query, projection=None, **kwargs):
        rows = [
            dict(row) for row in self.rows
            if all(row.get(key) == value for key, value in query.items())
        ]
        return FakeCursor(rows)

    async def count_documents(self, query, **kwargs):
        return sum(
            1 for row in self.rows
            if all(row.get(key) == value for key, value in query.items())
        )

    async def insert_one(self, row, **kwargs):
        self.rows.append(dict(row))
        return SimpleNamespace(inserted_id=row.get("id"))

    async def update_one(self, query, update, **kwargs):
        for row in self.rows:
            if all(row.get(key) == value for key, value in query.items()):
                row.update(update.get("$set", {}))
                for key, value in update.get("$inc", {}).items():
                    row[key] = row.get(key, 0) + value
                return SimpleNamespace(matched_count=1, modified_count=1)
        return SimpleNamespace(matched_count=0, modified_count=0)


class FakeDB:
    def __init__(self, **collections):
        self.collections = collections

    def __getitem__(self, key):
        return self.collections.setdefault(key, FakeCollection())


def invoice():
    return {
        "id": "invoice-1",
        "season_code": "2627",
        "sale_id": "sale-1",
        "payment_status": "UNPAID",
        "version": 1,
        "paid_amount_dt": Decimal128("0.000"),
        "outstanding_amount_dt": Decimal128("100.000"),
        "applied_credit_amount_dt": Decimal128("0.000"),
    }


def cash_account(account_id="cash-1"):
    return {
        "id": account_id, "name": "Caisse principale",
        "account_type": "CASH", "currency": "TND", "active": True,
    }


def draft():
    return SalePaymentDraft(
        payment_date=date(2026, 11, 20),
        amount_dt=Decimal("25.000"),
        method="CASH",
        expected_invoice_version=1,
        idempotency_key="cash-payment-auto-account-001",
    )


@pytest.mark.asyncio
async def test_cash_sale_payment_auto_selects_single_active_cash_account(monkeypatch):
    db = FakeDB(
        commercial_sales_invoices=FakeCollection([invoice()]),
        commercial_sale_payments=FakeCollection(),
        accounting_treasury_accounts=FakeCollection([cash_account()]),
        commercial_counters=FakeCollection(),
        commercial_audit_events=FakeCollection(),
    )
    movement_calls = []

    async def no_op_reconcile(*_args, **_kwargs):
        return None

    async def reserve_number(*_args, **_kwargs):
        return "2627PAY0001"

    async def record_movement(*_args, **kwargs):
        movement_calls.append(kwargs)

    monkeypatch.setattr(sales_service, "assert_invoice_receivable_fields_reconcile", no_op_reconcile)
    monkeypatch.setattr(sales_service, "reserve_document_number", reserve_number)
    monkeypatch.setattr(sales_service, "record_source_payment_movement", record_movement)

    payment = await sales_service.record_sale_payment(
        db, "invoice-1", draft(), season_code="2627",
        actor_user={"active": True, "role": "admin"}, actor_user_id="admin-1",
        payment_id="payment-1", audit_event_id="audit-1",
        created_at=datetime(2026, 11, 20, tzinfo=timezone.utc), session=object(),
    )

    assert payment["treasury_account_id"] == "cash-1"
    assert payment["treasury_allocation_status"] == "MAPPED"
    assert len(movement_calls) == 1
    assert movement_calls[0]["source_type"] == "GS_SALE_PAYMENT"
    assert movement_calls[0]["source_id"] == "payment-1"


@pytest.mark.asyncio
async def test_cash_sale_payment_rejects_multiple_active_cash_accounts(monkeypatch):
    db = FakeDB(
        commercial_sales_invoices=FakeCollection([invoice()]),
        commercial_sale_payments=FakeCollection(),
        accounting_treasury_accounts=FakeCollection([cash_account("cash-1"), cash_account("cash-2")]),
        commercial_counters=FakeCollection(),
        commercial_audit_events=FakeCollection(),
    )

    async def no_op_reconcile(*_args, **_kwargs):
        return None

    monkeypatch.setattr(sales_service, "assert_invoice_receivable_fields_reconcile", no_op_reconcile)

    with pytest.raises(ValueError, match="more than one active TND cash account"):
        await sales_service.record_sale_payment(
            db, "invoice-1", draft(), season_code="2627",
            actor_user={"active": True, "role": "admin"}, actor_user_id="admin-1",
            payment_id="payment-1", audit_event_id="audit-1",
            created_at=datetime(2026, 11, 20, tzinfo=timezone.utc), session=object(),
        )

    assert db["commercial_sale_payments"].rows == []
    assert db["accounting_treasury_movements"].rows == []
