from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel


class RecentCharge(BaseModel):
    date: date
    amount: Decimal


class RecurringExpenseItem(BaseModel):
    merchant_name: str
    category: str | None
    average_amount: Decimal
    last_amount: Decimal
    previous_amount: Decimal | None
    last_charge_date: date
    next_charge_day: int
    frequency: str
    trend: str
    trend_pct: float | None
    months_seen: int
    split_type: str
    currency: str
    status: str
    recent_charges: list[RecentCharge]


class SubscriptionsSummary(BaseModel):
    total_recurring: Decimal
    monthly_total: Decimal
    pct_of_total: float
    count: int


class SubscriptionsResponse(BaseModel):
    items: list[RecurringExpenseItem]
    summary_by_currency: dict[str, SubscriptionsSummary]
    computed_at: datetime | None


class SubscriptionOverrideRequest(BaseModel):
    merchant_key: str
    status: str | None = None
    category: str | None = None
    next_charge_day: int | None = None
