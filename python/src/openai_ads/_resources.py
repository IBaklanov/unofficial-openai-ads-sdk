from __future__ import annotations

import json
from typing import Any, Dict, Optional, Type, TypeVar

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from ._errors import ValidationError
from ._http import AsyncHTTP, SyncHTTP, dump_model
from ._models import (
    Ad,
    AdAccount,
    AdCreateParams,
    AdGroup,
    AdGroupCreateParams,
    AdGroupUpdateParams,
    AdUpdateParams,
    Campaign,
    CampaignCreateParams,
    CampaignUpdateParams,
    Insight,
    InsightsParams,
    ListResponse,
    Upload,
    UploadParams,
)
from ._pagination import AsyncPage, Page

ModelT = TypeVar("ModelT", bound=BaseModel)


def validate(model: Type[ModelT], values: Dict[str, Any]) -> ModelT:
    try:
        return model.model_validate(values)
    except PydanticValidationError as exc:
        raise ValidationError("OpenAI Ads request failed validation") from exc


def list_params(
    limit: Optional[int], after: Optional[str], before: Optional[str], order: Optional[str]
) -> Dict[str, Any]:
    return {
        k: v for k, v in {"limit": limit, "after": after, "before": before, "order": order}.items() if v is not None
    }


def insight_query(params: Dict[str, Any]) -> Dict[str, Any]:
    parsed = dump_model(validate(InsightsParams, params))
    date_range = parsed.pop("date_range", None)
    if date_range:
        parsed["time_ranges"] = [json.dumps({"type": "date_range", **date_range})]
    return parsed


class Campaigns:
    def __init__(self, http: SyncHTTP):
        self._http = http

    def list(
        self,
        *,
        limit: Optional[int] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        order: Optional[str] = None,
    ) -> Page[Campaign]:
        params = list_params(limit, after, before, order)
        return Page(
            lambda page_params: self._http.request(
                "GET", "/campaigns", params=page_params, response_model=ListResponse[Campaign]
            ),
            params,
        )

    def create(self, **params: Any) -> Campaign:
        return self._http.request(
            "POST", "/campaigns", json_data=dump_model(validate(CampaignCreateParams, params)), response_model=Campaign
        )

    def retrieve(self, campaign_id: str) -> Campaign:
        return self._http.request("GET", f"/campaigns/{campaign_id}", response_model=Campaign)

    def update(self, campaign_id: str, **params: Any) -> Campaign:
        return self._http.request(
            "POST",
            f"/campaigns/{campaign_id}",
            json_data=dump_model(validate(CampaignUpdateParams, params)),
            response_model=Campaign,
        )

    def activate(self, campaign_id: str) -> Campaign:
        return self._action(campaign_id, "activate")

    def pause(self, campaign_id: str) -> Campaign:
        return self._action(campaign_id, "pause")

    def archive(self, campaign_id: str) -> Campaign:
        return self._action(campaign_id, "archive")

    def _action(self, campaign_id: str, action: str) -> Campaign:
        return self._http.request("POST", f"/campaigns/{campaign_id}/{action}", response_model=Campaign)


class AdGroups:
    def __init__(self, http: SyncHTTP):
        self._http = http

    def list(
        self,
        *,
        campaign_id: str,
        limit: Optional[int] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        order: Optional[str] = None,
    ) -> Page[AdGroup]:
        params = {"campaign_id": campaign_id, **list_params(limit, after, before, order)}
        return Page(
            lambda page_params: self._http.request(
                "GET", "/ad_groups", params=page_params, response_model=ListResponse[AdGroup]
            ),
            params,
        )

    def create(self, **params: Any) -> AdGroup:
        return self._http.request(
            "POST", "/ad_groups", json_data=dump_model(validate(AdGroupCreateParams, params)), response_model=AdGroup
        )

    def retrieve(self, ad_group_id: str) -> AdGroup:
        return self._http.request("GET", f"/ad_groups/{ad_group_id}", response_model=AdGroup)

    def update(self, ad_group_id: str, **params: Any) -> AdGroup:
        return self._http.request(
            "POST",
            f"/ad_groups/{ad_group_id}",
            json_data=dump_model(validate(AdGroupUpdateParams, params)),
            response_model=AdGroup,
        )

    def activate(self, ad_group_id: str) -> AdGroup:
        return self._action(ad_group_id, "activate")

    def pause(self, ad_group_id: str) -> AdGroup:
        return self._action(ad_group_id, "pause")

    def archive(self, ad_group_id: str) -> AdGroup:
        return self._action(ad_group_id, "archive")

    def _action(self, ad_group_id: str, action: str) -> AdGroup:
        return self._http.request("POST", f"/ad_groups/{ad_group_id}/{action}", response_model=AdGroup)


