from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_current_path_surface_is_vendored():
    contract = json.loads((ROOT / "contracts/openai-ads-contract.json").read_text())
    assert sorted(contract["paths"]) == [
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
    ]


def test_contract_captures_cpc_and_dotted_insights_behavior():
    contract = json.loads((ROOT / "contracts/openai-ads-contract.json").read_text())
    compatibility = contract["x-unofficial-sdk-compatibility"]
    assert "click" in compatibility["billing_event_types"]
    assert "clicks" in compatibility["campaign_bidding_types"]
    assert "bidding_type" in compatibility["campaign_create_fields"]
    assert "ad.cpc" in compatibility["insights_fields"]["ad"]
    assert "conversion_event_setting_ids" in compatibility["observed_response_fields"]["campaign"]
    assert compatibility["insights_date_windows"]["future_until_rejected"] is True
    assert "ad_group_name" in compatibility["insights_field_validation"]["rejected_examples"]
    assert compatibility["insights_field_validation"]["accepted_replacements"]["timezone"] == "metadata.timezone"
    assert "budget.daily_spend_limit_micros" in compatibility["budget_fields"]["unsupported_create_update_fields"]
    assert compatibility["cpc"]["net_new_campaigns_only"] is True
