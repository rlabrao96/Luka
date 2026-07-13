import uuid
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, field_serializer


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    email_provider: str
    whatsapp_verified: bool
    phone_whatsapp: str | None = None
    preferred_currency: str = "CLP"
    household_id: uuid.UUID | None = None
    # Contribution mode for the caller's active HouseholdMember row.
    # Null when the user has no active household membership.
    contribution_mode: str | None = None
    fixed_contribution_amount: Decimal | None = None
    fixed_contribution_currency: str | None = None
    feature_trips_enabled: bool = False
    # Initial-sync cutoff (YYYY-MM-DD) for newly-connected banks; null = no cutoff.
    transactions_since: date | None = None
    model_config = {"from_attributes": True}

    @field_serializer("fixed_contribution_amount")
    def _serialize_fixed_contribution_amount(self, value: Decimal | None) -> str | None:
        # Align with the DB column (Numeric(14, 2)): always serialize with 2 decimal places
        # so the frontend sees a stable string representation regardless of input scale.
        if value is None:
            return None
        return f"{value.quantize(Decimal('0.01')):.2f}"


class WhatsAppVerifyRequest(BaseModel):
    phone: str
    pin: str


ALLOWED_CURRENCIES = {
    "CLP",
    "USD",
    "COP",
    "BRL",
    "MXN",
    "ARS",
    "PEN",
    "UYU",
    "PYG",
    "BOB",
    "VES",
    "DOP",
    "GTQ",
    "HNL",
    "NIO",
    "CRC",
}


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    phone_whatsapp: str | None = None
    preferred_currency: str | None = None
    # Initial-sync cutoff for newly-connected banks. Only applied when provided
    # (matches the other fields' update-when-not-None convention). The picker
    # always sends a concrete month-start; there is no "clear" affordance.
    transactions_since: date | None = None


class StoreProviderTokensRequest(BaseModel):
    provider_token: str
    provider_refresh_token: str | None = None


class SendWhatsAppPinRequest(BaseModel):
    phone: str
