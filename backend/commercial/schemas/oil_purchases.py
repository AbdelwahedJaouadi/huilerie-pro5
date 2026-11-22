"""Customer-owned oil purchases and payable settlement command schemas."""
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OilPurchasePaymentDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    payment_date: date
    amount_tnd: Decimal = Field(gt=Decimal("0"), max_digits=18, decimal_places=3)
    method: Literal["CASH", "BANK_TRANSFER", "CHEQUE"]
    reference: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=500)
    expected_purchase_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=16, max_length=128)

    @model_validator(mode="after")
    def validate_payment_reference(self):
        if self.method in {"BANK_TRANSFER", "CHEQUE"} and not (self.reference or "").strip():
            raise ValueError("A reference is required for bank transfers and cheques")
        return self


class SupplierPaymentDraft(BaseModel):
    """Immutable settlement against an approved olive purchase from a supplier."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    payment_date: date
    amount_tnd: Decimal = Field(gt=Decimal("0"), max_digits=18, decimal_places=3)
    method: Literal["CASH", "BANK_TRANSFER", "CHEQUE"]
    treasury_account_id: str | None = Field(default=None, min_length=1, max_length=80)
    reference: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=500)
    expected_purchase_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=16, max_length=128)

    @model_validator(mode="after")
    def validate_payment_reference(self):
        if self.method in {"BANK_TRANSFER", "CHEQUE"} and not (self.reference or "").strip():
            raise ValueError("A reference is required for bank transfers and cheques")
        return self


class SupplierOilPurchaseDraft(BaseModel):
    """Direct purchase of ready oil from a supplier; no inventory movement is posted."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    supplier_id: str = Field(min_length=1, max_length=100)
    purchase_date: date
    oil_type: str = Field(min_length=2, max_length=80)
    quantity_l: Decimal = Field(gt=Decimal("0"), max_digits=18, decimal_places=3)
    unit_price_tnd_per_l: Decimal = Field(ge=Decimal("0"), max_digits=18, decimal_places=3)
    notes: str | None = Field(default=None, max_length=1000)
    idempotency_key: str = Field(min_length=16, max_length=128)

    @model_validator(mode="after")
    def validate_oil_type(self):
        if not self.oil_type.strip():
            raise ValueError("Oil type is required")
        return self
