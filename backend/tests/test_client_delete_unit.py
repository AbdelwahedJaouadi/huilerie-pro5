from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from routers import extras


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    async def to_list(self, _length):
        return list(self.docs)


class FakeCollection:
    def __init__(self, docs=None, calls=None):
        self.docs = list(docs or [])
        self.calls = calls if calls is not None else []
        self.last_query = None

    async def find_one(self, query, projection=None, **kwargs):
        self.last_query = query
        return next((doc for doc in self.docs if all(doc.get(k) == v for k, v in query.items())), None)

    async def update_one(self, query, update, **kwargs):
        self.calls.append(("update", query, update))
        return SimpleNamespace(matched_count=1, upserted_id=None)

    async def delete_one(self, query, **kwargs):
        self.calls.append(("delete", query))
        matched = next((doc for doc in self.docs if all(doc.get(k) == v for k, v in query.items())), None)
        if matched:
            self.docs.remove(matched)
        return SimpleNamespace(deleted_count=1 if matched else 0)

    async def insert_one(self, doc, **kwargs):
        self.calls.append(("insert", dict(doc)))
        return SimpleNamespace(inserted_id=doc.get("id"))


class FakeLoads(FakeCollection):
    def find(self, query, projection=None, **kwargs):
        return FakeCursor([doc for doc in self.docs if doc.get("phone") == query.get("phone")])


class FakeDB(SimpleNamespace):
    def __getitem__(self, name):
        return getattr(self, name)


@pytest.mark.asyncio
async def test_client_with_load_history_is_deactivated_and_all_records_are_retained(monkeypatch):
    calls = []
    fake = FakeDB(
        loads=FakeLoads([{"id": "load-1", "phone": "21600000000", "client_name": "Client"}], calls),
        clients=FakeCollection([{"phone": "21600000000", "client_name": "Client", "active": True}], calls),
        sms_log=FakeCollection(calls=calls),
        commercial_buyers=FakeCollection(calls=calls),
        commercial_custody_owners=FakeCollection(calls=calls),
        commercial_customer_custody_receipts=FakeCollection(calls=calls),
        commercial_audit_events=FakeCollection(calls=calls),
    )
    monkeypatch.setattr(extras, "db", fake)

    async def run(operation):
        return await operation(object())

    monkeypatch.setattr(extras, "run_transaction", run)
    result = await extras.delete_client("21600000000", {"id": "admin", "username": "admin"})

    assert result.deleted == 0
    assert result.deactivated is True
    assert result.loads_retained == 1
    assert any(call[0] == "update" for call in calls)
    assert any(call[0] == "insert" and call[1]["action"] == "CLIENT_DEACTIVATED" for call in calls)
    assert not any(call[0] == "delete" for call in calls)


@pytest.mark.asyncio
async def test_client_without_history_is_hard_deleted(monkeypatch):
    calls = []
    fake = FakeDB(
        loads=FakeLoads([], calls),
        clients=FakeCollection([{"phone": "21600000000", "client_name": "Client", "active": True}], calls),
        sms_log=FakeCollection(calls=calls),
        commercial_buyers=FakeCollection(calls=calls),
        commercial_custody_owners=FakeCollection(calls=calls),
        commercial_customer_custody_receipts=FakeCollection(calls=calls),
        commercial_audit_events=FakeCollection(calls=calls),
    )
    monkeypatch.setattr(extras, "db", fake)

    async def run(operation):
        return await operation(object())

    monkeypatch.setattr(extras, "run_transaction", run)
    result = await extras.delete_client("21600000000", {"id": "admin", "username": "admin"})

    assert result.deleted == 1
    assert result.deactivated is False
    assert result.loads_retained == 0
    assert ("delete", {"phone": "21600000000"}) in calls


@pytest.mark.asyncio
async def test_client_referenced_in_gs_without_traditional_load_is_deactivated(monkeypatch):
    calls = []
    fake = FakeDB(
        loads=FakeLoads([], calls),
        clients=FakeCollection([{"phone": "21600000000", "client_name": "Client", "active": True}], calls),
        sms_log=FakeCollection(calls=calls),
        commercial_buyers=FakeCollection([{"phone": "21600000000", "id": "buyer-1"}], calls),
        commercial_custody_owners=FakeCollection(calls=calls),
        commercial_customer_custody_receipts=FakeCollection(calls=calls),
        commercial_audit_events=FakeCollection(calls=calls),
    )
    monkeypatch.setattr(extras, "db", fake)

    async def run(operation):
        return await operation(object())

    monkeypatch.setattr(extras, "run_transaction", run)
    result = await extras.delete_client("21600000000", {"id": "admin", "username": "admin"})

    assert result.deactivated is True
    assert result.deleted == 0
    assert not any(call[0] == "delete" for call in calls)


@pytest.mark.asyncio
async def test_delete_unknown_client_returns_404(monkeypatch):
    calls = []
    fake = FakeDB(
        loads=FakeLoads([], calls),
        clients=FakeCollection([], calls),
        sms_log=FakeCollection(calls=calls),
        commercial_buyers=FakeCollection(calls=calls),
        commercial_custody_owners=FakeCollection(calls=calls),
        commercial_customer_custody_receipts=FakeCollection(calls=calls),
        commercial_audit_events=FakeCollection(calls=calls),
    )
    monkeypatch.setattr(extras, "db", fake)

    async def run(operation):
        return await operation(object())

    monkeypatch.setattr(extras, "run_transaction", run)
    with pytest.raises(HTTPException) as exc:
        await extras.delete_client("21600000000", {"id": "admin", "username": "admin"})
    assert exc.value.status_code == 404
    assert exc.value.detail == "client_not_found"


@pytest.mark.asyncio
async def test_customer_custody_receipt_phone_reference_prevents_hard_delete(monkeypatch):
    calls = []
    fake = FakeDB(
        loads=FakeLoads([], calls),
        clients=FakeCollection([{"phone": "21600000000", "client_name": "Client", "active": True}], calls),
        sms_log=FakeCollection(calls=calls),
        commercial_buyers=FakeCollection(calls=calls),
        commercial_custody_owners=FakeCollection(calls=calls),
        commercial_customer_custody_receipts=FakeCollection(
            [{"customer_phone": "21600000000", "id": "receipt-1"}], calls
        ),
        commercial_audit_events=FakeCollection(calls=calls),
    )
    monkeypatch.setattr(extras, "db", fake)

    async def run(operation):
        return await operation(object())

    monkeypatch.setattr(extras, "run_transaction", run)
    result = await extras.delete_client("21600000000", {"id": "admin", "username": "admin"})

    assert result.deactivated is True
    assert result.deleted == 0
    assert not any(call[0] == "delete" for call in calls)
