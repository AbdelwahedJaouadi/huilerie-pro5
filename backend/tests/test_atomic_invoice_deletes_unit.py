from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from lib import db as db_module
from routers import extras, invoices, loads


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def with_transaction(self, operation):
        return await operation(self)


class FakeClient:
    async def start_session(self):
        return FakeSession()


class FakeDB(SimpleNamespace):
    def __getitem__(self, name):
        return getattr(self, name)


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    async def to_list(self, _length):
        return list(self.docs)


class FakeCollection:
    """Minimal async collection fake for linked-history existence checks."""

    def __init__(self, calls=None):
        self.calls = calls if calls is not None else []

    async def find_one(self, query, projection=None, **kwargs):
        self.calls.append("linked-history-check")
        return None


class FakeAuditEvents:
    def __init__(self, calls=None):
        self.calls = calls if calls is not None else []
        self.events = []

    async def insert_one(self, event, **kwargs):
        assert kwargs.get("session") is not None
        self.calls.append("audit-event")
        self.events.append(dict(event))


@pytest.mark.asyncio
async def test_run_transaction_uses_session_with_transaction(monkeypatch):
    monkeypatch.setattr(db_module, "client", FakeClient())
    seen = []

    async def operation(session):
        seen.append(session)
        return "committed"

    result = await db_module.run_transaction(operation)

    assert result == "committed"
    assert len(seen) == 1


@pytest.mark.asyncio
async def test_invoice_creation_writes_source_load_and_invoice_in_same_session(monkeypatch):
    session = object()
    load = {
        "id": "load-1", "code": "2627101", "client_name": "Test client",
        "phone": "21600000000", "olive_kg": 100.0, "oil_kg": 20.0,
        "day": "2026-11-01", "cancelled": False,
    }

    class Loads:
        async def find_one(self, query, projection=None, **kwargs):
            assert kwargs["session"] is session
            return dict(load)

        async def update_one(self, query, update, **kwargs):
            assert kwargs["session"] is session
            assert query["id"] == "load-1"
            assert update == {"$inc": {"invoice_guard_version": 1}}
            return SimpleNamespace(matched_count=1)

    class Invoices:
        async def find_one(self, query, **kwargs):
            assert kwargs["session"] is session
            return None

        async def insert_one(self, doc, **kwargs):
            assert kwargs["session"] is session
            self.inserted = doc

    class AuditEvents(FakeAuditEvents):
        async def insert_one(self, event, **kwargs):
            assert kwargs["session"] is session
            self.events.append(dict(event))

    class Settings:
        async def find_one(self, query, projection=None, **kwargs):
            assert kwargs["session"] is session
            return {"price_per_kg": 1.5, "mill_name": "Test mill"}

    fake_invoices = Invoices()
    fake_audit = AuditEvents()
    monkeypatch.setattr(invoices, "db", SimpleNamespace(
        loads=Loads(), invoices=fake_invoices, settings=Settings(),
        commercial_audit_events=fake_audit,
    ))

    result = await invoices._create_invoice_in_session(
        {"load_id": "load-1", "paid_amount": 0},
        {"username": "admin"},
        session,
    )

    assert result["number"] == "FAC-2627101"
    assert result["total"] == 30.0
    assert fake_invoices.inserted["load_id"] == "load-1"
    assert len(fake_audit.events) == 1
    assert fake_audit.events[0]["action"] == "INVOICE_CREATED"


@pytest.mark.asyncio
async def test_load_delete_checks_all_downstream_references_before_deleting(monkeypatch):
    session = object()
    calls = []

    class Invoices:
        async def find_one(self, query, projection=None, **kwargs):
            assert kwargs["session"] is session
            calls.append("invoice-check")
            return None

    class Loads:
        async def find_one(self, query, projection=None, **kwargs):
            assert kwargs["session"] is session
            calls.append("load-read")
            return {"id": query["id"], "code": "2627101", "client_name": "Client", "olive_kg": 100}

        async def delete_one(self, query, **kwargs):
            assert kwargs["session"] is session
            calls.append("load-delete")
            return SimpleNamespace(deleted_count=1)

    class Related:
        async def find_one(self, query, projection=None, **kwargs):
            assert kwargs["session"] is session
            calls.append("reference-check")
            return None

    async def run(operation):
        return await operation(session)

    monkeypatch.setattr(loads, "db", FakeDB(
        invoices=Invoices(), loads=Loads(), lab=Related(), sms_log=Related(),
        commercial_direct_load_purchases=Related(),
        commercial_customer_custody_receipts=Related(),
        commercial_lots=Related(),
        commercial_audit_events=FakeAuditEvents(calls),
    ))
    monkeypatch.setattr(loads, "run_transaction", run)

    result = await loads.delete_load("load-1", {})

    assert result == {"ok": True}
    assert calls == [
        "load-read", "invoice-check",
        "reference-check", "reference-check", "reference-check",
        "reference-check", "reference-check",
        "load-delete", "audit-event",
    ]


