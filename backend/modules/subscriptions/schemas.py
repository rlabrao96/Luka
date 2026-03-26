from __future__ import annotations

from datetime import date
from decimal import Decimal
from pydantic import BaseModel


class RecurringExpenseResponse(BaseModel):
    merchant_name: str
    category: str | None
    average_amount: Decimal
    last_amount: Decimal
    previous_amount: Decimal | None
    last_charge_date: date
    predicted_next_date: date
    frequency: str
    trend: str
    trend_pct: float | None
    months_seen: int
    split_type: str
