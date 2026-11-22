from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from commercial.schemas.oil_purchases import OilPurchasePaymentDraft, SupplierOilPurchaseDraft


def base(**overrides):
    values = {
        "payment_date": date(2026, 11, 8),
        "amount_tnd": Decimal("25.000"),
        "method": "CASH",
        "expected_purchase_version": 1,
        "idempotency_key": "oil-purchase-payment-key-001",
    }
    values.update(overrides)
    return values


def test_cash_payment_does_not_require_reference():
    draft = OilPurchasePaymentDraft(**base())
    assert draft.amount_tnd == Decimal("25.000")
    assert draft.reference is None


@pytest.mark.parametrize("method", ["BANK_TRANSFER", "CHEQUE"])
def test_non_cash_payment_requires_reference(method):
    with pytest.raises(ValidationError, match="reference is required"):
        OilPurchasePaymentDraft(**base(method=method))
    draft = OilPurchasePaymentDraft(**base(method=method, reference="PAYMENT-REF-001"))
    assert draft.reference == "PAYMENT-REF-001"


def test_payment_amount_must_be_positive():
    with pytest.raises(ValidationError):
        OilPurchasePaymentDraft(**base(amount_tnd=Decimal("0.000")))



def supplier_oil_base(**overrides):
    values = {
        "supplier_id": "supplier-001",
        "purchase_date": date(2026, 11, 8),
        "oil_type": "Extra virgin",
        "quantity_l": Decimal("125.500"),
        "unit_price_tnd_per_l": Decimal("18.250"),
        "idempotency_key": "supplier-ready-oil-purchase-001",
    }
    values.update(overrides)
    return values


def test_supplier_oil_purchase_accepts_litre_quantity_and_computes_input_shape():
    draft = SupplierOilPurchaseDraft(**supplier_oil_base())
    assert draft.quantity_l == Decimal("125.500")
    assert draft.unit_price_tnd_per_l == Decimal("18.250")
    assert draft.supplier_id == "supplier-001"


@pytest.mark.parametrize("quantity", [Decimal("0"), Decimal("-1")])
def test_supplier_oil_purchase_requires_positive_litre_quantity(quantity):
    with pytest.raises(ValidationError):
        SupplierOilPurchaseDraft(**supplier_oil_base(quantity_l=quantity))


def test_supplier_oil_purchase_rejects_blank_oil_type():
    with pytest.raises(ValidationError, match="Oil type is required"):
        SupplierOilPurchaseDraft(**supplier_oil_base(oil_type="   "))
