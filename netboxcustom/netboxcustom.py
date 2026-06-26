import asyncio
from typing import Any

from .netboxcustom_async import AsyncNetboxCustom, LookupSiteByIp


class NetboxCustom:
    """
    Synchronous wrapper around AsyncNetboxCustom.

    Wraps all async methods automatically via __getattr__.
    A single event loop is kept alive for the lifetime of the context manager
    so the underlying httpx.AsyncClient stays open across method calls.

    Usage:
        with NetboxCustom(endpoint, token) as nb:
            result = nb.get_site_list()
    """

    def __init__(self, endpoint: str, token: str) -> None:
        self._async = AsyncNetboxCustom(endpoint, token)
        self._loop = asyncio.new_event_loop()

    def __enter__(self) -> "NetboxCustom":
        self._loop.run_until_complete(self._async.__aenter__())
        return self

    def __exit__(self, *args: Any) -> None:
        self._loop.run_until_complete(self._async.__aexit__(*args))
        self._loop.close()

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._async, name)
        if asyncio.iscoroutinefunction(attr):

            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                return self._loop.run_until_complete(attr(*args, **kwargs))

            return sync_wrapper
        return attr

    # --- explizite Signaturen für Pylance-Autocomplete ---

    def get_site_list(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self._loop.run_until_complete(self._async.get_site_list(params))

    def lookup_site_by_ip(self, device_ip: str = "0.0.0.0", api_filter: dict[str, Any] | None = None) -> str:
        return self._loop.run_until_complete(self._async.lookup_site_by_ip(device_ip, api_filter))

    def lookup_site_by_ip_full(self, device_ip: str = "0.0.0.0", api_filter: dict[str, Any] | None = None) -> LookupSiteByIp:
        return self._loop.run_until_complete(self._async.lookup_site_by_ip_full(device_ip, api_filter))

    def device_exists_bySerial(self, serial_number: str, device_type: str | None = None) -> dict[str, Any]:
        return self._loop.run_until_complete(self._async.device_exists_bySerial(serial_number, device_type))

    def get_rendered_config_bySerial(self, serial_number: str) -> str:
        return self._loop.run_until_complete(self._async.get_rendered_config_bySerial(serial_number))

    def createDevices(
        self,
        device_info_list: list[dict[str, Any]],
        site_slug: str = "",
        role_slug: str = "",
        device_create_args: dict[str, Any] | None = None,
        create_vc: bool = False,
    ) -> list[dict[str, Any]]:
        return self._loop.run_until_complete(
            self._async.createDevices(device_info_list, site_slug, role_slug, device_create_args, create_vc)
        )

    def lookup_firmware_by_model_type(self, model_type: str, firmware_custom_field: str = "firmware_filename") -> dict[str, Any]:
        return self._loop.run_until_complete(self._async.lookup_firmware_by_model_type(model_type, firmware_custom_field))
