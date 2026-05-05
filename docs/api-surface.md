# API Surface

This SDK tracks the public OpenAI Ads Advertiser API and keeps a small SDK compatibility contract for behavior covered by tests.

## Contract Files

- `contracts/openai-ads-public-openapi.json`: current public OpenAPI snapshot from the OpenAI Ads docs.
- `contracts/openai-ads-contract.json`: SDK contract used by tests. It starts from the public OpenAPI snapshot and adds SDK compatibility notes for supported behavior.

## Compatibility Notes

- CPM ad groups use `billing_event_type = "impression"`.
- CPC ad groups use `billing_event_type = "click"`.
- CPC campaigns should be created with `bidding_type = "clicks"`.
- Insights helpers accept dotted fields such as `campaign.clicks`, `ad_group.spend`, and `ad.cpc`.
- `creative.image_url` values are response artifacts; persist `file_id` as the durable creative image handle.
