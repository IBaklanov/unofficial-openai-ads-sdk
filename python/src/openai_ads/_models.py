from __future__ import annotations

from datetime import date
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ResponseModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Budget(RequestModel):
    lifetime_spend_limit_micros: int = Field(ge=1_000_000)

    @model_validator(mode="before")
    @classmethod
    def normalize_budget(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        if "daily_spend_limit_micros" in data:
            raise ValueError("budget.daily_spend_limit_micros is not supported; use lifetime_spend_limit_micros")
        legacy_spend_limit = data.pop("spend_limit_micros", None)
        if "lifetime_spend_limit_micros" not in data and legacy_spend_limit is not None:
            data["lifetime_spend_limit_micros"] = legacy_spend_limit
        elif (
            legacy_spend_limit is not None
            and data.get("lifetime_spend_limit_micros") != legacy_spend_limit
        ):
            raise ValueError("budget.spend_limit_micros must match lifetime_spend_limit_micros when both are provided")
        return data


class TargetingLocations(RequestModel):
    countries: Optional[List[str]] = None


class Targeting(RequestModel):
    locations: Optional[TargetingLocations] = None
    excluded_locations: Optional[TargetingLocations] = None


class Campaign(ResponseModel):
    id: str
    created_at: int
    updated_at: int
    name: str
    description: Optional[str] = None
    status: str
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    budget: Dict[str, Any]
    targeting: Optional[Dict[str, Any]] = None
    bidding_type: Optional[Literal["impressions", "clicks"]] = None
    mode: Optional[str] = None
    conversion_event_setting_ids: Optional[List[str]] = None


class CampaignCreateParams(RequestModel):
    name: str = Field(min_length=3, max_length=1000)
    description: Optional[str] = None
    start_time: Optional[int] = Field(default=None, ge=946684800, le=4102444800)
    end_time: Optional[int] = Field(default=None, ge=946684800, le=4102444800)
    status: Literal["active", "paused"]
    budget: Budget
    targeting: Optional[Targeting] = None
    bidding_type: Optional[Literal["impressions", "clicks"]] = None

    @field_validator("name")
    @classmethod
    def name_has_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must contain a non-space character")
        return value


class CampaignUpdateParams(RequestModel):
    name: Optional[str] = Field(default=None, min_length=3, max_length=1000)
    description: Optional[str] = None
    start_time: Optional[int] = Field(default=None, ge=946684800, le=4102444800)
    end_time: Optional[int] = Field(default=None, ge=946684800, le=4102444800)
    status: Optional[Literal["active", "paused", "archived"]] = None
    budget: Optional[Budget] = None
    targeting: Optional[Targeting] = None


class BiddingConfig(RequestModel):
    billing_event_type: Literal["impression", "click"]
    max_bid_micros: int = Field(ge=1, le=100_000_000)


class AdGroup(ResponseModel):
    id: str
    created_at: int
    updated_at: int
    name: str
    description: Optional[str] = None
    context_hints: Optional[List[str]] = None
    status: str
    bidding_config: Dict[str, Any]


class AdGroupCreateParams(RequestModel):
    campaign_id: str
    name: str = Field(min_length=3, max_length=1000)
    description: Optional[str] = None
    context_hints: Optional[List[str]] = None
    status: Literal["active", "paused"]
    bidding_config: BiddingConfig


class AdGroupUpdateParams(RequestModel):
    name: Optional[str] = Field(default=None, min_length=3, max_length=1000)
    description: Optional[str] = None
    context_hints: Optional[List[str]] = None
    status: Optional[Literal["active", "paused", "archived"]] = None
    bidding_config: Optional[BiddingConfig] = None


class Creative(ResponseModel):
    type: Literal["chat_card"]
    title: str
    body: str
    target_url: Optional[str] = None
    file_id: Optional[str] = None
    image_url: Optional[str] = None


class CreativeParams(RequestModel):
    type: Literal["chat_card"]
    title: str = Field(min_length=3, max_length=50)
    body: str = Field(max_length=100)
    target_url: str
    file_id: str


class UpdateCreativeParams(RequestModel):
    type: Literal["chat_card"]
    title: Optional[str] = Field(default=None, min_length=3, max_length=50)
    body: Optional[str] = Field(default=None, max_length=100)
    target_url: Optional[str] = None
    file_id: Optional[str] = None


class Ad(ResponseModel):
    id: str
    created_at: int
    updated_at: int
    ad_group_id: Optional[str] = None
    name: str
    status: str
    creative: Dict[str, Any]
    review_status: Optional[Literal["in_review", "rejected", "approved"]] = None
    appeal: Optional[Any] = None


class AdCreateParams(RequestModel):
    ad_group_id: str
    name: str = Field(min_length=3, max_length=1000)
    status: Literal["active", "paused"]
    creative: CreativeParams


class AdUpdateParams(RequestModel):
    name: Optional[str] = Field(default=None, min_length=3, max_length=1000)
    status: Optional[Literal["active", "paused", "archived"]] = None
    creative: Optional[UpdateCreativeParams] = None


class UploadParams(RequestModel):
    image_url: Optional[str] = None
    file: Optional[Any] = None

    @model_validator(mode="after")
    def has_source(self) -> "UploadParams":
        if bool(self.image_url) == bool(self.file):
            raise ValueError("Provide exactly one of image_url or file.")
        return self


class Upload(ResponseModel):
    file_id: str


class AdAccount(ResponseModel):
    id: str
    name: Optional[str] = None
    url: Optional[str] = None
    preview_url: Optional[str] = None
    timezone: Optional[str] = None
    currency_code: Optional[str] = None


class DateRange(RequestModel):
    since: str
    until: str

    @model_validator(mode="after")
    def until_is_not_future(self) -> "DateRange":
        try:
            until_date = date.fromisoformat(self.until)
        except ValueError:
            return self
        if until_date > date.today():
            raise ValueError("date_range.until cannot be in the future")
        return self


class InsightsParams(RequestModel):
    time_granularity: Optional[Literal["daily", "none"]] = None
    aggregation_level: Optional[Literal["ad_account", "campaign", "ad_group", "ad"]] = None
    limit: Optional[int] = Field(default=None, ge=1, le=10_000)
    before: Optional[str] = None
    after: Optional[str] = None
    date_range: Optional[DateRange] = None
    fields: Optional[List[str]] = None
    filters: Optional[List[str]] = None
    sort: Optional[List[str]] = None

    @field_validator("fields")
    @classmethod
    def fields_are_dotted(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return value
        for field in value:
            if "." not in field:
                raise ValueError(
                    f'insights field "{field}" is not supported; use dotted fields such as '
                    "ad_group.name or metadata.timezone"
                )
        return value


class Insight(ResponseModel):
    id: Optional[str] = None
    start_time: Optional[Any] = None
    end_time: Optional[Any] = None


T = TypeVar("T")


class ListResponse(ResponseModel, Generic[T]):
    object: str = "list"
    data: List[T]
    first_id: Optional[str] = None
    last_id: Optional[str] = None
    has_more: bool
    count: Optional[int] = None
