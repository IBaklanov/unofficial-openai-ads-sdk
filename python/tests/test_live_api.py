from __future__ import annotations

import os
import random
import string
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from typing import Literal

import pytest
from openai_ads import OpenAIAds

pytestmark = pytest.mark.skipif(not os.environ.get("OPENAI_ADS_API_KEY"), reason="OPENAI_ADS_API_KEY is not set")


def test_live_read_only_integration():
    client = OpenAIAds()
    assert client.ad_account.retrieve().id
    assert isinstance(client.campaigns.list(limit=1).get().data, list)


@pytest.mark.skipif(
    os.environ.get("OPENAI_ADS_LIVE_MUTATE") != "1",
    reason="OPENAI_ADS_LIVE_MUTATE=1 is required for mutating integration tests",
)
@pytest.mark.parametrize(
    ("label", "billing_event_type", "max_bid_micros"),
    [
        ("cpm", "impression", 60_000),
        ("cpc", "click", 3_000_000),
    ],
)
def test_live_mutating_integration_creates_updates_insights_and_archives(
    label: Literal["cpm", "cpc"],
    billing_event_type: Literal["impression", "click"],
    max_bid_micros: int,
):
    client = OpenAIAds()
    suffix = f"sdk-validation-{label}-{int(datetime.now(timezone.utc).timestamp())}-{random_suffix()}"
    created: dict[str, str] = {}
    dates = validation_dates()

    try:
        assert client.ad_account.retrieve().id

        upload = client.uploads.create(file=("sdk-validation.png", BytesIO(VALIDATION_PNG), "image/png"))
        assert upload.file_id

        campaign = client.campaigns.create(
            name=f"SDK validation campaign {suffix}",
            description=f"Disposable SDK validation campaign {suffix}",
            status="paused",
            start_time=dates["start"],
            end_time=dates["end"],
            budget={"lifetime_spend_limit_micros": 1_000_000},
            targeting={"locations": {"countries": ["US"]}},
            bidding_type="clicks" if billing_event_type == "click" else "impressions",
        )
        created["campaign_id"] = campaign.id
        assert suffix in campaign.name

        assert isinstance(client.campaigns.list(limit=20, order="desc").get().data, list)
        assert client.campaigns.retrieve(campaign.id).id == campaign.id
        updated_campaign = client.campaigns.update(
            campaign.id,
            description=f"Updated disposable SDK validation campaign {suffix}",
            status="paused",
        )
        assert updated_campaign.description and "Updated" in updated_campaign.description

        ad_group = client.ad_groups.create(
            campaign_id=campaign.id,
            name=f"SDK validation {label} ad group {suffix}",
            description=f"Disposable SDK validation ad group {suffix}",
            context_hints=["sdk validation", label, suffix],
            status="paused",
            bidding_config={"billing_event_type": billing_event_type, "max_bid_micros": max_bid_micros},
        )
        created["ad_group_id"] = ad_group.id
        assert ad_group.bidding_config["billing_event_type"] == billing_event_type

        assert isinstance(client.ad_groups.list(campaign_id=campaign.id, limit=20).get().data, list)
        assert client.ad_groups.retrieve(ad_group.id).id == ad_group.id
        updated_ad_group = client.ad_groups.update(
            ad_group.id,
            context_hints=["sdk validation", "updated", label, suffix],
            status="paused",
            bidding_config={"billing_event_type": billing_event_type, "max_bid_micros": max_bid_micros},
        )
        assert "updated" in (updated_ad_group.context_hints or [])

        ad = client.ads.create(
            ad_group_id=ad_group.id,
            name=f"SDK validation ad {suffix}",
            status="paused",
            creative={
                "type": "chat_card",
                "title": "SDK validation",
                "body": "Disposable SDK validation creative.",
                "target_url": "https://example.com/workspace-planner",
                "file_id": upload.file_id,
            },
        )
        created["ad_id"] = ad.id
        assert suffix in ad.name

        assert isinstance(client.ads.list(ad_group_id=ad_group.id, limit=20).get().data, list)
        assert client.ads.retrieve(ad.id).id == ad.id
        updated_ad = client.ads.update(
            ad.id,
            name=f"SDK validation ad updated {suffix}",
            status="paused",
            creative={
                "type": "chat_card",
                "title": "Validation v2",
                "body": "Updated disposable validation creative.",
                "target_url": "https://example.com/workspace-planner",
                "file_id": upload.file_id,
            },
        )
        assert "updated" in updated_ad.name

        insight_params = {
            "time_granularity": "none",
            "aggregation_level": "ad",
            "limit": 1,
            "date_range": {"since": dates["since"], "until": dates["until"]},
            "fields": ["ad.id", "ad.name", "ad.clicks", "ad.impressions"],
        }
        assert isinstance(client.insights.ad_account(**insight_params).get().data, list)
        assert isinstance(client.insights.campaign(campaign.id, **insight_params).get().data, list)
        assert isinstance(client.insights.ad_group(ad_group.id, **insight_params).get().data, list)
        assert isinstance(client.insights.ad(ad.id, **insight_params).get().data, list)

        assert client.ads.activate(ad.id).id == ad.id
        paused_ad = client.ads.pause(ad.id)
        assert client.ad_groups.activate(ad_group.id).id == ad_group.id
        paused_ad_group = client.ad_groups.pause(ad_group.id)
        assert client.campaigns.activate(campaign.id).id == campaign.id
        paused_campaign = client.campaigns.pause(campaign.id)

        assert paused_ad.status == "paused"
        assert paused_ad_group.status == "paused"
        assert paused_campaign.status == "paused"
    finally:
        archive_created(client, created)


def archive_created(client: OpenAIAds, created: dict[str, str]) -> None:
    if ad_id := created.get("ad_id"):
        try:
            client.ads.archive(ad_id)
        except Exception:
            pass
    if ad_group_id := created.get("ad_group_id"):
        try:
            client.ad_groups.archive(ad_group_id)
        except Exception:
            pass
    if campaign_id := created.get("campaign_id"):
        try:
            client.campaigns.archive(campaign_id)
        except Exception:
            pass


def validation_dates() -> dict[str, int | str]:
    today = date.today()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)
    day_after = today + timedelta(days=2)
    return {
        "since": yesterday.isoformat(),
        "until": today.isoformat(),
        "start": unix_seconds(tomorrow),
        "end": unix_seconds(day_after),
    }


def unix_seconds(value: date) -> int:
    return int(datetime(value.year, value.month, value.day, tzinfo=timezone.utc).timestamp())


def random_suffix() -> str:
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(6))


VALIDATION_PNG = bytes(
    [
        137,
        80,
        78,
        71,
        13,
        10,
        26,
        10,
        0,
        0,
        0,
        13,
        73,
        72,
        68,
        82,
        0,
        0,
        0,
        1,
        0,
        0,
        0,
        1,
        8,
        6,
        0,
        0,
        0,
        31,
        21,
        196,
        137,
        0,
        0,
        0,
        13,
        73,
        68,
        65,
        84,
        120,
        156,
        99,
        248,
        15,
        4,
        0,
        9,
        251,
        3,
        253,
        160,
        94,
        229,
        39,
        0,
        0,
        0,
        0,
        73,
        69,
        78,
        68,
        174,
        66,
        96,
        130,
    ]
)
