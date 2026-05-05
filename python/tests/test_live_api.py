from __future__ import annotations

import os

import pytest
from openai_ads import OpenAIAds

pytestmark = pytest.mark.skipif(not os.environ.get("OPENAI_ADS_API_KEY"), reason="OPENAI_ADS_API_KEY is not set")


def test_live_read_only_integration():
    client = OpenAIAds()
    assert client.ad_account.retrieve().id
    assert isinstance(client.campaigns.list(limit=1).get().data, list)
