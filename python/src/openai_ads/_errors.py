from __future__ import annotations

from typing import Any, Optional

import httpx


class OpenAIAdsError(Exception):
    pass


class ValidationError(OpenAIAdsError):
    pass


class TimeoutError(OpenAIAdsError):
    pass


class APIError(OpenAIAdsError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        response: httpx.Response,
        body: Any,
        request_id: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response
        self.body = body
        self.request_id = request_id


class AuthenticationError(APIError):
    pass


class RateLimitError(APIError):
    pass
