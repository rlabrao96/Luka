"""Partner-card charge attribution: hand off a transaction on a shared card to
a household partner. See docs/superpowers/specs/2026-07-12-partner-card-charge-attribution-design.md.
"""

from __future__ import annotations

import uuid

from sqlalchemy import or_

from modules.transactions.models import Transaction, TransactionAttribution


def effective_owner_id(owner_user_id: uuid.UUID, attribution: TransactionAttribution | None):
    """Who a transaction's amount counts for: the recipient when actively
    attributed, otherwise the account/transaction owner."""
    if attribution is not None and attribution.status == "active":
        return attribution.attributed_to_user_id
    return owner_user_id


def attributed_to_clause(caller_id: uuid.UUID):
    """Rows actively attributed to ``caller_id``. Requires outerjoin(TransactionAttribution)."""
    return (TransactionAttribution.attributed_to_user_id == caller_id) & (
        TransactionAttribution.status == "active"
    )


def owned_by_caller_clause(caller_id: uuid.UUID):
    """A transaction counts for ``caller_id`` when it is their own row and NOT
    actively attributed away, OR it is actively attributed TO them.

    Requires the query to ``outerjoin(TransactionAttribution)``. This is the
    single predicate the exactly-one-owner AGGREGATES use (dashboard totals,
    category breakdown), guaranteeing exactly-one-owner by construction.
    """
    attributed_away = (TransactionAttribution.id.isnot(None)) & (
        TransactionAttribution.status == "active"
    )
    own_kept = (Transaction.user_id == caller_id) & (~attributed_away)
    return or_(own_kept, attributed_to_clause(caller_id))
