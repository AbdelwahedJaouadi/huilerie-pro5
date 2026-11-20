from datetime import date

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
