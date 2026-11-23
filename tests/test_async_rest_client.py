import httpx2
import pytest

from netboxcustom.AsyncNetboxRestClient import AsyncNetboxRestClient
from netboxcustom.exceptions import NetboxCustomConnectionError, NetboxCustomGeneralError, NetboxCustomHttpError


async def _close(client: AsyncNetboxRestClient) -> None:
    if client._client is not None:
        await client._client.aclose()
        client._client = None


async def test_fetch_all_follows_paginated_next_urls() -> None:
    requests: list[httpx2.URL] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request.url)
        offset = request.url.params.get("offset")
        if offset == "1000":
            return httpx2.Response(
                200,
                json={"count": 2, "next": None, "previous": "x", "results": [{"id": 2}]},
            )

        return httpx2.Response(
            200,
            json={
                "count": 2,
                "next": "https://netbox.internal/api/dcim/sites/?limit=1000&offset=1000",
                "previous": None,
                "results": [{"id": 1}],
            },
        )

    client = AsyncNetboxRestClient("https://netbox.example", "token")
    client._client = httpx2.AsyncClient(base_url="https://netbox.example", transport=httpx2.MockTransport(handler))
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
    requests: list[httpx2.URL] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request.url)
        return httpx2.Response(
            200,
            json={"count": 1, "next": None, "previous": None, "results": [{"id": 1}]},
        )

    client = AsyncNetboxRestClient("https://netbox.example", "token")
    client._client = httpx2.AsyncClient(base_url="https://netbox.example", transport=httpx2.MockTransport(handler))
    try:
        result = await client._fetch_all("dcim/sites/", {"limit": 0})
    finally:
        await _close(client)

    assert result == [{"id": 1}]
    assert str(requests[0]) == "https://netbox.example/api/dcim/sites/?limit=0"


async def test_fetch_all_rejects_repeated_next_url() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={
                "count": 2,
                "next": str(request.url),
                "previous": None,
                "results": [{"id": 1}],
            },
        )

    client = AsyncNetboxRestClient("https://netbox.example", "token")
    client._client = httpx2.AsyncClient(base_url="https://netbox.example", transport=httpx2.MockTransport(handler))
    try:
        with pytest.raises(NetboxCustomGeneralError, match="pagination loop"):
            await client._fetch_all("dcim/sites/")
    finally:
        await _close(client)


async def test_fetch_all_error_contains_netbox_response_body() -> None:
    body = {"role": ["Select a valid choice. accessx is not one of the available choices."]}

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(400, json=body)

    client = AsyncNetboxRestClient("https://netbox.example", "token")
    client._client = httpx2.AsyncClient(base_url="https://netbox.example", transport=httpx2.MockTransport(handler))
    try:
        with pytest.raises(NetboxCustomHttpError, match="accessx is not one of the available choices") as exc:
            await client._fetch_all("ipam/prefixes/", {"role": "accessx"})
        assert exc.value.status_code == 400
        assert "role=accessx" in exc.value.url
        assert isinstance(exc.value, NetboxCustomConnectionError)
    finally:
        await _close(client)
