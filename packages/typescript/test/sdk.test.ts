import { describe, expect, it } from "vitest";
import { OpenAIAds, RateLimitError, ValidationError } from "../src/index.js";

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json", ...(init.headers ?? {}) },
    ...init,
  });
}

describe("OpenAIAds TypeScript SDK", () => {
  it("creates campaigns without a campaign id", async () => {
    const requests: { url: string; init: RequestInit }[] = [];
    const client = new OpenAIAds({
      apiKey: "test",
      fetch: async (url, init) => {
        requests.push({ url: String(url), init: init ?? {} });
        return jsonResponse({
          id: "cmpn_1",
          created_at: 1,
          updated_at: 1,
          name: "Campaign",
          status: "paused",
          budget: { lifetime_spend_limit_micros: 1_000_000 },
        });
      },
    });

    const campaign = await client.campaigns.create({
      name: "Campaign",
      status: "paused",
      budget: { lifetime_spend_limit_micros: 1_000_000 },
      bidding_type: "clicks",
    });

    expect(campaign.id).toBe("cmpn_1");
    expect(requests[0].url).toBe("https://api.ads.openai.com/v1/campaigns");
    expect(JSON.parse(String(requests[0].init.body))).not.toHaveProperty("campaign_id");
  });

  it("maps legacy campaign spend limits and rejects unsupported budget/update fields", async () => {
    const requests: { url: string; init: RequestInit }[] = [];
    const client = new OpenAIAds({
      apiKey: "test",
      fetch: async (url, init) => {
        requests.push({ url: String(url), init: init ?? {} });
        return jsonResponse({
          id: "cmpn_1",
          created_at: 1,
          updated_at: 1,
          name: "Campaign",
          status: "paused",
          budget: { lifetime_spend_limit_micros: 1_000_000 },
        });
      },
    });

    await client.campaigns.create({
      name: "Campaign",
      status: "paused",
      budget: { spend_limit_micros: 1_000_000 },
    });

    expect(JSON.parse(String(requests[0].init.body)).budget).toEqual({ lifetime_spend_limit_micros: 1_000_000 });
    expect(() =>
      client.campaigns.create({
        name: "Campaign",
        status: "paused",
        budget: { daily_spend_limit_micros: 1_000_000 } as any,
      }),
    ).toThrow(ValidationError);
    expect(() => client.campaigns.update("cmpn_1", { bidding_type: "clicks" } as any)).toThrow(ValidationError);
  });

  it("creates click ad groups under campaigns", async () => {
    const client = new OpenAIAds({
      apiKey: "test",
      fetch: async () => jsonResponse({
        id: "adgrp_1",
        created_at: 1,
        updated_at: 1,
        name: "Group",
        status: "paused",
        bidding_config: { billing_event_type: "click", max_bid_micros: 3_000_000 },
      }),
    });
    const adGroup = await client.adGroups.create({
      campaign_id: "cmpn_1",
      name: "Group",
      status: "paused",
      bidding_config: { billing_event_type: "click", max_bid_micros: 3_000_000 },
    });
    expect(adGroup.bidding_config.billing_event_type).toBe("click");
  });

  it("encodes insight arrays with bracket query parameters", async () => {
    let captured = "";
    const client = new OpenAIAds({
      apiKey: "test",
      fetch: async (url) => {
        captured = String(url);
        return jsonResponse({ object: "list", data: [], has_more: false });
      },
    });
    await client.insights.ad("ad_1", {
      fields: ["ad.id", "ad.cpc"],
      dateRange: { since: "2026-05-04", until: "2026-05-05" },
    });
    expect(captured).toContain("fields%5B%5D=ad.id");
    expect(captured).toContain("time_ranges%5B%5D=");
  });

  it("retries rate limits and surfaces rate limit errors", async () => {
    let calls = 0;
    const client = new OpenAIAds({
      apiKey: "test",
      maxRetries: 1,
      fetch: async () => {
        calls += 1;
        return jsonResponse({ error: { message: "too many" } }, { status: 429, headers: { "retry-after": "0" } });
      },
    });
    await expect(client.campaigns.list({ limit: 1 })).rejects.toBeInstanceOf(RateLimitError);
    expect(calls).toBe(2);
  });

  it("validates requests strictly", () => {
    const client = new OpenAIAds({ apiKey: "test", fetch: async () => jsonResponse({}) });
    expect(() =>
      client.campaigns.create({
        name: "  ",
        status: "paused",
        budget: { lifetime_spend_limit_micros: 10 },
      }),
    ).toThrow(ValidationError);
  });
});
