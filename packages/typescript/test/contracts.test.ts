import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const root = resolve(import.meta.dirname, "../../..");

describe("OpenAI Ads public contract", () => {
  it("keeps the current path surface vendored", () => {
    const contract = JSON.parse(readFileSync(resolve(root, "contracts/openai-ads-contract.json"), "utf8"));
    expect(Object.keys(contract.paths).sort()).toEqual([
      "/ad_account",
      "/ad_account/insights",
      "/ad_groups",
      "/ad_groups/{ad_group_id}",
      "/ad_groups/{ad_group_id}/activate",
      "/ad_groups/{ad_group_id}/archive",
      "/ad_groups/{ad_group_id}/insights",
      "/ad_groups/{ad_group_id}/pause",
      "/ads",
      "/ads/{ad_id}",
      "/ads/{ad_id}/activate",
      "/ads/{ad_id}/archive",
      "/ads/{ad_id}/insights",
      "/ads/{ad_id}/pause",
      "/campaigns",
      "/campaigns/{campaign_id}",
      "/campaigns/{campaign_id}/activate",
      "/campaigns/{campaign_id}/archive",
      "/campaigns/{campaign_id}/insights",
      "/campaigns/{campaign_id}/pause",
      "/upload",
    ]);
  });

  it("captures SDK CPC and dotted insights compatibility behavior", () => {
    const contract = JSON.parse(readFileSync(resolve(root, "contracts/openai-ads-contract.json"), "utf8"));
    const compatibility = contract["x-unofficial-sdk-compatibility"];
    expect(compatibility.billing_event_types).toContain("click");
    expect(compatibility.campaign_bidding_types).toContain("clicks");
    expect(compatibility.campaign_create_fields).toContain("bidding_type");
    expect(compatibility.insights_fields.ad).toContain("ad.cpc");
    expect(compatibility.observed_response_fields.campaign).toContain("conversion_event_setting_ids");
  });
});
