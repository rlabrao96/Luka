"""Shared JSON-walking helpers for privacy / redaction tests.

Chunk C wrote a local copy of these inside `test_budget_v2_endpoint.py`;
Chunk D promotes them to a shared module so the contribution-mode
regression suite and any future redaction test can share the same
Decimal-aware comparison logic.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Iterator


def walk_json(obj: Any) -> Iterator[Any]:
    """Yield every leaf value in a JSON-parsed structure.

    Descends into dicts (values only) and lists. Anything else (str, int,
    float, bool, None, Decimal) is yielded as-is.
    """
    if isinstance(obj, dict):
        for v in obj.values():
            yield from walk_json(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_json(v)
    else:
        yield obj


def assert_value_absent(obj: Any, forbidden_value: Decimal | int | float) -> None:
    """Raise AssertionError if any leaf equals ``forbidden_value``.

    Decimal-aware: compares by ``Decimal(str(leaf)) == Decimal(str(forbidden))``
    so ``2137913`` matches ``Decimal("2137913.00")`` and ``"2137913"``.
    Non-numeric leaves (arbitrary strings, None, bools) are skipped.
    """
    forbidden = Decimal(str(forbidden_value))
    for leaf in walk_json(obj):
        if leaf is None or isinstance(leaf, bool):
            # bool is a subclass of int — skip to avoid False==0 false-positives.
            continue
        try:
            if Decimal(str(leaf)) == forbidden:
                raise AssertionError(f"Forbidden value {forbidden} found in response JSON")
        except (ValueError, InvalidOperation):
            # Non-numeric string — not a match candidate.
            continue