@pytest.mark.asyncio
async def test_load_delete_rejects_gs_reference_without_deleting(monkeypatch):
    session = object()
    calls = []

    class Invoices:
        async def find_one(self, query, projection=None, **kwargs):
            return None

    class Loads:
        async def find_one(self, query, projection=None, **kwargs):
            return {"id": query["id"], "olive_kg": 100}

        async def delete_one(self, query, **kwargs):
            calls.append("load-delete")
            return SimpleNamespace(deleted_count=1)

    class Related:
        async def find_one(self, query, projection=None, **kwargs):
            return {"id": "gs-ref"} if query.get("source_load_id") == "load-1" else None

    async def run(operation):
        return await operation(session)

    monkeypatch.setattr(loads, "db", FakeDB(
        invoices=Invoices(), loads=Loads(), lab=Related(), sms_log=Related(),
        commercial_direct_load_purchases=Related(),
        commercial_customer_custody_receipts=Related(),
        commercial_lots=Related(),
        commercial_audit_events=FakeAuditEvents(calls),
    ))
    monkeypatch.setattr(loads, "run_transaction", run)

    with pytest.raises(HTTPException) as exc:
        await loads.delete_load("load-1", {})

    assert exc.value.status_code == 409
    assert exc.value.detail == "load_has_gs_reference"
    assert calls == []


@pytest.mark.asyncio
async def test_client_delete_deactivates_and_preserves_all_load_records(monkeypatch):
    session = object()
    calls = []

    class Loads:
        def find(self, query, projection=None, **kwargs):
            assert kwargs["session"] is session
            return FakeCursor([{"id": "load-1", "client_name": "Client"}])

    class Clients:
        async def find_one(self, query, projection=None, **kwargs):
            assert kwargs["session"] is session
            return {"phone": "21600000000", "client_name": "Client", "active": True}

        async def update_one(self, query, update, **kwargs):
            assert kwargs["session"] is session
            calls.append("client-deactivate")
            return SimpleNamespace(matched_count=1)

        async def delete_one(self, query, **kwargs):
            calls.append("client-delete")
            return SimpleNamespace(deleted_count=1)

    class Related:
        async def find_one(self, query, projection=None, **kwargs):
            assert kwargs["session"] is session
            return None

    async def run(operation):
        return await operation(session)

    monkeypatch.setattr(extras, "db", FakeDB(
        loads=Loads(), clients=Clients(), invoices=Related(), sms_log=Related(),
        commercial_suppliers=FakeCollection(calls=calls),
        commercial_buyers=Related(), commercial_custody_owners=Related(),
        commercial_customer_custody_receipts=Related(),
        commercial_customer_custody_releases=Related(),
        commercial_audit_events=FakeAuditEvents(calls),
    ))
    monkeypatch.setattr(extras, "run_transaction", run)

    result = await extras.delete_client("21600000000", {"id": "admin", "username": "admin"})

    assert result.deleted == 0
    assert result.deactivated is True
    assert result.loads_retained == 1
    assert calls == ["client-deactivate", "audit-event"]


@pytest.mark.asyncio
async def test_client_without_history_can_be_deleted_in_one_transaction(monkeypatch):
    session = object()
    calls = []

    class Loads:
        def find(self, query, projection=None, **kwargs):
            assert kwargs["session"] is session
            return FakeCursor([])

    class Clients:
        async def find_one(self, query, projection=None, **kwargs):
            assert kwargs["session"] is session
            return {"phone": "21600000000", "client_name": "Client"}

        async def delete_one(self, query, **kwargs):
            assert kwargs["session"] is session
            calls.append("client-delete")
            return SimpleNamespace(deleted_count=1)

    class Related:
        async def find_one(self, query, projection=None, **kwargs):
            assert kwargs["session"] is session
            return None

    async def run(operation):
        return await operation(session)

    monkeypatch.setattr(extras, "db", FakeDB(
        loads=Loads(), clients=Clients(), sms_log=Related(),
        commercial_suppliers=FakeCollection(calls=calls),
        commercial_buyers=Related(), commercial_custody_owners=Related(),
        commercial_customer_custody_receipts=Related(),
        commercial_customer_custody_releases=Related(),
        commercial_audit_events=FakeAuditEvents(calls),
    ))
    monkeypatch.setattr(extras, "run_transaction", run)

    result = await extras.delete_client("21600000000", {"id": "admin", "username": "admin"})

    assert result.deleted == 1
    assert result.deactivated is False
    assert calls == ["client-delete"]
