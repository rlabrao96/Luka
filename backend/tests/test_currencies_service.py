import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock


def _make_db():
    db = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    return db


def _make_uc(code, is_primary=False, sort_order=0):
    m = MagicMock()
    m.currency_code = code
    m.is_primary = is_primary
    m.sort_order = sort_order
    return m


_UNSET = object()


def _exec_returning(scalars_list=None, scalar_val=_UNSET):
    result = MagicMock()
    if scalars_list is not None:
        s = MagicMock()
        s.all = MagicMock(return_value=scalars_list)
        result.scalars = MagicMock(return_value=s)
    if scalar_val is not _UNSET:
        result.scalar = MagicMock(return_value=scalar_val)
        result.scalar_one_or_none = MagicMock(return_value=scalar_val)
    return result


# ---------------------------------------------------------------------------
# get_currencies
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_currencies_returns_existing_sorted():
    from modules.currencies.service import get_currencies

    uid = uuid.uuid4()
    db = _make_db()
    rows = [_make_uc("CLP", is_primary=True, sort_order=0), _make_uc("USD", sort_order=1)]
    db.execute = AsyncMock(return_value=_exec_returning(scalars_list=rows))

    result = await get_currencies(db, uid)
    assert len(result) == 2
    assert result[0].currency_code == "CLP"


@pytest.mark.asyncio
async def test_get_currencies_auto_seeds_from_preferred_currency():
    from modules.currencies.service import get_currencies

    uid = uuid.uuid4()
    db = _make_db()
    mock_user = MagicMock()
    mock_user.preferred_currency = "CLP"

    call_count = 0
    seeded = [_make_uc("CLP", is_primary=True, sort_order=0)]

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _exec_returning(scalars_list=[])        # no rows → triggers seed
        if call_count == 2:
            return _exec_returning(scalar_val=mock_user)   # fetch user for preferred_currency
        return _exec_returning(scalars_list=seeded)        # re-fetch after seed

    db.execute = mock_execute

    result = await get_currencies(db, uid)
    assert db.add.called
    assert db.commit.called
    assert result[0].currency_code == "CLP"
    assert result[0].is_primary is True


# ---------------------------------------------------------------------------
# add_currency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_currency_happy_path():
    from modules.currencies.service import add_currency

    uid = uuid.uuid4()
    db = _make_db()
    responses = iter([
        _exec_returning(scalar_val=None),   # duplicate check → not found
        _exec_returning(scalar_val=1),      # max sort_order → 1
    ])
    db.execute = AsyncMock(side_effect=lambda _: next(responses))

    result = await add_currency(db, uid, "USD")
    assert result.currency_code == "USD"
    assert result.is_primary is False
    assert db.add.called


@pytest.mark.asyncio
async def test_add_currency_invalid_code_raises():
    from modules.currencies.service import add_currency

    db = _make_db()
    with pytest.raises(ValueError, match="[Nn]ot supported"):
        await add_currency(db, uuid.uuid4(), "XXX")


@pytest.mark.asyncio
async def test_add_currency_duplicate_raises():
    from modules.currencies.service import add_currency

    uid = uuid.uuid4()
    db = _make_db()
    db.execute = AsyncMock(return_value=_exec_returning(scalar_val=_make_uc("USD")))

    with pytest.raises(ValueError, match="[Aa]lready"):
        await add_currency(db, uid, "USD")


# ---------------------------------------------------------------------------
# delete_currency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_currency_last_one_raises():
    from modules.currencies.service import delete_currency

    uid = uuid.uuid4()
    db = _make_db()
    db.execute = AsyncMock(return_value=_exec_returning(
        scalars_list=[_make_uc("CLP", is_primary=True, sort_order=0)]
    ))

    with pytest.raises(ValueError, match="[Uu]na moneda"):
        await delete_currency(db, uid, "CLP")


@pytest.mark.asyncio
async def test_delete_currency_non_primary():
    from modules.currencies.service import delete_currency

    uid = uuid.uuid4()
    db = _make_db()
    clp = _make_uc("CLP", is_primary=True, sort_order=0)
    usd = _make_uc("USD", sort_order=1)
    db.execute = AsyncMock(return_value=_exec_returning(scalars_list=[clp, usd]))
    db.delete = AsyncMock()  # ORM delete

    await delete_currency(db, uid, "USD")
    db.commit.assert_called_once()
    db.delete.assert_called_once()  # ORM delete was called for the target row
    assert clp.is_primary is True  # primary unchanged


@pytest.mark.asyncio
async def test_delete_currency_primary_promotes_lowest_sort_order():
    from modules.currencies.service import delete_currency

    uid = uuid.uuid4()
    db = _make_db()
    clp = _make_uc("CLP", is_primary=True, sort_order=0)
    usd = _make_uc("USD", is_primary=False, sort_order=1)
    cop = _make_uc("COP", is_primary=False, sort_order=2)

    call_n = 0

    async def mock_exec(stmt):
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            return _exec_returning(scalars_list=[clp, usd, cop])
        return MagicMock()

    db.execute = mock_exec
    db.delete = AsyncMock()  # ORM delete

    await delete_currency(db, uid, "CLP")
    assert usd.is_primary is True
    assert clp.is_primary is False
    db.delete.assert_called_once_with(clp)  # correct row passed to ORM delete
    assert cop.is_primary is False           # other non-promoted row unchanged
    db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# sync_preferred_currency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_preferred_currency_sets_existing_row_as_primary():
    from modules.currencies.service import sync_preferred_currency

    uid = uuid.uuid4()
    db = _make_db()
    clp = _make_uc("CLP", is_primary=True, sort_order=0)
    usd = _make_uc("USD", is_primary=False, sort_order=1)

    call_n = 0
    async def mock_exec(stmt):
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            return _exec_returning(scalars_list=[clp, usd])
        return MagicMock()

    db.execute = mock_exec

    await sync_preferred_currency(db, uid, "USD")
    assert usd.is_primary is True
    assert clp.is_primary is False
    db.commit.assert_not_called()  # caller is responsible for the commit
