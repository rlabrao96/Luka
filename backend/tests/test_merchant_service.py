import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from modules.merchants.service import lookup_merchant


@pytest.mark.asyncio
async def test_returns_cached_categories_on_redis_hit():
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=json.dumps(["Supermercado"]))
    mock_db = AsyncMock()
    result = await lookup_merchant("COMPRA LIDER PROVI", db=mock_db, redis=mock_redis)
    assert result == ["Supermercado"]
    mock_redis.get.assert_called_once()
    # DB should NOT be called on cache hit
    mock_db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_calls_llm_on_cache_and_db_miss():
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()

    # Mock DB: scalar_one_or_none returns None (cache miss)
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = None
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_execute_result)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    with patch("modules.merchants.service.categorize_with_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = ["Combustible", "Auto", "Transporte"]
        result = await lookup_merchant("COPEC VITACURA", db=mock_db, redis=mock_redis)

    assert "Combustible" in result
    assert len(result) == 3
    mock_llm.assert_called_once_with("COPEC")  # normalized name
    mock_redis.setex.assert_called_once()  # result cached


@pytest.mark.asyncio
async def test_returns_single_category_for_known_merchant():
    """Known merchant with user selections returns only top 1 category."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)  # cache miss
    mock_redis.setex = AsyncMock()

    mock_merchant = MagicMock()
    mock_merchant.id = 1
    mock_merchant.llm_suggested_categories = ["Supermercado", "Retail", "Alimentos"]

    mock_category = MagicMock()
    mock_category.category = "Supermercado"

    mock_merchant_result = MagicMock()
    mock_merchant_result.scalar_one_or_none.return_value = mock_merchant

    mock_categories_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_category]
    mock_categories_result.scalars.return_value = mock_scalars

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[mock_merchant_result, mock_categories_result])

    result = await lookup_merchant("LIDER PROVI", db=mock_db, redis=mock_redis)
    assert result == ["Supermercado"]
    assert len(result) == 1


@pytest.mark.asyncio
async def test_returns_single_llm_suggestion_for_merchant_without_selections():
    """Merchant in DB with only LLM suggestions returns top 1 suggestion."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()

    mock_merchant = MagicMock()
    mock_merchant.id = 1
    mock_merchant.llm_suggested_categories = ["Combustible", "Auto", "Transporte"]

    mock_merchant_result = MagicMock()
    mock_merchant_result.scalar_one_or_none.return_value = mock_merchant

    mock_categories_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_categories_result.scalars.return_value = mock_scalars

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[mock_merchant_result, mock_categories_result])

    result = await lookup_merchant("COPEC VITACURA", db=mock_db, redis=mock_redis)
    assert result == ["Combustible"]
    assert len(result) == 1
