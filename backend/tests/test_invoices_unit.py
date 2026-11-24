"""Isolated unit tests for invoice business rules; never connect to a real database."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from lib.money import money_float
from routers import invoices as invoice_routes


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.insert_sessions = []

    async def find_one(self, query, projection=None, **kwargs):
        for doc in self.docs:
            if all(
                doc.get(key) != value["$ne"] if isinstance(value, dict) and "$ne" in value
                else doc.get(key) == value
                for key, value in query.items()
            ):
                return dict(doc)
        return None

    async def insert_one(self, doc, **kwargs):
        self.insert_sessions.append(kwargs.get("session"))
        self.docs.append(dict(doc))
        return SimpleNamespace(inserted_id="fake-id")

    async def update_one(self, query, update, **kwargs):
        for doc in self.docs:
            if all(
                doc.get(key) != value["$ne"] if isinstance(value, dict) and "$ne" in value
                else doc.get(key) == value
                for key, value in query.items()
            ):
                doc.update(update.get("$set", {}))
                for key, value in update.get("$push", {}).items():
                    doc.setdefault(key, []).append(value)
                for key, value in update.get("$inc", {}).items():
                    doc[key] = doc.get(key, 0) + value
                return SimpleNamespace(modified_count=1, matched_count=1)
        return SimpleNamespace(modified_count=0, matched_count=0)

    async def count_documents(self, query, **kwargs):
        return len(self.docs)

    async def delete_one(self, query, **kwargs):
        for index, doc in enumerate(self.docs):
            if all(doc.get(key) == value for key, value in query.items()):
                self.docs.pop(index)
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)


@pytest.fixture
def fake_db(monkeypatch):
    load = {
        "id": "load-test-1",
        "code": "2627100",
        "client_name": "Client test",
        "phone": "555-0100",
        "olive_kg": 100.0,
        "oil_kg": 15.0,
        "day": "2026-10-27",
        "season_id": "2026-2027",
        "cancelled": False,
    }
    fake = SimpleNamespace(
        loads=FakeCollection([load]),
        settings=FakeCollection([{"key": "app", "price_per_kg": 0.18}]),
        invoices=FakeCollection(),
        accounting_treasury_accounts=FakeCollection(),
        accounting_treasury_movements=FakeCollection(),
        accounting_treasury_movement_events=FakeCollection(),
        commercial_audit_events=FakeCollection(),
    )
    monkeypatch.setattr(invoice_routes, "db", fake)

    async def fake_transaction(operation):
        return await operation(object())

    monkeypatch.setattr(invoice_routes, "run_transaction", fake_transaction)
    return fake


@pytest.mark.asyncio
async def test_create_invoice_calculates_total_and_balance(fake_db):
    result = await invoice_routes.create_invoice(
        {"load_id": "load-test-1", "paid_amount": 0.5, "payment_method": "CASH"},
        {"username": "admin"},
    )

    assert result["total"] == 2.7
    assert result["paid_amount"] == 0.5
    assert result["balance"] == 2.2
    assert result["load_code"] == "2627100"
    assert result["number"] == "FAC-2627100"
    assert len(result["history"]) == 1
    assert result["history"][0]["after"]["balance"] == 2.2


@pytest.mark.asyncio
async def test_duplicate_invoice_for_same_load_is_rejected(fake_db):
    await invoice_routes.create_invoice(
        {"load_id": "load-test-1", "paid_amount": 0},
        {"username": "admin"},
    )

    with pytest.raises(HTTPException) as exc:
        await invoice_routes.create_invoice(
            {"load_id": "load-test-1", "paid_amount": 0},
            {"username": "admin"},
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_update_recalculates_balance_and_records_history(fake_db):
    created = await invoice_routes.create_invoice(
        {"load_id": "load-test-1", "paid_amount": 0.5, "payment_method": "CASH"},
        {"username": "admin"},
    )

    updated = await invoice_routes.update_invoice(
        created["id"],
        {"price_per_kg": 0.2, "paid_amount": 1.0},
        {"username": "admin"},
    )

    assert updated["total"] == 3.0
    assert updated["paid_amount"] == 1.0
    assert updated["balance"] == 2.0
    assert len(updated["history"]) == 2
    assert updated["history"][-1]["action"] == "updated"
    assert updated["history"][-1]["before"]["balance"] == 2.2
    assert updated["history"][-1]["after"]["balance"] == 2.0
    assert len(fake_db.commercial_audit_events.docs) == 2
    assert fake_db.commercial_audit_events.docs[-1]["action"] == "INVOICE_UPDATED"
    assert money_float(fake_db.commercial_audit_events.docs[-1]["details"]["previous_values"]["balance"]) == 2.2
    assert all(session is not None for session in fake_db.commercial_audit_events.insert_sessions)


@pytest.mark.asyncio
async def test_incremental_payment_is_appended_to_payment_ledger(fake_db):
    created = await invoice_routes.create_invoice(
        {"load_id": "load-test-1", "paid_amount": 0.5, "payment_method": "CASH"},
        {"username": "admin"},
    )

    updated = await invoice_routes.update_invoice(
        created["id"],
        {"payment_amount": 0.75, "payment_method": "CASH"},
        {"username": "cashier"},
    )

    assert updated["paid_amount"] == 1.25
    assert updated["balance"] == 1.45
    assert len(updated["payments"]) == 2
    assert updated["payments"][-1]["by"] == "cashier"
    assert updated["payments"][-1]["amount"] == 0.75
    assert len(updated["history"]) == 2


@pytest.mark.asyncio
async def test_paid_amount_cannot_exceed_total(fake_db):
    with pytest.raises(HTTPException) as exc:
        await invoice_routes.create_invoice(
            {"load_id": "load-test-1", "paid_amount": 2.71, "payment_method": "CASH"},
            {"username": "admin"},
        )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_invoice_keeps_price_snapshot_when_settings_change(fake_db):
    created = await invoice_routes.create_invoice(
        {"load_id": "load-test-1", "paid_amount": 0},
        {"username": "admin"},
    )

    fake_db.settings.docs[0]["price_per_kg"] = 0.25

    assert created["price_per_kg"] == 0.18
    assert created["total"] == 2.7
    assert money_float(fake_db.invoices.docs[0]["price_per_kg"]) == 0.18


@pytest.mark.asyncio
async def test_cancelled_load_cannot_be_invoiced(fake_db):
    fake_db.loads.docs[0]["cancelled"] = True

    with pytest.raises(HTTPException) as exc:
        await invoice_routes.create_invoice(
            {"load_id": "load-test-1", "paid_amount": 0},
            {"username": "admin"},
        )

    assert exc.value.status_code == 400
    assert not fake_db.invoices.docs


@pytest.mark.asyncio
async def test_non_finite_price_update_is_rejected_without_changing_invoice(fake_db):
    created = await invoice_routes.create_invoice(
        {"load_id": "load-test-1", "paid_amount": 0},
        {"username": "admin"},
    )

    with pytest.raises(HTTPException) as exc:
        await invoice_routes.update_invoice(
            created["id"],
            {"price_per_kg": float("nan"), "paid_amount": 0},
            {"username": "admin"},
        )

    assert exc.value.status_code == 422
    assert money_float(fake_db.invoices.docs[0]["price_per_kg"]) == 0.18
    assert len(fake_db.invoices.docs[0]["history"]) == 1


@pytest.mark.asyncio
async def test_update_rejects_payment_above_recalculated_total(fake_db):
    created = await invoice_routes.create_invoice(
        {"load_id": "load-test-1", "paid_amount": 0},
        {"username": "admin"},
    )

    with pytest.raises(HTTPException) as exc:
        await invoice_routes.update_invoice(
            created["id"],
            {"price_per_kg": 0.1, "paid_amount": 11},
            {"username": "admin"},
        )

    assert exc.value.status_code == 422
    assert money_float(fake_db.invoices.docs[0]["price_per_kg"]) == 0.18
    assert money_float(fake_db.invoices.docs[0]["paid_amount"]) == 0
    assert len(fake_db.invoices.docs[0]["history"]) == 1


@pytest.mark.asyncio
async def test_negative_payment_is_rejected(fake_db):
    with pytest.raises(HTTPException) as exc:
        await invoice_routes.create_invoice(
            {"load_id": "load-test-1", "paid_amount": -1},
            {"username": "admin"},
        )

    assert exc.value.status_code == 422
    assert not fake_db.invoices.docs


@pytest.mark.asyncio
async def test_unchanged_invoice_edit_does_not_add_history(fake_db):
    created = await invoice_routes.create_invoice(
        {"load_id": "load-test-1", "paid_amount": 0.5, "payment_method": "CASH"},
        {"username": "admin"},
    )

    updated = await invoice_routes.update_invoice(
        created["id"], {"price_per_kg": 0.18, "paid_amount": 0.5}, {"username": "admin"}
    )

    assert updated["total"] == 2.7
    assert updated["balance"] == 2.2
    assert len(updated["history"]) == 1
    assert len(fake_db.commercial_audit_events.docs) == 1


@pytest.mark.asyncio
async def test_update_with_no_editable_fields_is_rejected_without_history_change(fake_db):
    created = await invoice_routes.create_invoice(
        {"load_id": "load-test-1", "paid_amount": 0},
        {"username": "admin"},
    )

    with pytest.raises(HTTPException) as exc:
        await invoice_routes.update_invoice(
            created["id"], {"unexpected_field": "ignored"}, {"username": "admin"}
        )

    assert exc.value.status_code == 422
    assert exc.value.detail == "no_editable_fields"
    assert len(fake_db.invoices.docs[0]["history"]) == 1


@pytest.mark.asyncio
async def test_concurrent_invoice_edit_is_rejected_without_overwriting_history(fake_db, monkeypatch):
    created = await invoice_routes.create_invoice(
        {"load_id": "load-test-1", "paid_amount": 0.5, "payment_method": "CASH"},
        {"username": "admin"},
    )
    original_update_one = fake_db.invoices.update_one

    async def simulate_concurrent_edit(query, update, **kwargs):
        # Simulate another admin saving the invoice after this request read it.
        fake_db.invoices.docs[0]["updated_at"] = "changed-by-another-edit"
        return await original_update_one(query, update, **kwargs)

    monkeypatch.setattr(fake_db.invoices, "update_one", simulate_concurrent_edit)

    with pytest.raises(HTTPException) as exc:
        await invoice_routes.update_invoice(
            created["id"],
            {"price_per_kg": 0.2, "paid_amount": 0.5},
            {"username": "admin"},
        )

    assert exc.value.status_code == 409
    assert exc.value.detail == "invoice_changed_retry"
    assert money_float(fake_db.invoices.docs[0]["price_per_kg"]) == 0.18
    assert len(fake_db.invoices.docs[0]["history"]) == 1


@pytest.mark.asyncio
async def test_delete_invoice_records_full_snapshot_in_same_transaction(fake_db):
    created = await invoice_routes.create_invoice(
        {"load_id": "load-test-1", "paid_amount": 0.5, "payment_method": "CASH"},
        {"username": "admin"},
    )

    result = await invoice_routes.delete_invoice(created["id"], {"username": "admin"})

    assert result == {"ok": True}
    assert fake_db.invoices.docs == []
    event = fake_db.commercial_audit_events.docs[-1]
    assert event["action"] == "INVOICE_DELETED"
    assert event["details"]["number"] == "FAC-2627100"
    assert money_float(event["details"]["paid_amount"]) == 0.5
    assert all(session is not None for session in fake_db.commercial_audit_events.insert_sessions)


@pytest.mark.asyncio
async def test_initial_cash_payment_creates_one_linked_treasury_movement(fake_db):
    fake_db.accounting_treasury_accounts.docs.append({
        "id": "cash-1", "name": "Caisse", "account_type": "CASH",
        "currency": "TND", "active": True,
    })
    result = await invoice_routes.create_invoice(
        {"load_id": "load-test-1", "paid_amount": 0.5,
         "payment_method": "CASH", "treasury_account_id": "cash-1"},
        {"id": "admin-1", "username": "admin"},
    )
    payment = result["payments"][0]
    assert payment["treasury_allocation_status"] == "MAPPED"
    assert payment["treasury_account_id"] == "cash-1"
    assert len(fake_db.accounting_treasury_movements.docs) == 1
    movement = fake_db.accounting_treasury_movements.docs[0]
    assert movement["source_type"] == "TRADITIONAL_RECEIPT"
    assert movement["source_id"] == payment["id"]
    assert movement["season_code"] == "2627"
    assert movement["opening_balance_applied"] is False
    assert movement["gl_posting_status"] == "NOT_POSTED"
    assert len(fake_db.accounting_treasury_movement_events.docs) == 1


@pytest.mark.asyncio
async def test_initial_bank_transfer_requires_reference_and_compatible_account(fake_db):
    fake_db.accounting_treasury_accounts.docs.append({
        "id": "bank-1", "name": "Banque", "account_type": "BANK",
        "currency": "TND", "active": True,
    })
    with pytest.raises(HTTPException) as exc:
        await invoice_routes.create_invoice(
            {"load_id": "load-test-1", "paid_amount": 0.5,
             "payment_method": "BANK_TRANSFER", "treasury_account_id": "bank-1"},
            {"username": "admin"},
        )
    assert exc.value.detail == "payment_reference_required"
    assert fake_db.invoices.docs == []
    result = await invoice_routes.create_invoice(
        {"load_id": "load-test-1", "paid_amount": 0.5,
         "payment_method": "BANK_TRANSFER", "payment_reference": "VIR-001",
         "treasury_account_id": "bank-1"},
        {"username": "admin"},
    )
    assert result["payments"][0]["reference"] == "VIR-001"
    assert fake_db.accounting_treasury_movements.docs[0]["settlement_status"] == "PENDING_BANK_CONFIRMATION"


@pytest.mark.asyncio
async def test_initial_payment_requires_method_but_zero_payment_does_not(fake_db):
    with pytest.raises(HTTPException) as exc:
        await invoice_routes.create_invoice(
            {"load_id": "load-test-1", "paid_amount": 0.5},
            {"username": "admin"},
        )
    assert exc.value.detail == "payment_method_required"
    assert fake_db.invoices.docs == []
    result = await invoice_routes.create_invoice(
        {"load_id": "load-test-1", "paid_amount": 0},
        {"username": "admin"},
    )
    assert result["payments"] == []
    assert fake_db.accounting_treasury_movements.docs == []


@pytest.mark.asyncio
async def test_initial_payment_without_configured_accounts_is_explicitly_unallocated(fake_db):
    result = await invoice_routes.create_invoice(
        {"load_id": "load-test-1", "paid_amount": 0.5, "payment_method": "CASH"},
        {"username": "admin"},
    )
    assert result["payments"][0]["treasury_allocation_status"] == "UNALLOCATED"
    assert result["payments"][0]["treasury_account_id"] is None
    assert fake_db.accounting_treasury_movements.docs == []


@pytest.mark.asyncio
async def test_initial_payment_rejects_wrong_or_inactive_account(fake_db):
    fake_db.accounting_treasury_accounts.docs.append({
        "id": "bank-1", "name": "Banque", "account_type": "BANK",
        "currency": "TND", "active": False,
    })
    with pytest.raises(HTTPException) as exc:
        await invoice_routes.create_invoice(
            {"load_id": "load-test-1", "paid_amount": 0.5,
             "payment_method": "CASH", "treasury_account_id": "bank-1"},
            {"username": "admin"},
        )
    assert exc.value.detail == "treasury_account_invalid"
    assert fake_db.invoices.docs == []
    assert fake_db.accounting_treasury_movements.docs == []


@pytest.mark.asyncio
async def test_initial_cash_payment_auto_selects_the_only_active_cash_account(fake_db):
    fake_db.accounting_treasury_accounts.docs.append({
        "id": "cash-1", "name": "Caisse", "account_type": "CASH",
        "currency": "TND", "active": True,
    })
    result = await invoice_routes.create_invoice(
        {"load_id": "load-test-1", "paid_amount": 0.5, "payment_method": "CASH"},
        {"id": "admin-1", "username": "admin"},
    )
    payment = result["payments"][0]
    assert payment["treasury_account_id"] == "cash-1"
    assert payment["treasury_allocation_status"] == "MAPPED"
    assert len(fake_db.accounting_treasury_movements.docs) == 1
    assert fake_db.accounting_treasury_movements.docs[0]["source_id"] == payment["id"]


@pytest.mark.asyncio
async def test_incremental_cash_payment_auto_selects_the_only_active_cash_account(fake_db):
    fake_db.accounting_treasury_accounts.docs.append({
        "id": "cash-1", "name": "Caisse", "account_type": "CASH",
        "currency": "TND", "active": True,
    })
    created = await invoice_routes.create_invoice(
        {"load_id": "load-test-1", "paid_amount": 0},
        {"id": "admin-1", "username": "admin"},
    )
    updated = await invoice_routes.update_invoice(
        created["id"],
        {"payment_amount": 0.5, "payment_method": "CASH"},
        {"id": "cashier-1", "username": "cashier"},
    )
    payment = updated["payments"][-1]
    assert payment["treasury_account_id"] == "cash-1"
    assert payment["treasury_allocation_status"] == "MAPPED"
    assert len(fake_db.accounting_treasury_movements.docs) == 1
    assert fake_db.accounting_treasury_movements.docs[0]["source_id"] == payment["id"]
