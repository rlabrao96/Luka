"""Heuristic v1 forecast engine for budget-v2.

These are intentionally simple functions — share×CV ranking, pace projection,
Gaussian overshoot probability — so the budget page has a deterministic,
auditable signal in the first sprint. A future Bayesian engine will swap in
behind the same signatures.

All monetary inputs/outputs are `Decimal` to avoid drift with SQLAlchemy's
Numeric columns. Statistical math still runs in float internally (stdlib
`statistics` + `math.erf`), with results cast back to Decimal at the edge.
"""

from __future__ import annotations

import math
import statistics
from decimal import Decimal
from typing import Iterable


_ZERO = Decimal("0")


# -------------------------------------------------------------- category stats


def category_stats(monthly_spends: Iterable[Decimal]) -> tuple[Decimal, Decimal, int]:
    """Return (mean, population stdev, n) over a list of monthly totals.

    Empty iterables return (0, 0, 0). Single-value series returns (x, 0, 1).
    Uses `statistics.pstdev` (population stdev) so a 3-month window behaves
    like the usual household-budget intuition — we're describing this user's
    realized spend, not inferring a population.
    """
    values = [float(v) for v in monthly_spends]
    n = len(values)
    if n == 0:
        return _ZERO, _ZERO, 0
    mean = statistics.mean(values)
    std = statistics.pstdev(values) if n > 1 else 0.0
    return Decimal(str(round(mean, 2))), Decimal(str(round(std, 2))), n


# ----------------------------------------------------- select risk categories


def select_risk_categories(
    stats: dict[str, tuple[Decimal, Decimal, int]],
    top_n: int = 5,
) -> list[tuple[str, Decimal]]:
    """Rank categories by `share × CV`, return top N as `[(name, score)]`.

    Intuition: a category is "risky" when it's a meaningful slice of the
    budget AND its month-to-month spend swings. CV (coefficient of variation,
    std/mean) normalizes swing relative to scale so Supermercado and
    Restaurantes can be compared on the same axis.

    Categories with zero mean (no data) are excluded.
    """
    if not stats:
        return []
    total_mean = sum((m for (m, _s, _n) in stats.values()), start=_ZERO)
    if total_mean == _ZERO:
        return []

    scored: list[tuple[str, Decimal]] = []
    for name, (mean, std, _n) in stats.items():
        if mean <= _ZERO:
            continue
        share = mean / total_mean  # Decimal/Decimal -> Decimal
        cv = std / mean
        score = share * cv
        scored.append((name, score))

    scored.sort(key=lambda kv: kv[1], reverse=True)
    return scored[:top_n]


# ----------------------------------------------------------------- pace forecast


def pace_forecast(
    spent_so_far: Decimal,
    current_day: int,
    days_in_month: int,
    historical_std: Decimal,
) -> tuple[Decimal, Decimal]:
    """Linearly project final spend from MTD, guarding early-month noise.

    Returns `(projected_final, projected_std)`. The projected std is scaled
    proportionally with the pace ratio so the overshoot probability picks
    up on wide historical swings.

    Day-3 guard: for `current_day < 3` we treat it as day 3. Without this,
    spending $10k on day 1 would "project" a $300k month for a category
    that normally runs $100k — way too noisy a signal to ship to users.
    """
    if days_in_month <= 0:
        return spent_so_far, historical_std
    effective_day = max(current_day, 3)
    if effective_day >= days_in_month:
        return spent_so_far, historical_std
    ratio = Decimal(days_in_month) / Decimal(effective_day)
    projected = spent_so_far * ratio
    projected_std = historical_std * ratio
    return projected, projected_std


# ------------------------------------------------------ overshoot probability


def overshoot_probability(projected: Decimal, cap: Decimal, std: Decimal) -> Decimal:
    """Gaussian P(actual > cap) given `projected` as the mean and `std` as σ.

    Uses `math.erf` to compute the normal CDF exactly (no scipy dep). When
    `std == 0` the distribution collapses to a step function — use a hard
    threshold instead of dividing by zero.

    Returned probability is a Decimal in [0, 1].
    """
    if std <= _ZERO:
        return Decimal("1") if projected > cap else _ZERO
    z = (float(cap) - float(projected)) / float(std)
    # P(X > cap) = 1 - Φ(z)
    cdf = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    p_over = max(0.0, min(1.0, 1.0 - cdf))
    return Decimal(str(round(p_over, 4)))


# ------------------------------------------------------------------- runway


def runway_days(spendable_remaining: Decimal, daily_burn_14: Decimal) -> int:
    """How many days of runway given remaining budget and the 14-day burn rate.

    Zero burn returns a large sentinel (365 days) instead of infinity so the
    UI has a safe upper bound.
    """
    if spendable_remaining <= _ZERO:
        return 0
    if daily_burn_14 <= _ZERO:
        return 365
    return int(spendable_remaining / daily_burn_14)


# -------------------------------------------------------- spendable ceiling


def spendable_ceiling(
    income: Decimal,
    known_bills: Decimal,
    cuotas_this_month: Decimal,
    savings_target: Decimal,
) -> Decimal:
    """Discretionary budget = income minus fixed commitments.

    Clamped to 0 — a negative ceiling is a signal to the user, not a usable
    number, and `v2_service` handles the overdraft story separately via
    `ceiling_clamped`-style flags in downstream blocks.
    """
    ceiling = income - known_bills - cuotas_this_month - savings_target
    return ceiling if ceiling > _ZERO else _ZERO
