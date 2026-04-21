"""Pydantic schemas for the cuotas REST surface (Chunk E).

Kept isolated from `v2_schemas.py` so the CRUD router doesn't couple to the
aggregate response Chunk C owns.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from modules.auth.schemas import ALLOWED_CURRENCIES


class CuotaCreateRequest(BaseModel):
    """Payload for POST /cuotas — marks a purchase as an installment plan.

    The server computes `monthly_amount` and `last_cuota_date`; the caller
    only supplies totals and the start month.
    """

    merchant_name: str = Field(min_length=1, max_length=255)
    total_amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    installments_total: int = Field(gt=0)

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, v: str) -> str:
        code = v.upper()
        if code not in ALLOWED_CURRENCIES:
            raise ValueError(f"unsupported currency: {v}")
        return code

    first_cuota_date: date
    split_type: str = Field(default="personal", pattern="^(personal|shared)$")
    origin_transaction_id: UUID | None = None


class CuotaResponse(BaseModel):
    """One cuota row as exposed via the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    merchant_name: str
    total_amount: Decimal
    currency: str
    installments_total: int
    installments_paid: int
    monthly_amount: Decimal
    first_cuota_date: date
    last_cuota_date: date
    status: str
    split_type: str
    origin_transaction_id: UUID | None = None
    created_at: datetime


class CuotaListResponse(BaseModel):
    cuotas: list[CuotaResponse]
