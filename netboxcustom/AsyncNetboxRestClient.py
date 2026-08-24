from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from .exceptions import NetboxCustomConnectionError, NetboxCustomGeneralError


class AsyncNetboxRestClient:
    """
    Async NetBox client.

    Nutzung:
        async with AsyncNetboxRestClient(endpoint, token) as nb:
            result = await nb.get_site_list()
    """

    def __init__(self, endpoint: str, token: str) -> None:
        self._endpoint = endpoint
        self._token = token
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "AsyncNetboxRestClient":

        token_type = "Bearer" if self._token.startswith("nbt_") else "Token"

        self._client = httpx.AsyncClient(
            base_url=self._endpoint.rstrip("/"),
            headers={
                "Authorization": f"{token_type} {self._token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("'async with NetboxAsyncClient(…)' muss vor der Verwendung aufgerufen werden.")
        return self._client

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _fix_path(self, path: str) -> str:
        """
        Fixes / in the path
        """
        # remove / at the start and make sure an there is an / at the end
        path = "/api/" + path.strip("/") + "/"

        return path

    def _relative_url(self, url: str) -> str:
        """
        NetBox returns absolute URLs in pagination links. Keep following them
        through the configured base_url instead of switching to the URL host.
        """
        parts = urlsplit(url)
        if parts.scheme and parts.netloc:
            return urlunsplit(("", "", parts.path, parts.query, parts.fragment))
        return url

    async def _fetch_all(self, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """
        Lädt alle Seiten eines NetBox-Listenendpunkts (Pagination).
        path: z.B. "dcim/sites/" (ohne führendes /api/)

        Returns an empty list if nothing was found!
        """
        client = self._get_client()
        results: list[dict[str, Any]] = []
        url: str | None = self._fix_path(path)
        current_params: dict[str, Any] | None = dict(params or {})
        current_params.setdefault("limit", 1000)
        seen_urls: set[str] = set()

        while url:
            url = self._relative_url(url)
            request_url = str(client.build_request("GET", url, params=current_params).url)
            if request_url in seen_urls:
                raise NetboxCustomGeneralError(f"NetBox pagination loop detected for {request_url}")
            seen_urls.add(request_url)

            try:
                resp = await client.get(url, params=current_params)
            except httpx.TransportError as e:
                raise NetboxCustomConnectionError(message=str(e))

            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise NetboxCustomConnectionError(message=str(e))

            data = resp.json()
            results.extend(data.get("results", []))
            # next enthält die vollständige URL inkl. Query-Parameter
            url = data.get("next")
            # Params nur beim ersten Request setzen; next-URL enthält sie bereits
            current_params = None

        return results

    async def _delete_id(self, path: str, id: str | int) -> None:
        client = self._get_client()
        url: str = self._fix_path(path)

        try:
            resp = await client.delete(url + f"{id}/")
        except httpx.TransportError as e:
            raise NetboxCustomConnectionError(message=str(e))

        resp.raise_for_status()

    async def _patch(self, path: str, json: dict | None = None) -> httpx.Response:
        client = self._get_client()
        url = self._fix_path(path)
        try:
            resp = await client.patch(url, json=json)
        except httpx.TransportError as e:
            raise NetboxCustomConnectionError(message=str(e))
        return resp

    async def _post(self, path: str, json: dict | None = None) -> httpx.Response:
        client = self._get_client()
        url = self._fix_path(path)
        try:
            resp = await client.post(url, json=json)
        except httpx.TransportError as e:
            raise NetboxCustomConnectionError(message=str(e))
        return resp
