import { OpenAIAds } from "unofficial-openai-ads-sdk";

const ads = new OpenAIAds({ apiKey: process.env.OPENAI_ADS_API_KEY });

const insights = await ads.insights.adAccount({
  aggregationLevel: "ad",
  timeGranularity: "daily",
  dateRange: { since: "2026-05-01", until: "2026-05-05" },
  fields: ["ad.id", "ad.name", "ad.clicks", "ad.impressions", "ad.cpc"],
});

console.log(insights.data);
