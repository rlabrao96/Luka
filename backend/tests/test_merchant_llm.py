import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_llm_returns_3_categories():
    mock_response = MagicMock()
    mock_response.text = '{"categories": ["Supermercado", "Retail", "Alimentos"]}'

    with patch("modules.merchants.llm._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client
        from modules.merchants.llm import categorize_with_llm

        categories = await categorize_with_llm("LIDER")
    assert len(categories) == 3
    assert "Supermercado" in categories


@pytest.mark.asyncio
async def test_llm_strips_code_fences():
    mock_response = MagicMock()
    mock_response.text = '```json\n{"categories": ["Combustible", "Auto", "Transporte"]}\n```'

    with patch("modules.merchants.llm._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client
        from modules.merchants.llm import categorize_with_llm

        categories = await categorize_with_llm("COPEC")
    assert len(categories) == 3
    assert "Combustible" in categories


@pytest.mark.asyncio
async def test_llm_returns_empty_list_on_error():
    with patch("modules.merchants.llm._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(side_effect=Exception("API error"))
        mock_get_client.return_value = mock_client
        from modules.merchants.llm import categorize_with_llm

        categories = await categorize_with_llm("UNKNOWN_MERCHANT")
    assert categories == []


@pytest.mark.asyncio
async def test_llm_truncates_to_3_categories():
    mock_response = MagicMock()
    mock_response.text = '{"categories": ["A", "B", "C", "D", "E"]}'

    with patch("modules.merchants.llm._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client
        from modules.merchants.llm import categorize_with_llm

        categories = await categorize_with_llm("LIDER")
    assert len(categories) == 3
