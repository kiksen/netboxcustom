import asyncio
from collections.abc import Sequence
from typing import Any, Literal

from .models import DeviceInfo, DeviceType, LookupSiteByIp, VirtualChassis
from .netboxcustom_async import AsyncNetboxCustom


class NetboxCustom:
    """
    Synchronous wrapper around AsyncNetboxCustom.

    Wraps all async methods automatically via __getattr__.
    A single event loop is kept alive for the lifetime of the context manager
    so the underlying httpx2.AsyncClient stays open across method calls.

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

    def get_rendered_config_bySerial(self, serial_number: str, load_vc_master: bool = False) -> str:
        return self._loop.run_until_complete(self._async.get_rendered_config_bySerial(serial_number, load_vc_master))

    def get_vc_members_by_device_id(self, device_id: int) -> VirtualChassis:
        return self._loop.run_until_complete(self._async.get_vc_members_by_device_id(device_id))

    def createDevices(
        self,
        device_info_list: list[dict[str, Any]],
        site_slug: str = "",
        role_slug: str = "",
        device_create_args: dict[str, Any] | None = None,
        create_vc: bool = False,
        default_device_names: None | list[str] = None,
        compare_lowercase: bool = False,
    ) -> list[dict[str, Any]]:
        return self._loop.run_until_complete(
            self._async.createDevices(
                device_info_list,
                site_slug,
                role_slug,
                device_create_args,
                create_vc,
                default_device_names,
                compare_lowercase,
            )
        )

    def createDevicesFromModels(
        self,
        device_info_list: list[DeviceInfo],
        site_slug: str = "",
        role_slug: str = "",
        device_create_args: dict[str, Any] | None = None,
        create_vc: bool = False,
        default_device_names: None | list[str] = None,
        compare_lowercase: bool = False,
    ) -> list[dict[str, Any]]:
        return self._loop.run_until_complete(
            self._async.createDevicesFromModels(
                device_info_list,
                site_slug,
                role_slug,
                device_create_args,
                create_vc,
                default_device_names,
                compare_lowercase,
            )
        )

    def get_device_type(
        self,
        device_type: str,
        firmware_custom_field: str = "firmware_filename",
        version_custom_field: str | None = None,
        search_from: Literal["model", "part_number", "slug"] | Sequence[Literal["model", "part_number", "slug"]] = "model",
        ignore_case: bool = False,
    ) -> DeviceType:
        return self._loop.run_until_complete(
            self._async.get_device_type(
                device_type, firmware_custom_field, version_custom_field, search_from, ignore_case
            )
        )

    def get_device_types(
        self,
        api_filter: dict[str, Any] | None = None,
        firmware_custom_field: str = "firmware_filename",
        version_custom_field: str | None = None,
    ) -> list[DeviceType]:
        return self._loop.run_until_complete(
            self._async.get_device_types(api_filter, firmware_custom_field, version_custom_field)
        )

    def get_device_types_by_names(
        self,
        device_types: list[str],
        firmware_custom_field: str = "firmware_filename",
        version_custom_field: str | None = None,
    ) -> list[DeviceType]:
        return self._loop.run_until_complete(
            self._async.get_device_types_by_names(device_types, firmware_custom_field, version_custom_field)
        )
