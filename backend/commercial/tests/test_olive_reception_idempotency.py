from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from commercial import routers
from commercial.routers import (
    OliveReceptionPurchaseCommand,
    _olive_reception_command_fingerprint,
)


def _command(**overrides):
    values = {
        "new_supplier_name": "Supplier A",
        "new_supplier_phone": "+216 20 000 000",
        "new_supplier_tax_identifier": "tn 12345",
        "purchase_date": date(2026, 11, 18),
        "lines": [{
            "variety_id": "variety-1",
            "quantity_kg": "8200.000",
            "unit_price_millimes": "2000",
        }],
        "receiving_location_id": "receiving-1",
        "notes": " First delivery ",
        "idempotency_key": "olive-reception-idempotency-key-001",
        "gross_weight_kg": "12500.000",
        "tare_weight_kg": "4300.000",
    }
    values.update(overrides)
    return OliveReceptionPurchaseCommand(**values)


def test_reception_fingerprint_normalizes_phone_tax_name_and_decimal_format():
    first = _command()
    second = _command(
        new_supplier_name=" supplier a ",
        new_supplier_phone="+21620000000",
        new_supplier_tax_identifier="TN 12345",
        gross_weight_kg="12500.0000",
        tare_weight_kg="4300.0000",
        lines=[{
            "variety_id": "variety-1",
            "quantity_kg": "8200.0000",
            "unit_price_millimes": "2000",
        }],
        notes="First delivery",
    )

    assert _olive_reception_command_fingerprint(first) == _olive_reception_command_fingerprint(second)


def test_reception_fingerprint_covers_new_supplier_contact_and_tax_metadata():
    baseline = _olive_reception_command_fingerprint(_command())

    changed_phone = _olive_reception_command_fingerprint(
        _command(new_supplier_phone="+216 21 000 000")
    )
    changed_tax = _olive_reception_command_fingerprint(
        _command(new_supplier_tax_identifier="TN 99999")
    )
    changed_location = _olive_reception_command_fingerprint(
        _command(receiving_location_id="receiving-2")
    )

    assert changed_phone != baseline
    assert changed_tax != baseline
    assert changed_location != baseline


class FakeIdempotencyCollection:
    def __init__(self, record):
        self.record = record

    async def find_one(self, query, projection=None):
        if self.record and all(self.record.get(key) == value for key, value in query.items()):
            return self.record
        return None


@pytest.mark.asyncio
async def test_reception_replays_same_key_and_payload_before_season_validation(monkeypatch):
    command = _command()
    fingerprint = _olive_reception_command_fingerprint(command)
    record = {
        "actor_user_id": "worker-1",
        "idempotency_key": command.idempotency_key,
        "request_fingerprint": fingerprint,
        "purchase_id": "purchase-existing",
        "supplier_id": "supplier-existing",
    }
    monkeypatch.setattr(
        routers,
        "db",
        SimpleNamespace(commercial_olive_reception_idempotency=FakeIdempotencyCollection(record)),
    )
    monkeypatch.setattr(routers, "_authorize", lambda user, permission: None)

    async def replay(existing_record):
        return {"purchase": {"id": existing_record["purchase_id"]}, "supplier": {"id": existing_record["supplier_id"]}}

    monkeypatch.setattr(routers, "_load_olive_reception_result", replay)

    result = await routers.create_olive_reception_purchase(
        command,
        {"id": "worker-1", "role": "worker", "active": True},
    )

    assert result == {"purchase": {"id": "purchase-existing"}, "supplier": {"id": "supplier-existing"}}


@pytest.mark.asyncio
async def test_reception_same_key_with_changed_supplier_phone_returns_conflict(monkeypatch):
    original = _command()
    record = {
        "actor_user_id": "worker-1",
        "idempotency_key": original.idempotency_key,
        "request_fingerprint": _olive_reception_command_fingerprint(original),
        "purchase_id": "purchase-existing",
        "supplier_id": "supplier-existing",
    }
    monkeypatch.setattr(
        routers,
        "db",
        SimpleNamespace(commercial_olive_reception_idempotency=FakeIdempotencyCollection(record)),
    )
    monkeypatch.setattr(routers, "_authorize", lambda user, permission: None)

    with pytest.raises(HTTPException) as exc:
        await routers.create_olive_reception_purchase(
            _command(new_supplier_phone="+216 21 000 000"),
            {"id": "worker-1", "role": "worker", "active": True},
        )

    assert exc.value.status_code == 409
    assert exc.value.detail == "olive_reception_idempotency_payload_conflict"
