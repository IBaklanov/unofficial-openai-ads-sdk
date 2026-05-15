from __future__ import annotations

from datetime import date, timedelta

import httpx
import pytest
from openai_ads import OpenAIAds, RateLimitError, ValidationError


def response(body, status_code=200, headers=None):
    return httpx.Response(status_code, json=body, headers=headers or {})


def test_campaign_create_does_not_require_campaign_id():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return response(
            {
                "id": "cmpn_1",
                "created_at": 1,
                "updated_at": 1,
                "name": "Campaign",
                "status": "paused",
                "budget": {"lifetime_spend_limit_micros": 1_000_000},
            }
        )

    client = OpenAIAds(api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    campaign = client.campaigns.create(
        name="Campaign",
        status="paused",
        budget={"lifetime_spend_limit_micros": 1_000_000},
        bidding_type="clicks",
    )
    assert campaign.id == "cmpn_1"
    assert requests[0].url.path == "/v1/campaigns"
    assert "campaign_id" not in requests[0].content.decode()


def test_campaign_budget_mapping_and_unsupported_update_fields():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return response(
            {
                "id": "cmpn_1",
                "created_at": 1,
                "updated_at": 1,
                "name": "Campaign",
                "status": "paused",
                "budget": {"lifetime_spend_limit_micros": 1_000_000},
            }
        )

    client = OpenAIAds(api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    client.campaigns.create(name="Campaign", status="paused", budget={"spend_limit_micros": 1_000_000})

    assert '"budget":{"lifetime_spend_limit_micros":1000000}' in requests[0].content.decode()
    with pytest.raises(ValidationError):
        client.campaigns.create(name="Campaign", status="paused", budget={"daily_spend_limit_micros": 1_000_000})
    with pytest.raises(ValidationError):
        client.campaigns.update("cmpn_1", bidding_type="clicks")


def test_ad_group_create_supports_click_billing():
    def handler(request: httpx.Request) -> httpx.Response:
        return response(
            {
                "id": "adgrp_1",
                "created_at": 1,
                "updated_at": 1,
                "name": "Group",
                "status": "paused",
                "bidding_config": {"billing_event_type": "click", "max_bid_micros": 3_000_000},
            }
        )

    client = OpenAIAds(api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    ad_group = client.ad_groups.create(
        campaign_id="cmpn_1",
        name="Group",
        status="paused",
        bidding_config={"billing_event_type": "click", "max_bid_micros": 3_000_000},
    )
    assert ad_group.bidding_config["billing_event_type"] == "click"


def test_insights_array_query_encoding():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return response({"object": "list", "data": [], "has_more": False})

    client = OpenAIAds(api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    client.insights.ad(
        "ad_1", fields=["ad.id", "ad.cpc"], date_range={"since": "2026-05-04", "until": "2026-05-05"}
    ).get()
    assert "fields%5B%5D=ad.id" in seen[0]
    assert "time_ranges%5B%5D=" in seen[0]


def test_insights_reject_legacy_undotted_fields():
    client = OpenAIAds(
        api_key="test",
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda request: response({"object": "list", "data": [], "has_more": False}))
        ),
    )
    with pytest.raises(ValidationError):
        client.insights.ad("ad_1", fields=["ad_group_name"]).get()
    with pytest.raises(ValidationError):
        client.insights.ad("ad_1", fields=["timezone"]).get()
    client.insights.ad("ad_1", fields=["ad_group.name", "metadata.timezone"]).get()


def test_insights_reject_future_until_date():
    client = OpenAIAds(
        api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(lambda request: response({})))
    )
    future = (date.today() + timedelta(days=1)).isoformat()
    with pytest.raises(ValidationError):
        client.insights.ad("ad_1", date_range={"since": "2026-05-04", "until": future}).get()


def test_rate_limit_retries():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return response({"error": {"message": "too many"}}, 429, {"retry-after": "0"})

    client = OpenAIAds(api_key="test", max_retries=1, http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(RateLimitError):
        client.campaigns.list(limit=1).get()
    assert calls == 2


def test_strict_request_validation():
    client = OpenAIAds(
        api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(lambda request: response({})))
    )
    with pytest.raises(ValidationError):
        client.campaigns.create(name="  ", status="paused", budget={"lifetime_spend_limit_micros": 10})
