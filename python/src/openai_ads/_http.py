from __future__ import annotations

import asyncio
import os
import random
import time
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Mapping, Optional

import httpx
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from ._errors import APIError, AuthenticationError, RateLimitError, TimeoutError, ValidationError

RETRY_STATUSES = {408, 409, 429}


class BaseHTTP:
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: str = "https://api.ads.openai.com/v1",
        timeout: float = 60.0,
        max_retries: int = 2,
        default_headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_ADS_API_KEY")
        if not self.api_key:
            raise ValidationError("OpenAI Ads API key is required. Pass api_key or set OPENAI_ADS_API_KEY.")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.default_headers = dict(default_headers or {})

    def headers(self, idempotency_key: Optional[str] = None) -> Dict[str, str]:
        headers = {**self.default_headers, "authorization": f"Bearer {self.api_key}"}
        if idempotency_key:
            headers["idempotency-key"] = idempotency_key
        return headers

    def url(self, path: str) -> str:
        return f"{self.base_url}{path}"


class SyncHTTP(BaseHTTP):
    def __init__(self, *, http_client: Optional[httpx.Client] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._client = http_client or httpx.Client(timeout=self.timeout)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        data: Any = None,
        json_data: Any = None,
        files: Any = None,
        response_model: Any = None,
        idempotency_key: Optional[str] = None,
        retry_non_idempotent: bool = False,
    ) -> Any:
        can_retry = method == "GET" or retry_non_idempotent or bool(idempotency_key)
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.request(
                    method,
                    self.url(path),
                    params=encode_query_params(params),
                    data=data,
                    json=json_data if files is None else None,
                    files=files,
                    headers=self.headers(idempotency_key),
                    timeout=self.timeout,
                )
            except httpx.TimeoutException as exc:
                if can_retry and attempt < self.max_retries:
                    time.sleep(backoff_seconds(attempt))
                    continue
                raise TimeoutError("OpenAI Ads request timed out") from exc
            if response.is_success:
                return parse_response(response, response_model)
            if should_retry(response.status_code) and can_retry and attempt < self.max_retries:
                time.sleep(retry_after_seconds(response) or backoff_seconds(attempt))
                continue
            raise api_error(response)
        raise RuntimeError("unreachable")


class AsyncHTTP(BaseHTTP):
    def __init__(self, *, http_client: Optional[httpx.AsyncClient] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._client = http_client or httpx.AsyncClient(timeout=self.timeout)

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        data: Any = None,
        json_data: Any = None,
        files: Any = None,
        response_model: Any = None,
        idempotency_key: Optional[str] = None,
        retry_non_idempotent: bool = False,
    ) -> Any:
        can_retry = method == "GET" or retry_non_idempotent or bool(idempotency_key)
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._client.request(
                    method,
                    self.url(path),
                    params=encode_query_params(params),
                    data=data,
                    json=json_data if files is None else None,
                    files=files,
                    headers=self.headers(idempotency_key),
                    timeout=self.timeout,
                )
            except httpx.TimeoutException as exc:
                if can_retry and attempt < self.max_retries:
                    await asyncio.sleep(backoff_seconds(attempt))
                    continue
                raise TimeoutError("OpenAI Ads request timed out") from exc
            if response.is_success:
                return parse_response(response, response_model)
            if should_retry(response.status_code) and can_retry and attempt < self.max_retries:
                await asyncio.sleep(retry_after_seconds(response) or backoff_seconds(attempt))
                continue
            raise api_error(response)
        raise RuntimeError("unreachable")


def dump_model(model: BaseModel) -> Dict[str, Any]:
    return model.model_dump(exclude_unset=True, mode="json")


def encode_query_params(params: Optional[Mapping[str, Any]]) -> Any:
    if not params:
        return None
    encoded = []
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, list):
            encoded.extend((f"{key}[]", item) for item in value)
        else:
            encoded.append((key, value))
    return encoded


def parse_response(response: httpx.Response, response_model: Any) -> Any:
    try:
        data = response.json() if response.content else {}
    except ValueError:
        data = response.text
    if response_model is None:
        return data
    try:
        return response_model.model_validate(data)
    except PydanticValidationError as exc:
        raise ValidationError("OpenAI Ads response failed validation") from exc


def api_error(response: httpx.Response) -> APIError:
    try:
        body = response.json()
    except ValueError:
        body = response.text
    message = extract_message(body) or f"OpenAI Ads API request failed with status {response.status_code}"
    request_id = response.headers.get("x-request-id")
    if response.status_code in (401, 403):
        return AuthenticationError(
            message, status_code=response.status_code, response=response, body=body, request_id=request_id
        )
    if response.status_code == 429:
        return RateLimitError(
            message, status_code=response.status_code, response=response, body=body, request_id=request_id
        )
    return APIError(message, status_code=response.status_code, response=response, body=body, request_id=request_id)


def extract_message(body: Any) -> Optional[str]:
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"]
        if isinstance(body.get("message"), str):
            return body["message"]
    return None


def should_retry(status_code: int) -> bool:
    return status_code in RETRY_STATUSES or status_code >= 500


def retry_after_seconds(response: httpx.Response) -> Optional[float]:
    value = response.headers.get("retry-after")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            return max(0.0, parsedate_to_datetime(value).timestamp() - time.time())
        except (TypeError, ValueError):
            return None


def backoff_seconds(attempt: int) -> float:
    return min(2**attempt, 8) + random.random() * 0.25
