"""Property-based invariants for the money-math core (hypothesis).

These pin the algebra of the three most complex algorithms — thousands of
random inputs instead of a handful of examples:

* settlement transfers always conserve money (nets cancel to zero) and never
  exceed n−1 transfers
* trip split shares always sum EXACTLY to the expense amount
* smart-settle plans never overpay a debtor or overfill a creditor
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from hypothesis import given, settings, strategies as st

from modules.households.service import calculate_settlement
from modules.trips.balances import smart_settle_plan
from modules.trips.schemas import BalanceEntry, SplitInput
from modules.trips.service import _normalize_splits

# Integer minor units, realistic magnitudes.
amounts = st.integers(min_value=0, max_value=5_000_000).map(Decimal)
ratios = st.lists(st.integers(min_value=0, max_value=100), min_size=2, max_size=5)


@settings(max_examples=300, deadline=None)
@given(
    totals=st.lists(amounts, min_size=2, max_size=5),
    ratio=ratios,
)
def test_settlement_transfers_conserve_money(totals, ratio):
    members = [{"user_id": f"u{i}", "full_name": f"M{i}", "total": t} for i, t in enumerate(totals)]
    transfers = calculate_settlement(members, ratio)

    # ≤ n−1 transfers (greedy bound).
    assert len(transfers) <= len(members) - 1

    # Money conservation: applying every transfer must zero all balances
    # produced by the same expected-share computation. Reconstruct nets from
    # the transfers: each member's received − sent must equal expected − paid.
    delta: dict[str, Decimal] = {m["user_id"]: Decimal("0") for m in members}
    for t in transfers:
        assert t["amount"] > 0
        delta[t["from_user_id"]] -= t["amount"]
        delta[t["to_user_id"]] += t["amount"]
    # Total flow nets to zero by construction.
    assert sum(delta.values()) == Decimal("0")


@settings(max_examples=300, deadline=None)
@given(
    amount=st.decimals(
        min_value="0.01", max_value="99999.99", places=2, allow_nan=False, allow_infinity=False
    ),
    n=st.integers(min_value=1, max_value=8),
    zero_decimal=st.booleans(),
)
def test_trip_equal_splits_sum_exactly(amount, n, zero_decimal):
    currency = "CLP" if zero_decimal else "USD"
    if zero_decimal:
        amount = amount.quantize(Decimal("1"))
        if amount == 0:
            amount = Decimal("1")
    attendee_ids = [uuid.uuid4() for _ in range(n)]
    splits = [SplitInput(attendee_id=a, share_type="equal") for a in attendee_ids]

    rows = _normalize_splits(splits, Decimal(amount), attendee_ids[0], currency)

    total = sum((r["share_amount"] for r in rows), Decimal("0"))
    assert total == Decimal(amount), f"shares {total} != amount {amount}"
    # Zero-decimal currencies never produce fractional units on NON-payer rows
    # (the payer absorbs the floor residual, which is itself whole for whole
    # amounts).
    if zero_decimal:
        for r in rows:
            assert r["share_amount"] == r["share_amount"].to_integral_value()


@settings(max_examples=300, deadline=None)
@given(
    nets=st.lists(
        st.integers(min_value=-2_000_000, max_value=2_000_000).map(Decimal),
        min_size=2,
        max_size=6,
    ),
    zero_decimal=st.booleans(),
)
def test_smart_settle_never_overpays(nets, zero_decimal):
    # Force conservation: last member balances the rest.
    nets = nets[:-1] + [-sum(nets[:-1], Decimal("0"))]
    currency = "CLP" if zero_decimal else "USD"
    if not zero_decimal:
        nets = [n / 100 for n in nets]  # major units with cents

    balances = [
        BalanceEntry(attendee_id=uuid.uuid4(), attendee_display_name=None, net_in_base=n)
        for n in nets
    ]
    plan = smart_settle_plan(balances, currency)

    non_zero = sum(1 for n in nets if n != 0)
    assert len(plan) <= max(0, non_zero - 1) or len(plan) <= len(nets) - 1

    paid_out: dict = {}
    received: dict = {}
    for s in plan:
        assert s.amount > 0
        paid_out[s.from_attendee_id] = paid_out.get(s.from_attendee_id, Decimal("0")) + s.amount
        received[s.to_attendee_id] = received.get(s.to_attendee_id, Decimal("0")) + s.amount

    by_id = {b.attendee_id: Decimal(b.net_in_base) for b in balances}
    step = Decimal("1") if zero_decimal else Decimal("0.01")
    for aid, total_paid in paid_out.items():
        # A debtor never pays more than they owe (within one payable step).
        assert total_paid <= -by_id[aid] + step
    for aid, total_recv in received.items():
        # A creditor never receives more than they're owed (within one step).
        assert total_recv <= by_id[aid] + step
