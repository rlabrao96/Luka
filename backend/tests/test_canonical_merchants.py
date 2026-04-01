import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_create_canonical_from_groups():
    """Test that LLM groups are correctly persisted as canonical merchants."""
    from modules.merchant_review.service import create_canonicals_from_groups

    groups = [
        {"display_name": "Lider", "raw_names": ["LIDER PROVIDENCIA", "LIDER LAS CONDES"]},
        {"display_name": "Netflix", "raw_names": ["NETFLIX.COM"]},
    ]

    with patch(
        "modules.merchant_review.service._get_or_create_canonical",
        new_callable=AsyncMock,
    ) as mock_get_or_create:
        mock_get_or_create.side_effect = [
            {"id": "00000000-0000-0000-0000-000000000001", "display_name": "Lider", "is_new": True},
            {
                "id": "00000000-0000-0000-0000-000000000002",
                "display_name": "Netflix",
                "is_new": True,
            },
        ]
        with patch(
            "modules.merchant_review.service._link_merchants_to_canonical",
            new_callable=AsyncMock,
        ):
            result = await create_canonicals_from_groups(None, groups)

    assert len(result) == 2
    assert mock_get_or_create.call_count == 2
