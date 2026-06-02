from typing import Any

import httpx


class AsyncNetboxRestClient:
    """
    Async NetBox client.

    Nutzung:
        async with NetboxAsyncClient(endpoint, token) as nb:
            result = await nb.get_site_list()
    """

    def __init__(self, endpoint: str, token: str) -> None:
        self._endpoint = endpoint
        self._token = token
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "NetboxAsyncClient":

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

    async def _fetch_all(self, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """
        Lädt alle Seiten eines NetBox-Listenendpunkts (Pagination).
        path: z.B. "dcim/sites/" (ohne führendes /api/)

        Returns an empty list if nothing was found!
        """
        client = self._get_client()
        results: list[dict[str, Any]] = []
        url: str | None = f"/api/{path}"
        current_params = params or {}

        while url:
            resp = await client.get(url, params=current_params)
            resp.raise_for_status()
            data = resp.json()
            results.extend(data.get("results", []))
            # next enthält die vollständige URL inkl. Query-Parameter
            url = data.get("next")
            # Params nur beim ersten Request setzen; next-URL enthält sie bereits
            current_params = {}

        return results

    async def _delete_id(self, path: str, id: str | int) -> None:
        client = self._get_client()
        url: str = self._fix_path(path)

        resp = await client.delete(url + f"{id}/")
        resp.raise_for_status()
