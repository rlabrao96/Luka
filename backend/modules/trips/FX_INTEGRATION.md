# FX Integration Plan — Trips Phase 4

**Status:** Discovery output for Task 4.0 of `2026-04-30-viajes-trips.md`.
**Headline finding:** the spec (§5.2) assumes "the existing FX service that powers Plaid + email parser." **That service does not exist in the codebase today.** Plaid and the email parser both record only the source `currency` string on each transaction; neither fetches, converts, nor stores any FX rate. Phase 4 must therefore *build* the FX service before it can "reuse" it.

---

## Module

There is no FX module to import. The `backend/modules/currencies/` package is unrelated — it manages the user's list of preferred display currencies (`UserCurrency` model: `user_id`, `currency_code`, `is_primary`, `sort_order`). It performs no conversion and never contacts a rate provider.

Verified with:
- `grep -rn "fx_rate|exchange_rate|to_usd|original_amount|convert" backend/` → only hits are in the new `trips/*` files.
- `requirements.txt` contains no FX/forex client (no `forex-python`, `currencyconverter`, `openexchangerates`, etc.).
- No Alembic migration creates an `fx_rates`, `currency_rates`, or `exchange_rates` table.

**Recommended new path (to be created in Phase 4):** `backend/modules/fx/service.py`, exposed as:

```python
from modules.fx.service import get_rate
```

## API (proposed — does not yet exist)

```python
async def get_rate(
    db: AsyncSession,
    *,
    from_currency: str,   # ISO-4217, 3 chars
    to_currency: str,     # ISO-4217
    on_date: date,        # historical date; if today → live fetch
) -> Decimal:
    """Returns the multiplier such that `amount_from * rate == amount_to`.
    Raises FxRateUnavailable on provider failure or unsupported currency.
    Same-currency call short-circuits to Decimal('1')."""
```

Example: `rate = await get_rate(db, from_currency="USD", to_currency="CLP", on_date=date(2026, 4, 15))`.

## Historical support

**None today.** Phase 4 must add it. Recommended provider: `frankfurter.app` (free, ECB-backed, supports arbitrary past dates back to 1999, no API key, weekend dates resolved to the prior business day server-side). Fallback: `open.er-api.com`. Both must be wrapped behind the same `get_rate` interface so the provider is swappable.

## Storage on transactions

`backend/modules/transactions/models.py::Transaction` stores **only** `currency: Mapped[str]` (line 21). There is no `fx_rate`, `to_usd`, `original_amount`, or `home_currency_amount` column. Plaid's `mapper.py` reads `iso_currency_code` and stores it verbatim; email parser does the same via `_parse_amount`. Implication: any cross-currency analytics today is silently broken — out of Phase 4 scope but worth flagging in NEXT-STEPS.

## Caching

No DB cache exists. The new module should add a `fx_rates` table keyed `(base_currency, quote_currency, rate_date)` with a `rate numeric(20,10)` and `fetched_at` timestamp. `get_rate` reads-through cache, fetches on miss, and persists. In-memory caching is unnecessary given the small fan-out per request.

## Trips usage plan

`service.create_expense` (`backend/modules/trips/service.py:450`) currently hard-codes `fx_rate_to_base=None` (line 535). After the FX module exists, replace that with: if `expense.currency == trip.base_currency` keep `None`; else call `get_rate(db, from_currency=expense.currency, to_currency=trip.base_currency, on_date=expense.expense_date)` and store the returned `Decimal` on `trip_expenses.fx_rate_to_base`. The same call is needed in (a) `service.create_settlement` for `trip_settlements.fx_rate_to_base`, and (b) the base-currency-change handler at `service.py:228` — it must compute the `cross_rate` for `trip_base_currency_changes` via `get_rate` for the change date. Auto-suggest matching (spec §4.x) also needs `get_rate` to convert a transaction's amount into trip base for the ±5%/$5 tolerance check.

## Gotchas

- **Spec mismatch:** §5.2 says "reuse the existing FX service." There is no such service. Update the spec or the plan to acknowledge the build cost (~½ day).
- **Frankfurter weekend behavior:** rate for Sat/Sun resolves to Friday's close. Document this so users don't see unexplained "rate moved by 0%" on weekends.
- **Decimal vs float:** all monetary math in trips uses `Decimal(14,2)`; FX must return `Decimal`, never `float`, to avoid rounding drift in the ±$0.50 settlement tolerance.
- **Provider outages:** `get_rate` must raise (not silently return `1.0` or `None`) so `create_expense` can 503 cleanly rather than persist a wrong rate.
- **Same-currency short-circuit:** must run *before* any provider call to keep CLP→CLP expenses free of network dependency.
- **No retroactive backfill:** existing `transactions.currency` rows have no associated rate. Trips can ignore this for now (FX is per-trip-expense, not per-transaction), but cross-currency dashboards remain broken until a separate effort.
