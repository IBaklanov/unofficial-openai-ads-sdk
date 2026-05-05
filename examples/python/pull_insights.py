import os

from openai_ads import OpenAIAds

client = OpenAIAds(api_key=os.environ["OPENAI_ADS_API_KEY"])

page = client.insights.ad_account(
    aggregation_level="ad",
    time_granularity="daily",
    date_range={"since": "2026-05-01", "until": "2026-05-05"},
    fields=["ad.id", "ad.name", "ad.clicks", "ad.impressions", "ad.cpc"],
).get()

print(page.data)