class Ads:
    def __init__(self, http: SyncHTTP):
        self._http = http

    def list(
        self,
        *,
        ad_group_id: str,
        limit: Optional[int] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        order: Optional[str] = None,
    ) -> Page[Ad]:
        params = {"ad_group_id": ad_group_id, **list_params(limit, after, before, order)}
        return Page(
            lambda page_params: self._http.request("GET", "/ads", params=page_params, response_model=ListResponse[Ad]),
            params,
        )

    def create(self, **params: Any) -> Ad:
        return self._http.request(
            "POST", "/ads", json_data=dump_model(validate(AdCreateParams, params)), response_model=Ad
        )

    def retrieve(self, ad_id: str) -> Ad:
        return self._http.request("GET", f"/ads/{ad_id}", response_model=Ad)

    def update(self, ad_id: str, **params: Any) -> Ad:
        return self._http.request(
            "POST", f"/ads/{ad_id}", json_data=dump_model(validate(AdUpdateParams, params)), response_model=Ad
        )

    def activate(self, ad_id: str) -> Ad:
        return self._action(ad_id, "activate")

    def pause(self, ad_id: str) -> Ad:
        return self._action(ad_id, "pause")

    def archive(self, ad_id: str) -> Ad:
        return self._action(ad_id, "archive")

    def _action(self, ad_id: str, action: str) -> Ad:
        return self._http.request("POST", f"/ads/{ad_id}/{action}", response_model=Ad)


class Uploads:
    def __init__(self, http: SyncHTTP):
        self._http = http

    def create(self, **params: Any) -> Upload:
        body = validate(UploadParams, params)
        if body.file is not None:
            return self._http.request("POST", "/upload", files={"file": body.file}, response_model=Upload)
        return self._http.request("POST", "/upload", json_data={"image_url": body.image_url}, response_model=Upload)


class AdAccountResource:
    def __init__(self, http: SyncHTTP):
        self._http = http

    def retrieve(self) -> AdAccount:
        return self._http.request("GET", "/ad_account", response_model=AdAccount)


class Insights:
    def __init__(self, http: SyncHTTP):
        self._http = http

    def ad_account(self, **params: Any) -> Page[Insight]:
        return self._list("/ad_account/insights", params)

    def campaign(self, campaign_id: str, **params: Any) -> Page[Insight]:
        return self._list(f"/campaigns/{campaign_id}/insights", params)

    def ad_group(self, ad_group_id: str, **params: Any) -> Page[Insight]:
        return self._list(f"/ad_groups/{ad_group_id}/insights", params)

    def ad(self, ad_id: str, **params: Any) -> Page[Insight]:
        return self._list(f"/ads/{ad_id}/insights", params)

    def _list(self, path: str, params: Dict[str, Any]) -> Page[Insight]:
        query = insight_query(params)
        return Page(
            lambda page_params: self._http.request(
                "GET", path, params=page_params, response_model=ListResponse[Insight]
            ),
            query,
        )


class AsyncCampaigns:
    def __init__(self, http: AsyncHTTP):
        self._http = http

    async def create(self, **params: Any) -> Campaign:
        return await self._http.request(
            "POST", "/campaigns", json_data=dump_model(validate(CampaignCreateParams, params)), response_model=Campaign
        )


class AsyncAdAccountResource:
    def __init__(self, http: AsyncHTTP):
        self._http = http

    async def retrieve(self) -> AdAccount:
        return await self._http.request("GET", "/ad_account", response_model=AdAccount)


class AsyncInsights:
    def __init__(self, http: AsyncHTTP):
        self._http = http

    def ad_account(self, **params: Any) -> AsyncPage[Insight]:
        query = insight_query(params)
        return AsyncPage(
            lambda page_params: self._http.request(
                "GET", "/ad_account/insights", params=page_params, response_model=ListResponse[Insight]
            ),
            query,
        )
