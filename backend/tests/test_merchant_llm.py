import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_llm_returns_4_categories():
    mock_response = '{"categories": ["Supermercado", "Retail", "Alimentos", "Hogar"]}'
    with patch("modules.merchants.llm.openai_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(
            return_value=type(
                "R",
                (),
                {
                    "choices": [
                        type("C", (), {"message": type("M", (), {"content": mock_response})()})()
                    ]
                },
            )()
        )
        from modules.merchants.llm import categorize_with_llm

        categories = await categorize_with_llm("LIDER")
    assert len(categories) == 4
    assert "Supermercado" in categories


@pytest.mark.asyncio
async def test_llm_returns_empty_list_on_error():
    with patch("modules.merchants.llm.openai_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API error"))
        from modules.merchants.llm import categorize_with_llm

        categories = await categorize_with_llm("UNKNOWN_MERCHANT")
    assert categories == []
