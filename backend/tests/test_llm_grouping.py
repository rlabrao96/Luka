import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_group_merchants_parses_llm_response():
    """Test that the grouping function correctly parses LLM JSON output."""
    from modules.merchant_review.llm_grouping import group_raw_merchants

    fake_llm_response = [
        {"display_name": "Lider", "raw_names": ["LIDER PROVIDENCIA", "LIDER LAS CONDES"]},
        {"display_name": "Netflix", "raw_names": ["NETFLIX.COM"]},
    ]

    with patch(
        "modules.merchant_review.llm_grouping._call_grouping_llm",
        new_callable=AsyncMock,
        return_value=fake_llm_response,
    ):
        result = await group_raw_merchants(["LIDER PROVIDENCIA", "LIDER LAS CONDES", "NETFLIX.COM"])

    assert len(result) == 2
    assert result[0]["display_name"] == "Lider"
    assert set(result[0]["raw_names"]) == {"LIDER PROVIDENCIA", "LIDER LAS CONDES"}
    assert result[1]["display_name"] == "Netflix"


@pytest.mark.asyncio
async def test_group_merchants_handles_empty_input():
    from modules.merchant_review.llm_grouping import group_raw_merchants

    result = await group_raw_merchants([])
    assert result == []


@pytest.mark.asyncio
async def test_group_merchants_handles_llm_failure():
    from modules.merchant_review.llm_grouping import group_raw_merchants

    with patch(
        "modules.merchant_review.llm_grouping._call_grouping_llm",
        new_callable=AsyncMock,
        side_effect=Exception("LLM timeout"),
    ):
        result = await group_raw_merchants(["LIDER PROVIDENCIA"])

    # On failure, each name becomes its own group with title-cased display name
    assert len(result) == 1
    assert result[0]["display_name"] == "Lider Providencia"
    assert result[0]["raw_names"] == ["LIDER PROVIDENCIA"]
