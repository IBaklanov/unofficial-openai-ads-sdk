from __future__ import annotations

from typing import Any, Callable, Dict, Generic, Iterator, TypeVar

T = TypeVar("T")


class Page(Generic[T]):
    def __init__(self, fetch_page: Callable[[Dict[str, Any]], Any], params: Dict[str, Any]) -> None:
        self._fetch_page = fetch_page
        self._params = params

    def get(self) -> Any:
        return self._fetch_page(self._params)

    def auto_paging_iter(self) -> Iterator[T]:
        params = dict(self._params)
        while True:
            page = self._fetch_page(params)
            yield from page.data
            if not page.has_more or not page.last_id:
                break
            params["after"] = page.last_id


class AsyncPage(Generic[T]):
    def __init__(self, fetch_page: Callable[[Dict[str, Any]], Any], params: Dict[str, Any]) -> None:
        self._fetch_page = fetch_page
        self._params = params

    async def get(self) -> Any:
        return await self._fetch_page(self._params)

    async def auto_paging_iter(self):
        params = dict(self._params)
        while True:
            page = await self._fetch_page(params)
            for item in page.data:
                yield item
            if not page.has_more or not page.last_id:
                break
            params["after"] = page.last_id
