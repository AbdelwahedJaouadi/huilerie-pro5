from datetime import datetime, timezone
from decimal import Decimal
import asyncio

from accounting_foundation.traditional_treasury import (
    confirm_traditional_cheque_encashment,
    record_traditional_receipt_movement,
)


class FakeCollection:
    def __init__(self, rows=None):
        self.rows = [dict(row) for row in (rows or [])]

    async def find_one(self, query, projection=None, session=None):
        for row in self.rows:
            if all(row.get(key) == value for key, value in query.items()):
                return dict(row)
        return None

    async def insert_one(self, row, session=None):
        self.rows.append(dict(row))
        return type("InsertResult", (), {"inserted_id": row.get("id")})()

    async def update_one(self, query, update, session=None):
        for row in self.rows:
            if all(row.get(key) == value for key, value in query.items()):
                row.update(update.get("$set", {}))
                return type("UpdateResult", (), {"matched_count": 1, "modified_count": 1})()
        return type("UpdateResult", (), {"matched_count": 0, "modified_count": 0})()


class FakeDB:
    def __init__(self, collections=None):
        self.collections = {key: FakeCollection(rows) for key, rows in (collections or {}).items()}

    def __getattr__(self, name):
        return self.collections.setdefault(name, FakeCollection())


def receipt(method):
    return {
        "id": f"payment-{method.lower()}", "at": datetime(2026, 11, 24, tzinfo=timezone.utc),
        "amount": Decimal("369.000"), "method": method, "currency": "TND",
        "reference": "CHEQUE-2355" if method == "CHEQUE" else None,
    }


def bank_account():
    return {"id": "bank-1", "name": "BNA", "account_type": "BANK", "currency": "TND", "active": True}


def test_cash_receipt_is_reconciled_when_the_movement_is_recorded():
    async def run():
        db = FakeDB()
        movement = await record_traditional_receipt_movement(
            db, invoice={"id": "invoice-1", "number": "FAC-1"},
            payment={**receipt("CASH"), "id": "cash-payment"},
            account={"id": "cash-1", "name": "Caisse principale", "account_type": "CASH", "currency": "TND", "active": True},
            season_code="2627", actor_user_id="admin-1",
            recorded_at=datetime(2026, 11, 24, tzinfo=timezone.utc), session=object(),
        )
        assert movement["settlement_status"] == "CASH_RECORDED"
        assert movement["reconciliation_status"] == "RECONCILED"
        assert len(db.accounting_treasury_movements.rows) == 1
        assert len(db.accounting_treasury_movement_events.rows) == 1

    asyncio.run(run())


def test_cheque_stays_pending_until_confirmed_then_updates_same_movement_once():
    async def run():
        db = FakeDB()
        session = object()
        now = datetime(2026, 11, 24, tzinfo=timezone.utc)
        original = await record_traditional_receipt_movement(
            db, invoice={"id": "invoice-1", "number": "FAC-1"},
            payment=receipt("CHEQUE"), account=bank_account(), season_code="2627",
            actor_user_id="admin-1", recorded_at=now, session=session,
        )
        assert original["settlement_status"] == "PENDING_CHEQUE_CLEARANCE"
        assert original["reconciliation_status"] == "UNRECONCILED"

        cleared = await confirm_traditional_cheque_encashment(
            db, movement_id=original["id"], season_code="2627",
            encashment_date="2026-11-24", bank_reference="BNA-CREDIT-9981",
            actor_user_id="admin-1", confirmed_at=now, session=session,
        )
        assert cleared["id"] == original["id"]
        assert cleared["settlement_status"] == "CHEQUE_CLEARED"
        assert cleared["reconciliation_status"] == "RECONCILED"
        assert cleared["bank_statement_reference"] == "BNA-CREDIT-9981"
        assert len(db.accounting_treasury_movements.rows) == 1
        assert len(db.accounting_treasury_movement_events.rows) == 2
        assert db.accounting_treasury_movement_events.rows[-1]["action"] == "CHEQUE_ENCASHMENT_CONFIRMED"

        repeated = await confirm_traditional_cheque_encashment(
            db, movement_id=original["id"], season_code="2627",
            encashment_date="2026-11-24", bank_reference="BNA-CREDIT-9981",
            actor_user_id="admin-1", confirmed_at=now, session=session,
        )
        assert repeated["id"] == original["id"]
        assert len(db.accounting_treasury_movements.rows) == 1
        assert len(db.accounting_treasury_movement_events.rows) == 2

    asyncio.run(run())


def test_cheque_confirmation_rejects_wrong_source_or_non_pending_status():
    async def run():
        wrong = {"id": "movement-1", "season_code": "2627", "source_type": "GS_SALE_PAYMENT",
                 "payment_method": "CHEQUE", "direction": "IN", "account_type": "BANK",
                 "settlement_status": "PENDING_CHEQUE_CLEARANCE"}
        db = FakeDB({"accounting_treasury_movements": [wrong]})
        try:
            await confirm_traditional_cheque_encashment(
                db, movement_id="movement-1", season_code="2627", encashment_date="2026-11-24",
                bank_reference="BNA-1", actor_user_id="admin-1",
                confirmed_at=datetime.now(timezone.utc), session=object(),
            )
        except ValueError as exc:
            assert "traditional cheque" in str(exc)
        else:
            raise AssertionError("Non-traditional source must not be confirmed")
        assert len(db.accounting_treasury_movement_events.rows) == 0

    asyncio.run(run())
