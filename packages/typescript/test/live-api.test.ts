import { describe, expect, it } from "vitest";
import { OpenAIAds } from "../src/index.js";

const runLive = Boolean(process.env.OPENAI_ADS_API_KEY);
const runMutatingLive = runLive && process.env.OPENAI_ADS_LIVE_MUTATE === "1";

describe.skipIf(!runLive)("OpenAI Ads live read-only integration", () => {
  it("retrieves account and lists campaigns", async () => {
    const client = new OpenAIAds();
    expect((await client.adAccount.retrieve()).id).toBeTruthy();
    expect(Array.isArray((await client.campaigns.list({ limit: 1 })).data)).toBe(true);
  });
});

describe.skipIf(!runMutatingLive)("OpenAI Ads live mutating integration", () => {
  it.each([
    ["cpm", "impression", 60_000],
    ["cpc", "click", 3_000_000],
  ] as const)("validates the %s lifecycle and archives disposable objects", async (label, billingEventType, maxBidMicros) => {
    const client = new OpenAIAds();
    const suffix = `sdk-validation-${label}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const created: { campaignId?: string; adGroupId?: string; adId?: string } = {};
    try {
      const campaign = await client.campaigns.create({
        name: `SDK validation campaign ${suffix}`,
        description: `Disposable SDK validation campaign ${suffix}`,
        status: "paused",
        start_time: unixDaysFromNow(1),
        end_time: unixDaysFromNow(2),
        budget: { lifetime_spend_limit_micros: 1_000_000 },
        targeting: { locations: { countries: ["US"] } },
        bidding_type: billingEventType === "click" ? "clicks" : "impressions",
      });
      created.campaignId = campaign.id;
      await client.campaigns.update(campaign.id, { description: `Updated disposable SDK validation campaign ${suffix}`, status: "paused" });

      const adGroup = await client.adGroups.create({
        campaign_id: campaign.id,
        name: `SDK validation ${label} ad group ${suffix}`,
        status: "paused",
        context_hints: ["sdk validation", label, suffix],
        bidding_config: { billing_event_type: billingEventType, max_bid_micros: maxBidMicros },
      });
      created.adGroupId = adGroup.id;
      await client.adGroups.update(adGroup.id, { context_hints: ["sdk validation", "updated", label, suffix], status: "paused", bidding_config: { billing_event_type: billingEventType, max_bid_micros: maxBidMicros } });

      const upload = await client.uploads.create({ file: validationPngBlob() });
      const ad = await client.ads.create({
        ad_group_id: adGroup.id,
        name: `SDK validation ad ${suffix}`,
        status: "paused",
        creative: { type: "chat_card", title: "SDK validation", body: "Disposable SDK validation creative.", target_url: "https://example.com/workspace-planner", file_id: upload.file_id },
      });
      created.adId = ad.id;
      await client.ads.update(ad.id, { name: `SDK validation ad updated ${suffix}`, status: "paused", creative: { type: "chat_card", title: "Validation v2", body: "Updated disposable validation creative.", target_url: "https://example.com/workspace-planner", file_id: upload.file_id } });

      const dateRange = { since: isoDaysFromNow(-2), until: isoDaysFromNow(-1) };
      const fields = ["ad.id", "ad.clicks", "ad.impressions"];
      await expect(client.insights.adAccount({ aggregationLevel: "ad", timeGranularity: "none", limit: 1, dateRange, fields })).resolves.toMatchObject({ data: expect.any(Array) });
      await expect(client.insights.campaign(campaign.id, { aggregationLevel: "ad", timeGranularity: "none", limit: 1, dateRange, fields })).resolves.toMatchObject({ data: expect.any(Array) });
      await expect(client.insights.adGroup(adGroup.id, { aggregationLevel: "ad", timeGranularity: "none", limit: 1, dateRange, fields })).resolves.toMatchObject({ data: expect.any(Array) });
      await expect(client.insights.ad(ad.id, { aggregationLevel: "ad", timeGranularity: "none", limit: 1, dateRange, fields })).resolves.toMatchObject({ data: expect.any(Array) });

      expect((await client.ads.retrieve(ad.id)).status).toBeTruthy();
      expect((await client.adGroups.retrieve(adGroup.id)).status).toBeTruthy();
      expect((await client.campaigns.retrieve(campaign.id)).status).toBeTruthy();
    } finally {
      if (created.adId) await client.ads.archive(created.adId).catch(() => undefined);
      if (created.adGroupId) await client.adGroups.archive(created.adGroupId).catch(() => undefined);
      if (created.campaignId) await client.campaigns.archive(created.campaignId).catch(() => undefined);
    }
  }, 120_000);
});

function isoDaysFromNow(days: number): string {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}
function unixDaysFromNow(days: number): number {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() + days);
  return Math.floor(date.getTime() / 1000);
}
function validationPngBlob(): Blob {
  return new Blob([Uint8Array.from([137,80,78,71,13,10,26,10,0,0,0,13,73,72,68,82,0,0,0,1,0,0,0,1,8,6,0,0,0,31,21,196,137,0,0,0,13,73,68,65,84,120,156,99,248,15,4,0,9,251,3,253,160,94,229,39,0,0,0,0,73,69,78,68,174,66,96,130])], { type: "image/png" });
}
