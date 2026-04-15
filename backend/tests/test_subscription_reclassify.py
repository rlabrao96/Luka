"""Tests for subscription split_type classification and cascade behavior."""

from __future__ import annotations

import pytest

from modules.subscriptions.schemas import SubscriptionOverrideRequest


class TestSubscriptionOverrideRequestSchema:
    def test_accepts_optional_split_type_shared(self):
        req = SubscriptionOverrideRequest(merchant_key="netflix", split_type="shared")
        assert req.split_type == "shared"

    def test_accepts_optional_split_type_personal(self):
        req = SubscriptionOverrideRequest(merchant_key="netflix", split_type="personal")
        assert req.split_type == "personal"

    def test_split_type_defaults_to_none(self):
        req = SubscriptionOverrideRequest(merchant_key="netflix")
        assert req.split_type is None

    def test_rejects_invalid_split_type(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SubscriptionOverrideRequest(merchant_key="netflix", split_type="partner")
