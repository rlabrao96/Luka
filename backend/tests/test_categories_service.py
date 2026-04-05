import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call


def _mock_db():
    db = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    return db


def _make_pref(category, category_type, sort_order=0, is_custom=False):
    p = MagicMock()
    p.category = category
    p.category_type = category_type
    p.sort_order = sort_order
    p.is_custom = is_custom
    return p


_UNSET = object()


def _execute_returning(scalars_list=None, scalar_val=_UNSET):
    """Build a mock db.execute() return that supports .scalars().all() or .scalar()"""
    result = MagicMock()
    if scalars_list is not None:
        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=scalars_list)
        result.scalars = MagicMock(return_value=scalars_mock)
    if scalar_val is not _UNSET:
        result.scalar = MagicMock(return_value=scalar_val)
        result.scalar_one_or_none = MagicMock(return_value=scalar_val)
    return result


# ---------------------------------------------------------------------------
# get_category_preferences
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_category_preferences_seeds_when_empty():
    """User with no rows gets default 22 categories seeded."""
    from modules.settings.service import get_category_preferences

    user_id = uuid.uuid4()
    db = _mock_db()

    # First execute (check existing): returns empty list
    # Second execute (after seed): returns 2 sample prefs
    sample_prefs = [
        _make_pref("Alimentación", "expense", 0),
        _make_pref("Sueldo", "income", 0),
    ]

    call_count = 0
    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _execute_returning(scalars_list=[])
        return _execute_returning(scalars_list=sample_prefs)

    db.execute = mock_execute

    result = await get_category_preferences(db, user_id)

    assert db.add.called  # defaults were seeded
    assert db.commit.called
    assert any(r["category"] == "Alimentación" for r in result)


@pytest.mark.asyncio
async def test_get_category_preferences_expense_before_income():
    """Expense categories appear before income in the returned list."""
    from modules.settings.service import get_category_preferences

    user_id = uuid.uuid4()
    db = _mock_db()

    prefs = [
        _make_pref("Sueldo", "income", 0),
        _make_pref("Alimentación", "expense", 0),
    ]
    db.execute = AsyncMock(return_value=_execute_returning(scalars_list=prefs))

    result = await get_category_preferences(db, user_id)

    types = [r["category_type"] for r in result]
    # All expense before income
    expense_indices = [i for i, t in enumerate(types) if t == "expense"]
    income_indices = [i for i, t in enumerate(types) if t == "income"]
    if expense_indices and income_indices:
        assert max(expense_indices) < min(income_indices)


# ---------------------------------------------------------------------------
# add_category
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_category_happy_path():
    """Valid new category is inserted with is_custom=True."""
    from modules.settings.service import add_category

    user_id = uuid.uuid4()
    db = _mock_db()

    execute_responses = iter([
        _execute_returning(scalar_val=5),   # count query → 5 existing
        _execute_returning(scalar_val=None), # duplicate check → not found
        _execute_returning(scalar_val=4),   # max sort_order → 4
    ])
    db.execute = AsyncMock(side_effect=lambda _: next(execute_responses))

    result = await add_category(db, user_id, "Mascotas", "expense")

    assert result["category"] == "Mascotas"
    assert result["is_custom"] is True
    assert result["category_type"] == "expense"
    assert db.add.called


@pytest.mark.asyncio
async def test_add_category_at_limit_raises():
    """Adding when 19 already exist raises ValueError."""
    from modules.settings.service import add_category

    user_id = uuid.uuid4()
    db = _mock_db()
    db.execute = AsyncMock(return_value=_execute_returning(scalar_val=19))

    with pytest.raises(ValueError, match="19"):
        await add_category(db, user_id, "Nueva", "expense")


@pytest.mark.asyncio
async def test_add_category_duplicate_raises():
    """Adding a category that already exists raises ValueError."""
    from modules.settings.service import add_category

    user_id = uuid.uuid4()
    db = _mock_db()

    existing_pref = _make_pref("Alimentación", "expense")
    execute_responses = iter([
        _execute_returning(scalar_val=5),          # count → 5
        _execute_returning(scalar_val=existing_pref),  # duplicate check → found
    ])
    db.execute = AsyncMock(side_effect=lambda _: next(execute_responses))

    with pytest.raises(ValueError, match="[Dd]uplicate"):
        await add_category(db, user_id, "Alimentación", "expense")


