import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from modules.merchants.service import lookup_merchant


@pytest.mark.asyncio
async def test_returns_cached_categories_on_redis_hit():
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(
        return_value=json.dumps(["Supermercado", "Retail", "Alimentos", "Hogar"])
    )
    mock_db = AsyncMock()
    result = await lookup_merchant("COMPRA LIDER PROVI", db=mock_db, redis=mock_redis)
    assert result == ["Supermercado", "Retail", "Alimentos", "Hogar"]
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
        mock_llm.return_value = ["Combustible", "Auto", "Transporte", "Servicios"]
        result = await lookup_merchant("COPEC VITACURA", db=mock_db, redis=mock_redis)

    assert "Combustible" in result
    mock_llm.assert_called_once_with("COPEC")  # normalized name
    mock_redis.setex.assert_called_once()  # result cached
