"""Single source of truth for "does this transaction count toward money totals?"

Every aggregate that sums transaction amounts (dashboard summary, budgets,
household contributions, settlements, category breakdowns) must apply the SAME
exclusion rule, or Luka's own screens disagree about income and spend.

The rule:

* ``status = 'orphan'`` rows never count.
* ``transaction_type = 'transfer'`` rows never count. This covers both legs of
  an own-account transfer pair AND the bank leg of a wallet funding pair.
  IMPORTANT: a ``transfer_pair_id`` alone is NOT an exclusion signal — the
  wallet leg of a funding pair carries the pair id but keeps its
  expense/income type and is the canonical row that MUST count.
* refund pairs net to zero — both legs excluded via ``refund_pair_id``.
* reimbursement groups net to zero — all legs excluded via
  ``reimbursement_group_id``.

Pending rows are a per-view decision (the dashboard excludes them, budgets
count them) — deliberately NOT part of this predicate.
"""

from modules.transactions.models import Transaction


def totals_exclusion_sql(alias: str = "t") -> str:
    """The exclusion rule as a raw-SQL fragment for text() queries.

    Compose with ``AND``: ``WHERE ... AND {totals_exclusion_sql('t')}``.
    """
    return (
        f"{alias}.status != 'orphan' "
        f"AND {alias}.transaction_type != 'transfer' "
        f"AND {alias}.refund_pair_id IS NULL "
        f"AND {alias}.reimbursement_group_id IS NULL "
        f"AND {alias}.needs_classification IS NOT TRUE"
    )


def counts_toward_totals_clauses() -> tuple:
    """The exclusion rule as SQLAlchemy clauses, for select() queries.

    Usage: ``query.where(*counts_toward_totals_clauses())``.
    """
    return (
        Transaction.status != "orphan",
        Transaction.transaction_type != "transfer",
        Transaction.refund_pair_id.is_(None),
        Transaction.reimbursement_group_id.is_(None),
        Transaction.needs_classification.isnot(True),
    )


def exclude_from_totals(query):
    """Apply the invariant that transfers, refund pairs, reimbursement groups
    and orphans do not contribute to spend/income/budget totals.

    Use this whenever aggregating (SUM) over ``transactions``. Do NOT use it
    to filter list views — paired rows stay visible and the frontend groups
    them visually.
    """
    return query.where(*counts_toward_totals_clauses())
