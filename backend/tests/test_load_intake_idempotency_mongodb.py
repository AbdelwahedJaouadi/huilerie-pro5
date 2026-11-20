"""Real MongoDB transaction tests for concurrent traditional intake retries."""
import asyncio
import os
import uuid

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from lib.db import INDEXES
from models.schemas import LoadCreate
from routers import loads as load_routes


@pytest.mark.asyncio
async def test_concurrent_same_key_intake_commits_one_load_and_one_side_effect_set(monkeypatch):
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db_name = "load_idempotency_" + uuid.uuid4().hex
    test_db = client[db_name]
    sms_calls = []
    season = "2026-2027"

    try:
        await test_db.loads.create_indexes(INDEXES["loads"])
        await test_db.clients.create_indexes(INDEXES["clients"])

        async def run_transaction(operation):
            async with await client.start_session() as session:
                return await session.with_transaction(operation)

        async def next_code(_season, session=None):
            counter = await test_db.counters.find_one_and_update(
                {"_id": f"load_seq:{_season}"},
                {"$inc": {"seq": 1}},
                upsert=True,
                return_document=ReturnDocument.AFTER,
                session=session,
            )
            return f"2627{counter['seq']:04d}"

        async def send_sms(doc, kind):
            sms_calls.append((doc["id"], kind))

        monkeypatch.setattr(load_routes, "db", test_db)
        monkeypatch.setattr(load_routes, "run_transaction", run_transaction)
        monkeypatch.setattr(load_routes, "next_load_code", next_code)
        monkeypatch.setattr(load_routes, "active_season", lambda: _active_season(season))
        monkeypatch.setattr(load_routes, "_price", _price)
        monkeypatch.setattr(load_routes, "money_db", lambda value: value)
        monkeypatch.setattr(load_routes, "send_load_sms", send_sms)
        monkeypatch.setattr(load_routes, "to_load", lambda doc, _user: dict(doc))

        command = LoadCreate(
            client_name="Concurrent Intake",
            phone="+21600000001",
            olive_kg=8300.125,
            bags=120,
            variety="Chemlali",
            notes="same physical delivery",
            initial_status="pending",
            idempotency_key="concurrent-intake-request-0001",
        )
        user = {"id": "concurrent-worker", "username": "worker"}

        results = await asyncio.gather(
            load_routes.create_load(command, user),
            load_routes.create_load(command, user),
            return_exceptions=True,
        )

        errors = [result for result in results if isinstance(result, Exception)]
        assert not errors, errors
        assert results[0]["id"] == results[1]["id"]
        assert results[0]["code"] == results[1]["code"]
        assert await test_db.loads.count_documents({}) == 1
        assert await test_db.clients.count_documents({}) == 1
        assert await test_db.commercial_audit_events.count_documents({"action": "LOAD_CREATED"}) == 1
        assert len(sms_calls) == 1
        counter = await test_db.counters.find_one({"_id": f"load_seq:{season}"})
        assert counter["seq"] == 1
    finally:
        await client.drop_database(db_name)
        client.close()


async def _active_season(value):
    return value


async def _price():
    return 1.25
