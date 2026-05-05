import os

from openai_ads import OpenAIAds

client = OpenAIAds(api_key=os.environ["OPENAI_ADS_API_KEY"])

campaign = client.campaigns.create(
    name="Spring launch",
    status="paused",
    budget={"lifetime_spend_limit_micros": 100_000_000},
    targeting={"locations": {"countries": ["US"]}},
    bidding_type="clicks",
)

ad_group = client.ad_groups.create(
    campaign_id=campaign.id,
    name="Prospecting ad group",
    status="paused",
    bidding_config={"billing_event_type": "click", "max_bid_micros": 3_000_000},
)

print(ad_group.id)
