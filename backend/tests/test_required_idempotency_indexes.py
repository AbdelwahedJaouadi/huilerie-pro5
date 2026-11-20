from types import SimpleNamespace

import pytest

import lib.db as db_module


class FailingCollection:
    async def create_indexes(self, models):
        raise RuntimeError("index creation denied")


class FakeDatabase:
    def __getitem__(self, name):
        assert name == "load_intake_idempotency"
        return FailingCollection()


@pytest.mark.asyncio
async def test_required_idempotency_index_failure_fails_closed(monkeypatch):
    monkeypatch.setattr(db_module, "db", FakeDatabase())
    monkeypatch.setattr(
        db_module,
        "INDEXES",
        {"load_intake_idempotency": db_module.INDEXES["load_intake_idempotency"]},
    )

    with pytest.raises(RuntimeError, match="Required idempotency index unavailable"):
        await db_module.ensure_indexes()
