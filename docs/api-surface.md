# API Surface

This SDK tracks the public OpenAI Ads Advertiser API and keeps a small SDK compatibility contract for behavior covered by tests.

## Contract Files

- `contracts/openai-ads-public-openapi.json`: current public OpenAPI snapshot from the OpenAI Ads docs.
- `contracts/openai-ads-contract.json`: SDK contract used by tests. It starts from the public OpenAPI snapshot and adds SDK compatibility notes for supported behavior.

## Compatibility Notes

- CPM ad groups use `billing_event_type = "impression"`.
- CPC ad groups use `billing_event_type = "click"`.
- CPC campaigns should be created net-new with `bidding_type = "clicks"`. The SDK does not support converting an existing CPM campaign to CPC in place.
- Insights helpers accept stable dotted id and metric fields such as `campaign.clicks`, `ad_group.spend`, and `ad.cpc`.
- Insights request validation rejects name and timezone fields that are known to break current insight requests, including `ad_group_name`, `ad_group.name`, `ad.name`, `timezone`, and `metadata.timezone`.
- Insights date ranges may include today, but `until` cannot be in the future. Same-day API calls can succeed before same-day rows are available.
- Bulk insights importers should isolate per-scope `404` or persistent `5xx` failures, continue other scopes, and record those failures for follow-up.
- `creative.image_url` values are signed response artifacts; persist `file_id` as the durable creative image handle.
- Campaign create/update sends `budget.lifetime_spend_limit_micros`. The SDK maps legacy `budget.spend_limit_micros` forward and rejects unsupported `budget.daily_spend_limit_micros`.
