import httpx
import pytest

from netboxcustom.AsyncNetboxRestClient import AsyncNetboxRestClient
from netboxcustom.exceptions import NetboxCustomGeneralError


async def _close(client: AsyncNetboxRestClient) -> None:
    if client._client is not None:
        await client._client.aclose()
        client._client = None


async def test_fetch_all_follows_paginated_next_urls() -> None:
    requests: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url)
        offset = request.url.params.get("offset")
        if offset == "1000":
            return httpx.Response(
                200,
                json={"count": 2, "next": None, "previous": "x", "results": [{"id": 2}]},
            )

        return httpx.Response(
            200,
            json={
                "count": 2,
                "next": "https://netbox.internal/api/dcim/sites/?limit=1000&offset=1000",
                "previous": None,
                "results": [{"id": 1}],
            },
        )

    client = AsyncNetboxRestClient("https://netbox.example", "token")
    client._client = httpx.AsyncClient(base_url="https://netbox.example", transport=httpx.MockTransport(handler))
    try:
        result = await client._fetch_all("dcim/sites/")
    finally:
        await _close(client)

    assert result == [{"id": 1}, {"id": 2}]
    assert [str(request) for request in requests] == [
        "https://netbox.example/api/dcim/sites/?limit=1000",
        "https://netbox.example/api/dcim/sites/?limit=1000&offset=1000",
    ]


async def test_fetch_all_keeps_explicit_limit_zero() -> None:
    requests: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url)
        return httpx.Response(
            200,
            json={"count": 1, "next": None, "previous": None, "results": [{"id": 1}]},
        )

    client = AsyncNetboxRestClient("https://netbox.example", "token")
    client._client = httpx.AsyncClient(base_url="https://netbox.example", transport=httpx.MockTransport(handler))
    try:
        result = await client._fetch_all("dcim/sites/", {"limit": 0})
    finally:
        await _close(client)

    assert result == [{"id": 1}]
    assert str(requests[0]) == "https://netbox.example/api/dcim/sites/?limit=0"


async def test_fetch_all_rejects_repeated_next_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "count": 2,
                "next": str(request.url),
                "previous": None,
                "results": [{"id": 1}],
            },
        )

    client = AsyncNetboxRestClient("https://netbox.example", "token")
    client._client = httpx.AsyncClient(base_url="https://netbox.example", transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(NetboxCustomGeneralError, match="pagination loop"):
            await client._fetch_all("dcim/sites/")
    finally:
        await _close(client)
