import re
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from routers import loads
from models.schemas import LoadCreate
from lib.weighing import derive_net_weight_kg


def _body(**overrides):
    values = {
        "client_name": " Client A ",
        "phone": "216 00 000 000",
        "gross_weight_kg": "12500.000",
        "tare_weight_kg": "4200.000",
        "bags": 40,
        "variety": " Chetoui ",
        "notes": " Arrival ",
        "initial_status": "pending",
        "idempotency_key": "8f1a6c7d-2b3e-4a5f-9c8d-1e2f3a4b5c6d",
    }
    values.update(overrides)
    return LoadCreate(**values)


def test_load_intake_fingerprint_normalizes_phone_and_decimal_scale():
    first = _body()
    second = _body(
        phone="21600000000",
        gross_weight_kg="12500.0000",
        tare_weight_kg="4200.0000",
    )
    first_net = derive_net_weight_kg(first.gross_weight_kg, first.tare_weight_kg)
    second_net = derive_net_weight_kg(second.gross_weight_kg, second.tare_weight_kg)

    assert loads._load_intake_fingerprint(first, re.sub(r"\s+", "", first.phone), first_net) == (
        loads._load_intake_fingerprint(second, re.sub(r"\s+", "", second.phone), second_net)
    )


def test_load_intake_fingerprint_changes_when_weight_or_business_payload_changes():
    body = _body()
    net = derive_net_weight_kg(body.gross_weight_kg, body.tare_weight_kg)
    baseline = loads._load_intake_fingerprint(body, "21600000000", net)

    changed_weight = _body(gross_weight_kg="12600.000")
    changed_net = derive_net_weight_kg(changed_weight.gross_weight_kg, changed_weight.tare_weight_kg)
    changed_name = _body(client_name="Different client")

    assert loads._load_intake_fingerprint(changed_weight, "21600000000", changed_net) != baseline
    assert loads._load_intake_fingerprint(changed_name, "21600000000", net) != baseline


class FakeCollection:
    def __init__(self, document):
        self.document = document
        self.queries = []

    async def find_one(self, query, projection=None):
        self.queries.append(query)
        if self.document and all(self.document.get(key) == value for key, value in query.items()):
            return self.document
        return None


@pytest.mark.asyncio
async def test_same_key_and_same_payload_replays_original_load_without_creating_another():
    body = _body()
    phone = re.sub(r"\s+", "", body.phone)
    net = derive_net_weight_kg(body.gross_weight_kg, body.tare_weight_kg)
    fingerprint = loads._load_intake_fingerprint(body, phone, net)
    record = {
        "actor_user_id": "worker-1",
        "idempotency_key": body.idempotency_key,
        "request_fingerprint": fingerprint,
        "load_id": "existing-load",
    }
    idempotency = FakeCollection(record)
    existing_loads = FakeCollection({"id": "existing-load", "code": "2627A0001"})
    monkeypatch_db = SimpleNamespace(load_intake_idempotency=idempotency, loads=existing_loads, clients=FakeCollection(None))
    original_db = loads.db
    original_to_load = loads.to_load
    loads.db = monkeypatch_db
    loads.to_load = lambda doc, user, lab=None: {"id": doc["id"], "code": doc["code"]}
    try:
        result = await loads.create_load(body, {"id": "worker-1", "username": "worker", "role": "worker"})
    finally:
        loads.db = original_db
        loads.to_load = original_to_load

    assert result == {"id": "existing-load", "code": "2627A0001"}
    assert len(idempotency.queries) == 1


@pytest.mark.asyncio
async def test_same_key_with_changed_payload_returns_conflict():
    body = _body()
    phone = re.sub(r"\s+", "", body.phone)
    net = derive_net_weight_kg(body.gross_weight_kg, body.tare_weight_kg)
    record = {
        "actor_user_id": "worker-1",
        "idempotency_key": body.idempotency_key,
        "request_fingerprint": "different-fingerprint",
        "load_id": "existing-load",
    }
    original_db = loads.db
    loads.db = SimpleNamespace(load_intake_idempotency=FakeCollection(record))
    try:
        with pytest.raises(HTTPException) as exc:
            await loads._existing_idempotent_load(
                "worker-1", body.idempotency_key,
                loads._load_intake_fingerprint(body, phone, net),
                {"id": "worker-1", "username": "worker", "role": "worker"},
            )
    finally:
        loads.db = original_db

    assert exc.value.status_code == 409
    assert exc.value.detail == "idempotency_key_payload_conflict"
