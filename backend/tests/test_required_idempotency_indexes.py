import pytest

import lib.db as db_module


class FailingCollection:
    async def create_indexes(self, models):
        raise RuntimeError("index creation denied")


class FakeDatabase:
    def __init__(self, failing_collection):
        self.failing_collection = failing_collection

    def __getitem__(self, name):
        assert name == self.failing_collection
        return FailingCollection()


@pytest.mark.parametrize("collection", sorted(db_module.REQUIRED_IDEMPOTENCY_INDEX_COLLECTIONS))
@pytest.mark.asyncio
async def test_required_idempotency_index_failure_fails_closed(monkeypatch, collection):
    monkeypatch.setattr(db_module, "db", FakeDatabase(collection))
    monkeypatch.setattr(
        db_module,
        "INDEXES",
        {collection: db_module.INDEXES[collection]},
    )

    with pytest.raises(RuntimeError, match="Required idempotency index unavailable"):
        await db_module.ensure_indexes()