@pytest.mark.asyncio
async def test_add_category_empty_name_raises():
    """Empty/whitespace name raises ValueError."""
    from modules.settings.service import add_category

    db = _mock_db()
    with pytest.raises(ValueError):
        await add_category(db, uuid.uuid4(), "   ", "expense")


# ---------------------------------------------------------------------------
# reorder_categories
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reorder_categories_valid():
    """Valid reorder updates sort_order on existing rows."""
    from modules.settings.service import reorder_categories

    user_id = uuid.uuid4()
    db = _mock_db()

    pref_a = _make_pref("Alimentación", "expense", 0)
    pref_b = _make_pref("Hogar", "expense", 1)

    # First execute: existing rows; second execute: re-fetch after commit
    execute_responses = iter([
        _execute_returning(scalars_list=[pref_a, pref_b]),
        _execute_returning(scalars_list=[pref_b, pref_a]),  # after reorder
    ])
    db.execute = AsyncMock(side_effect=lambda _: next(execute_responses))

    items = [
        {"category": "Hogar", "sort_order": 0},
        {"category": "Alimentación", "sort_order": 1},
    ]
    await reorder_categories(db, user_id, items)

    assert pref_a.sort_order == 1
    assert pref_b.sort_order == 0
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_reorder_categories_mismatch_raises():
    """Submitted set that differs from existing raises ValueError."""
    from modules.settings.service import reorder_categories

    user_id = uuid.uuid4()
    db = _mock_db()

    pref_a = _make_pref("Alimentación", "expense", 0)
    db.execute = AsyncMock(return_value=_execute_returning(scalars_list=[pref_a]))

    items = [
        {"category": "Alimentación", "sort_order": 0},
        {"category": "Hogar", "sort_order": 1},  # not in existing
    ]
    with pytest.raises(ValueError):
        await reorder_categories(db, user_id, items)


# ---------------------------------------------------------------------------
# get_category_usage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_category_usage_returns_count():
    """Returns count of TransactionSplit rows with matching category."""
    from modules.settings.service import get_category_usage

    user_id = uuid.uuid4()
    db = _mock_db()
    db.execute = AsyncMock(return_value=_execute_returning(scalar_val=7))

    count = await get_category_usage(db, user_id, "Alimentación")
    assert count == 7


# ---------------------------------------------------------------------------
# delete_category
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_category_no_reclassify():
    """Deletes preference row and merchant selections without updating transactions."""
    from modules.settings.service import delete_category

    user_id = uuid.uuid4()
    db = _mock_db()
    # reclassify_to is None → only deletes
    db.execute = AsyncMock()

    await delete_category(db, user_id, "Hogar", reclassify_to=None)

    db.commit.assert_called_once()
    assert db.execute.call_count == 2  # delete MerchantCategorySelection + delete preference


@pytest.mark.asyncio
async def test_delete_category_with_reclassify():
    """Updates transactions + splits, deletes merchant selections, deletes preference."""
    from modules.settings.service import delete_category

    user_id = uuid.uuid4()
    db = _mock_db()

    # First execute: validate reclassify_to exists
    target_pref = _make_pref("Otros", "expense")
    execute_responses = iter([
        _execute_returning(scalar_val=target_pref),  # reclassify_to validation
        MagicMock(),  # update splits
        MagicMock(),  # update transactions
        MagicMock(),  # delete merchant selections
        MagicMock(),  # delete preference
    ])
    db.execute = AsyncMock(side_effect=lambda _: next(execute_responses))

    await delete_category(db, user_id, "Hogar", reclassify_to="Otros")

    db.commit.assert_called_once()
    assert db.execute.call_count == 5


@pytest.mark.asyncio
async def test_delete_category_invalid_reclassify_to_raises():
    """reclassify_to that doesn't exist in user's preferences raises ValueError."""
    from modules.settings.service import delete_category

    user_id = uuid.uuid4()
    db = _mock_db()
    db.execute = AsyncMock(return_value=_execute_returning(scalar_val=None))  # not found

    with pytest.raises(ValueError, match="not found"):
        await delete_category(db, user_id, "Hogar", reclassify_to="Nonexistent")
