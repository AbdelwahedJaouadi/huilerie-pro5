import pytest
from fastapi import HTTPException
from types import SimpleNamespace

from routers import loads


class FakeInvoices:
    def __init__(self, invoice=None):
        self.invoice = invoice

    async def find_one(self, query, projection=None):
        return self.invoice


@pytest.mark.asyncio
async def test_load_delete_guard_rejects_load_with_invoice(monkeypatch):
    fake = SimpleNamespace(invoices=FakeInvoices({"number": "FAC-2627100"}))
    monkeypatch.setattr(loads, "db", fake)

    with pytest.raises(HTTPException) as exc:
        await loads._ensure_load_has_no_invoice("load-1")

    assert exc.value.status_code == 409
    assert exc.value.detail == "load_has_invoice"


@pytest.mark.asyncio
async def test_load_delete_guard_allows_load_without_invoice(monkeypatch):
    fake = SimpleNamespace(invoices=FakeInvoices())
    monkeypatch.setattr(loads, "db", fake)

    await loads._ensure_load_has_no_invoice("load-1")


@pytest.mark.asyncio
async def test_create_load_rejects_deactivated_client_before_creating_load(monkeypatch):
    from models.schemas import LoadCreate

    class Clients:
        async def find_one(self, query, projection=None):
            assert query == {"phone": "21600000000", "active": False}
            return {"phone": "21600000000"}

    monkeypatch.setattr(loads, "db", SimpleNamespace(clients=Clients()))

    with pytest.raises(HTTPException) as exc:
        await loads.create_load(
            LoadCreate(client_name="Client", phone="216 0000 0000", olive_kg=100),
            {"id": "worker-1", "username": "worker", "role": "worker"},
        )

    assert exc.value.status_code == 409
    assert exc.value.detail == "client_inactive"
