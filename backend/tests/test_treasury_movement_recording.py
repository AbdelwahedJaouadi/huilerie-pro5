from datetime import datetime, timezone
from decimal import Decimal
import asyncio

from accounting_foundation.treasury_posting import build_movement_document, record_source_payment_movement


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
    assert row["reconciliation_status"] == "RECONCILED"
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
    assert row["reconciliation_status"] == "UNRECONCILED"
    assert row["external_reference"] == "REF-123"


def test_cheque_is_not_treated_as_cleared():
    row = build_movement_document(
        candidate(method="CHEQUE"), season_code="2627", actor_user_id="admin-1",
        movement_id="movement-3", recorded_at=datetime(2026, 11, 20, tzinfo=timezone.utc),
    )
    assert row["settlement_status"] == "PENDING_CHEQUE_CLEARANCE"
    assert row["reconciliation_status"] == "UNRECONCILED"


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


class FakeCollection:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    async def find_one(self, query, projection=None, session=None):
        for row in self.rows:
            if all(row.get(key) == value for key, value in query.items()):
                return dict(row)
        return None

    async def insert_one(self, row, session=None):
        self.rows.append(dict(row))
        return type("InsertResult", (), {"inserted_id": row.get("id")})()


class FakeDB:
    def __init__(self, collections):
        self.collections = {key: FakeCollection(value) for key, value in collections.items()}

    def __getitem__(self, key):
        return self.collections.setdefault(key, FakeCollection())


def test_source_payment_recording_is_idempotent_and_audited():
    async def run():
        db = FakeDB({
            "commercial_sale_payments": [{
                "id": "payment-1", "season_code": "2627", "document_number": "PAY-1",
                "invoice_id": "invoice-1", "sale_id": "sale-1", "amount_dt": "25.500",
                "payment_date": "2026-11-20", "method": "CASH",
                "treasury_account_id": "cash-1", "treasury_allocation_status": "MAPPED",
            }],
            "commercial_sales_invoices": [{
                "id": "invoice-1", "season_code": "2627", "sale_id": "sale-1", "buyer_id": "buyer-1",
            }],
            "accounting_treasury_accounts": [{
                "id": "cash-1", "name": "Main cash", "account_type": "CASH", "currency": "TND", "active": True,
            }],
        })
        kwargs = dict(
            source_type="GS_SALE_PAYMENT", source_id="payment-1", season_code="2627",
            actor_user_id="admin-1", recorded_at=datetime(2026, 11, 20, tzinfo=timezone.utc), session=object(),
        )
        first = await record_source_payment_movement(db, **kwargs)
        second = await record_source_payment_movement(db, **kwargs)
        assert first["id"] == second["id"]
        assert len(db["accounting_treasury_movements"].rows) == 1
        assert len(db["accounting_treasury_movement_events"].rows) == 1
        assert first["source_document_id"] == "invoice-1"
        assert first["reconciliation_status"] == "RECONCILED"
        assert db["accounting_treasury_movement_events"].rows[0]["details"]["reconciliation_status"] == "RECONCILED"

    asyncio.run(run())


def test_supplier_payment_recording_rejects_unapproved_purchase():
    async def run():
        db = FakeDB({
            "commercial_supplier_olive_purchase_payments": [{
                "id": "supplier-payment-1", "season_code": "2627", "purchase_id": "purchase-1",
                "supplier_id": "supplier-1", "amount_tnd": "10.000", "payment_date": "2026-11-20",
                "method": "CASH", "treasury_account_id": "cash-1", "treasury_allocation_status": "MAPPED",
            }],
            "commercial_olive_purchases": [{
                "id": "purchase-1", "season_code": "2627", "status": "DRAFT", "supplier_id": "supplier-1",
            }],
            "accounting_treasury_accounts": [{
                "id": "cash-1", "name": "Main cash", "account_type": "CASH", "currency": "TND", "active": True,
            }],
        })
        try:
            await record_source_payment_movement(
                db, source_type="GS_SUPPLIER_PAYMENT", source_id="supplier-payment-1",
                season_code="2627", actor_user_id="admin-1",
                recorded_at=datetime(2026, 11, 20, tzinfo=timezone.utc), session=object(),
            )
        except ValueError as exc:
            assert "SUPPLIER_PURCHASE_LINK_INVALID" in str(exc)
        else:
            raise AssertionError("Unapproved supplier purchase must block movement recording")
        assert db["accounting_treasury_movements"].rows == []

    asyncio.run(run())
