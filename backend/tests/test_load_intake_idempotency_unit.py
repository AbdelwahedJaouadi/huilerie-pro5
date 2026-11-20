"""Unit tests for idempotent traditional olive intake requests."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from routers import loads as load_routes
from models.schemas import LoadCreate


class FakeSession:
    pass


class FakeCollection:
    def __init__(self):
        self.docs = []

    async def find_one(self, query, projection=None, **kwargs):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return deepcopy(doc)
        return None

    async def insert_one(self, doc, **kwargs):
        self.docs.append(deepcopy(doc))
        return SimpleNamespace(inserted_id=len(self.docs))


@pytest.fixture
def intake_env(monkeypatch):
    loads = FakeCollection()
    clients = FakeCollection()
    audit = FakeCollection()
    session = FakeSession()
    sms_calls = []
    code_calls = []

    async def run_transaction(operation):
        return await operation(session)

    async def next_code(season, session=None):
        assert session is not None
        code_calls.append(season)
        return f"2627{len(code_calls):04d}"

    async def send_sms(doc, kind):
        sms_calls.append((doc["id"], kind))

    monkeypatch.setattr(
        load_routes,
        "db",
        SimpleNamespace(loads=loads, clients=clients, commercial_audit_events=audit),
    )
    monkeypatch.setattr(load_routes, "run_transaction", run_transaction)
    monkeypatch.setattr(load_routes, "next_load_code", next_code)
    monkeypatch.setattr(load_routes, "active_season", lambda: _season())
    monkeypatch.setattr(load_routes, "_price", lambda: _price())
    monkeypatch.setattr(load_routes, "money_db", lambda value: value)
    monkeypatch.setattr(load_routes, "send_load_sms", send_sms)
    monkeypatch.setattr(load_routes, "to_load", lambda doc, _user: deepcopy(doc))

    env = SimpleNamespace(
        loads=loads, clients=clients, audit=audit, session=session,
        sms_calls=sms_calls, code_calls=code_calls,
    )
    return env


async def _season():
    return "2026-2027"


async def _price():
    return 1.25


def _command(**overrides):
    payload = {
        "client_name": "Client Test",
        "phone": "+216 00 000 000",
        "olive_kg": 8300.125,
        "bags": 120,
        "variety": "Chemlali",
        "notes": "First intake",
        "initial_status": "pending",
        "idempotency_key": "intake-request-000001",
    }
    payload.update(overrides)
    return LoadCreate(**payload)


USER = {"id": "worker-1", "username": "worker", "full_name": "Worker"}


@pytest.mark.asyncio
async def test_first_request_creates_one_load_client_audit_and_sms(intake_env):
    result = await load_routes.create_load(_command(), USER)

    assert result["code"] == "26270001"
    assert len(intake_env.loads.docs) == 1
    assert len(intake_env.clients.docs) == 1
    assert len(intake_env.audit.docs) == 1
    assert intake_env.audit.docs[0]["action"] == "LOAD_CREATED"
    assert intake_env.sms_calls == [(result["id"], "arrival")]
    assert len(intake_env.code_calls) == 1


@pytest.mark.asyncio
async def test_same_key_and_same_payload_returns_original_load_without_side_effects(intake_env):
    first = await load_routes.create_load(_command(), USER)
    replay = await load_routes.create_load(_command(), USER)

    assert replay["id"] == first["id"]
    assert replay["code"] == first["code"]
    assert len(intake_env.loads.docs) == 1
    assert len(intake_env.clients.docs) == 1
    assert len(intake_env.audit.docs) == 1
    assert len(intake_env.sms_calls) == 1
    assert len(intake_env.code_calls) == 1


@pytest.mark.asyncio
async def test_same_key_with_changed_business_payload_returns_409_without_writes(intake_env):
    await load_routes.create_load(_command(), USER)

    with pytest.raises(HTTPException) as exc:
        await load_routes.create_load(_command(olive_kg=8301.125), USER)

    assert exc.value.status_code == 409
    assert exc.value.detail == "idempotency_key_payload_conflict"
    assert len(intake_env.loads.docs) == 1
    assert len(intake_env.clients.docs) == 1
    assert len(intake_env.audit.docs) == 1
    assert len(intake_env.sms_calls) == 1
    assert len(intake_env.code_calls) == 1


@pytest.mark.asyncio
async def test_different_keys_create_distinct_loads(intake_env):
    first = await load_routes.create_load(_command(), USER)
    second = await load_routes.create_load(
        _command(idempotency_key="intake-request-000002", olive_kg=7000.0),
        USER,
    )

    assert first["id"] != second["id"]
    assert first["code"] != second["code"]
    assert len(intake_env.loads.docs) == 2
    assert len(intake_env.audit.docs) == 2
    assert len(intake_env.sms_calls) == 2
    assert len(intake_env.code_calls) == 2


@pytest.mark.asyncio
async def test_legacy_request_without_idempotency_key_remains_supported(intake_env):
    result = await load_routes.create_load(
        _command(idempotency_key=None),
        USER,
    )

    assert result["id"]
    assert len(intake_env.loads.docs) == 1
    assert "idempotency_key" not in intake_env.loads.docs[0]
