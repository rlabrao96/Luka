"""Pydantic schemas for the `/budgets/v2/{household_id}` endpoint.

These models lock the response contract the frontend (Chunks B, G, H) and
the Day-1 sample fixture build against. Changes here should be mirrored in
`backend/tests/fixtures/budget_v2_sample_response.json` and vice versa —
`test_contract_fixture_matches_pydantic_schema` enforces that invariant
on every test run.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class SankeyNode(BaseModel):
    id: str
    label: str
    value: Decimal
    risk: bool | None = None
    level: int | None = None
    kind: str | None = None
    member_id: str | None = None


class SankeyLink(BaseModel):
    source: str
    target: str
    value: Decimal


class SankeyBlock(BaseModel):
    nodes: list[SankeyNode]
    links: list[SankeyLink]


class SpendableBlock(BaseModel):
    amount: Decimal
    spent: Decimal
    remaining: Decimal
    pct_used: Decimal


class RiskCategory(BaseModel):
    name: str
    spent: Decimal
    cap: Decimal
    historical_mean: Decimal
    historical_std: Decimal
    p_overshoot: Decimal
    projected_final: Decimal
    alert: bool


class RunwayBlock(BaseModel):
    days_remaining: int
    days_to_payday: int
    daily_burn_14d: Decimal
    alert: bool


class CuotasBlock(BaseModel):
    this_month: Decimal
    future_total: Decimal
    active_count: int


class SavingsTargetBlock(BaseModel):
    target: Decimal
    progress: Decimal
    pct_complete: Decimal


class DrilldownItem(BaseModel):
    id: str
    date: date
    merchant: str
    amount: Decimal  # positive, display-ready
    category: str | None
    bank_name: str | None
    split_type: str | None = None


class DrilldownBlock(BaseModel):
    node_id: str
    label: str
    kind: str  # "transactions" | "empty"
    empty_reason: str | None = None
    items: list[DrilldownItem]


class BudgetV2Response(BaseModel):
    view: str  # "personal" | "household"
    month: date
    currency: str
    currencies_available: list[str]
    sankey: SankeyBlock
    spendable: SpendableBlock
    risk_categories: list[RiskCategory]
    runway: RunwayBlock
    cuotas: CuotasBlock
    savings_target: SavingsTargetBlock
