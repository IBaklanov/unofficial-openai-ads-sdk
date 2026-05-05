# Unofficial OpenAI Ads SDK

Unofficial TypeScript SDK for the OpenAI Ads Advertiser API.

This package is not created, sponsored, or endorsed by OpenAI.

```sh
npm install unofficial-openai-ads-sdk
```

```ts
import { OpenAIAds } from "unofficial-openai-ads-sdk";

const ads = new OpenAIAds({ apiKey: process.env.OPENAI_ADS_API_KEY });

const campaign = await ads.campaigns.create({
  name: "Spring launch",
  status: "paused",
  budget: { lifetime_spend_limit_micros: 100_000_000 },
  targeting: { locations: { countries: ["US"] } },
  bidding_type: "clicks",
});

console.log(campaign.id);
```

Official API docs: https://developers.openai.com/ads/api-overview

Source: https://github.com/IBaklanov/unofficial-openai-ads-sdk
