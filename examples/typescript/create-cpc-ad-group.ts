import { OpenAIAds } from "unofficial-openai-ads-sdk";

const ads = new OpenAIAds({ apiKey: process.env.OPENAI_ADS_API_KEY });

const campaign = await ads.campaigns.create({
  name: "Spring launch",
  status: "paused",
  budget: { lifetime_spend_limit_micros: 100_000_000 },
  targeting: { locations: { countries: ["US"] } },
  bidding_type: "clicks",
});

const adGroup = await ads.adGroups.create({
  campaign_id: campaign.id,
  name: "Prospecting ad group",
  status: "paused",
  bidding_config: { billing_event_type: "click", max_bid_micros: 3_000_000 },
});

console.log(adGroup.id);
