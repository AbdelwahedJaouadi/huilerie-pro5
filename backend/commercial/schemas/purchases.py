"""Commercial olive purchase command schemas.

Totals are intentionally not accepted from the client; the service computes
them from validated line quantities and unit prices using Decimal arithmetic.
"""
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from lib.weighing import derive_net_weight_kg, validate_weight_kg


class OlivePurchaseLine(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    variety_id: str = Field(min_length=1, max_length=100)
    quantity_kg: Decimal = Field(gt=Decimal("0"), max_digits=18, decimal_places=3)
    unit_price_dt: Decimal = Field(ge=Decimal("0"), max_digits=18, decimal_places=3)


class OliveReceptionPurchaseLine(BaseModel):
    """Reception API line; the operator enters the unit price in millimes."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    variety_id: str = Field(min_length=1, max_length=100)
    quantity_kg: Decimal = Field(gt=Decimal("0"), max_digits=18, decimal_places=3)
    unit_price_millimes: Decimal = Field(
        ge=Decimal("0"), max_digits=18, decimal_places=0
    )


class OlivePurchaseDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    supplier_id: str = Field(min_length=1, max_length=100)
    purchase_date: date
    lines: tuple[OlivePurchaseLine, ...] = Field(min_length=1, max_length=100)
    notes: str | None = Field(default=None, max_length=1000)
    idempotency_key: str = Field(min_length=16, max_length=128)
    gross_weight_kg: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    tare_weight_kg: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)

    @field_validator("gross_weight_kg", "tare_weight_kg", mode="before")
    @classmethod
    def validate_raw_vehicle_reading(cls, value, info):
        if value is None:
            return None
        return validate_weight_kg(value, info.field_name)

    @model_validator(mode="after")
    def validate_lines(self):
        if sum((line.quantity_kg for line in self.lines), Decimal("0")) <= 0:
            raise ValueError("Purchase quantity must be positive")
        if (self.gross_weight_kg is None) != (self.tare_weight_kg is None):
            raise ValueError("gross_and_tare_must_be_provided_together")
        if self.gross_weight_kg is not None:
            if len(self.lines) != 1:
                raise ValueError("vehicle_weight_requires_single_purchase_line")
            net = derive_net_weight_kg(self.gross_weight_kg, self.tare_weight_kg)
            if self.lines[0].quantity_kg != net:
                raise ValueError("purchase_quantity_must_match_vehicle_net_weight")
        return self


class OlivePurchaseUpdate(BaseModel):
    """Versioned replacement of an unapproved purchase draft."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_version: int = Field(ge=1)
    supplier_id: str = Field(min_length=1, max_length=100)
    purchase_date: date
    lines: tuple[OlivePurchaseLine, ...] = Field(min_length=1, max_length=100)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_lines(self):
        if sum((line.quantity_kg for line in self.lines), Decimal("0")) <= 0:
            raise ValueError("Purchase quantity must be positive")
        return self


class ApproveOlivePurchaseCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_version: int = Field(ge=1)
    receiving_location_id: str = Field(min_length=1, max_length=100)
    idempotency_key: str = Field(min_length=16, max_length=128)


class CancelOlivePurchaseDraftCommand(BaseModel):
    """Audited cancellation of an unapproved olive purchase draft."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=5, max_length=500)
