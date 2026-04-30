"""Pydantic schemas for the Trips (Viajes) module.

Request/response models for trip endpoints. See spec
``docs/superpowers/specs/2026-04-30-viajes-trips-design.md`` §4.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


# --- Inputs: attendees ---


class CreateAttendeeInput(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    display_name: Optional[str] = None

    @model_validator(mode="after")
    def _at_least_one_identifier(self) -> "CreateAttendeeInput":
        if not (self.email or self.phone or self.display_name):
            raise ValueError("attendee requires at least one of: email, phone, display_name")
        return self


# --- Inputs: trips ---


class CreateTripRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    start_date: date
    end_date: date
    base_currency: str = Field(min_length=3, max_length=3)
    attendees: list[CreateAttendeeInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_dates(self) -> "CreateTripRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class UpdateTripRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    base_currency: Optional[str] = Field(default=None, min_length=3, max_length=3)

    @model_validator(mode="after")
    def _validate_dates(self) -> "UpdateTripRequest":
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("end_date must be on or after start_date")
        return self


# --- Inputs: expenses ---


class SplitInput(BaseModel):
    attendee_id: UUID
    share_type: Literal["equal", "custom_amount", "custom_percent"] = "equal"
    share_amount: Optional[Decimal] = None
    share_percent: Optional[Decimal] = None

    @model_validator(mode="after")
    def _validate_share(self) -> "SplitInput":
        if self.share_type == "custom_amount" and self.share_amount is None:
            raise ValueError("share_amount required when share_type=custom_amount")
        if self.share_type == "custom_percent" and self.share_percent is None:
            raise ValueError("share_percent required when share_type=custom_percent")
        return self


class CreateExpenseRequest(BaseModel):
    payer_attendee_id: UUID
    description: str = Field(min_length=1, max_length=500)
    amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    expense_date: date
    transaction_id: Optional[UUID] = None
    splits: list[SplitInput] = Field(min_length=1)


class UpdateExpenseRequest(BaseModel):
    payer_attendee_id: Optional[UUID] = None
    description: Optional[str] = Field(default=None, min_length=1, max_length=500)
    amount: Optional[Decimal] = Field(default=None, gt=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    expense_date: Optional[date] = None
    transaction_id: Optional[UUID] = None
    splits: Optional[list[SplitInput]] = None


# --- Inputs: settlements & joining ---


class CreateSettlementRequest(BaseModel):
    from_attendee_id: UUID
    to_attendee_id: UUID
    amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    transaction_id: Optional[UUID] = None

    @model_validator(mode="after")
    def _validate_parties(self) -> "CreateSettlementRequest":
        if self.from_attendee_id == self.to_attendee_id:
            raise ValueError("from_attendee_id and to_attendee_id must differ")
        return self


class JoinTripRequest(BaseModel):
    """Body for joining a trip via invite token. Token comes from URL path."""

    display_name: Optional[str] = None


# --- Outputs: attendees & splits ---


class AttendeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: Optional[UUID] = None
    display_name: Optional[str] = None
    left_at: Optional[datetime] = None
    created_at: datetime


class SplitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    attendee_id: UUID
    share_amount: Decimal
    share_type: Literal["equal", "custom_amount", "custom_percent"]


# --- Outputs: expenses & settlements ---


class ExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    trip_id: UUID
    payer_attendee_id: UUID
    description: str
    amount: Decimal
    currency: str
    expense_date: date
    transaction_id: Optional[UUID] = None
    fx_rate_to_base: Optional[Decimal] = None
    version: int
    created_at: datetime
    updated_at: datetime
    splits: list[SplitResponse] = Field(default_factory=list)


class SettlementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    trip_id: UUID
    from_attendee_id: UUID
    to_attendee_id: UUID
    amount: Decimal
    currency: str
    fx_rate_to_base: Optional[Decimal] = None
    settled_at: datetime
    transaction_id: Optional[UUID] = None
    write_off: bool = False
    created_at: datetime


# --- Outputs: balances & suggestions ---


class BalanceEntry(BaseModel):
    attendee_id: UUID
    attendee_display_name: Optional[str] = None
    net_in_base: Decimal


class SettleSuggestion(BaseModel):
    from_attendee_id: UUID
    to_attendee_id: UUID
    amount: Decimal
    currency: str


# --- Outputs: trips ---


class TripResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    start_date: date
    end_date: date
    base_currency: str
    status: Literal["upcoming", "active", "past"]
    created_at: datetime
    your_net_balance: Decimal


class TripDetailResponse(TripResponse):
    attendees: list[AttendeeResponse] = Field(default_factory=list)
    expenses: list[ExpenseResponse] = Field(default_factory=list)
    settlements: list[SettlementResponse] = Field(default_factory=list)
    balances: list[BalanceEntry] = Field(default_factory=list)
    settle_suggestions: list[SettleSuggestion] = Field(default_factory=list)


class TripListResponse(BaseModel):
    active: list[TripResponse] = Field(default_factory=list)
    upcoming: list[TripResponse] = Field(default_factory=list)
    past: list[TripResponse] = Field(default_factory=list)


# --- Outputs: invites & helpers ---


class InviteLinkResponse(BaseModel):
    token: str
    url: str
    expires_at: datetime


class TripPreviewResponse(BaseModel):
    name: str
    start_date: date
    end_date: date
    attendee_count: int
    base_currency: str


class SuggestedTransaction(BaseModel):
    transaction_id: UUID
    merchant: Optional[str] = None
    amount: Decimal
    currency: str
    transaction_date: date
    category: Optional[str] = None
