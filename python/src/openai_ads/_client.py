from __future__ import annotations

from typing import Optional

import httpx

from ._http import AsyncHTTP, SyncHTTP
from ._resources import (
    AdAccountResource,
    AdGroups,
    Ads,
    AsyncAdAccountResource,
    AsyncCampaigns,
    AsyncInsights,
    Campaigns,
    Insights,
    Uploads,
)


class OpenAIAds:
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: str = "https://api.ads.openai.com/v1",
        timeout: float = 60.0,
        max_retries: int = 2,
        http_client: Optional[httpx.Client] = None,
        default_headers: Optional[dict[str, str]] = None,
    ) -> None:
        http = SyncHTTP(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            http_client=http_client,
            default_headers=default_headers,
        )
        self.campaigns = Campaigns(http)
        self.ad_groups = AdGroups(http)
        self.ads = Ads(http)
        self.uploads = Uploads(http)
        self.ad_account = AdAccountResource(http)
        self.insights = Insights(http)


class AsyncOpenAIAds:
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: str = "https://api.ads.openai.com/v1",
        timeout: float = 60.0,
        max_retries: int = 2,
        http_client: Optional[httpx.AsyncClient] = None,
        default_headers: Optional[dict[str, str]] = None,
    ) -> None:
        http = AsyncHTTP(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            http_client=http_client,
            default_headers=default_headers,
        )
        self.campaigns = AsyncCampaigns(http)
        self.ad_account = AsyncAdAccountResource(http)
        self.insights = AsyncInsights(http)
