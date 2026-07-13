"""Shared-card charge classification: pend charges on a shared_card until sorted.
See docs/superpowers/specs/2026-07-12-shared-card-charge-classification-design.md.
"""

from __future__ import annotations


def should_pend(account_type: str | None, transaction_type: str | None) -> bool:
    """A non-transfer charge on a shared_card account is pending classification."""
    return account_type == "shared_card" and transaction_type != "transfer"
