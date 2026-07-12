import re
from dataclasses import dataclass
from typing import Any

import httpx

from .AsyncNetboxRestClient import AsyncNetboxRestClient
from .data import ScopeType, device_default_names
from .exceptions import (
    NetboxCustomCreateDeviceError,
    NetboxCustomFieldMissing,
    NetboxCustomGeneralError,
    NetboxCustomLookupError,
    NetboxCustomNotFoundError,
    NetboxScopeTypeNotFound,
)
from .helper import build_stack_hostname, has_object_scope


@dataclass
class DeviceType:
    device_type: str
    firmware_custom_field: str
    firmware_filename: str = ""
    platform: str = ""
    flash: str = ""
    error: str = ""


@dataclass
class LookupSiteByIp:
    site_slug: str
    api_filter: dict[str, Any]
    subnet: str


class AsyncNetboxCustom(AsyncNetboxRestClient):
    async def _device_delete_all_ips(self, device: dict[str, Any], interface_name: str | None = "vlan1") -> None:
        """Deletes all primary ipv4 and ipv6 IPs and checks vlan1 if an IP is attached."""

        if device.get("primary_ip4"):
            ip_id = device["primary_ip4"]["id"]
            await self._delete_id("ipam/ip-addresses", ip_id)

        if device.get("primary_ip6"):
            ip_id = device["primary_ip6"]["id"]
            await self._delete_id("ipam/ip-addresses", ip_id)

        if interface_name is not None:
            interfaces = await self._fetch_all(
                "dcim/interfaces/",
                {"device_id": device["id"], "name": interface_name},
            )
            for iface in interfaces:
                ip_list = await self._fetch_all("ipam/ip-addresses/", {"interface_id": iface["id"]})
                for ip in ip_list:
                    await self._delete_id("ipam/ip-addresses", ip["id"])

    async def _create_vc_from_device_list(self, device_obj_list: list[dict[str, Any]], site_id: int) -> None:
        """
        Erstellt ein Virtual Chassis aus einer Device-Liste.
        Wenn VC_Position und VC_Priority nicht gesetzt sind, dann werden sie erzeugt.
        """
        try:
            vc_name = device_obj_list[0]["name"]
            resp = await self._post(
                "dcim/virtual-chassis/",
                json={
                    "name": vc_name,
                    "site": site_id,
                    "master": device_obj_list[0]["id"],
                },
            )
            resp.raise_for_status()
            vc = resp.json()

            priority = 15
            for cnt, device in enumerate(device_obj_list, 1):
                patch: dict[str, Any] = {"virtual_chassis": vc["id"]}
                if not device.get("vc_position"):
                    patch["vc_position"] = cnt
                if not device.get("vc_priority"):
                    patch["vc_priority"] = priority
                    priority = priority - 1

                resp = await self._patch(f"dcim/devices/{device['id']}", json=patch)
                resp.raise_for_status()

        except httpx.HTTPStatusError as e:
            raise NetboxCustomCreateDeviceError(f"VC creation error: {e.response.text}")

    # ------------------------------------------------------------------
    # Sites
    # ------------------------------------------------------------------

    async def get_site_list(
        self,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        params: e.g.
            sites = await nb.get_site_list({"slug": "bonn"})
            sites = await nb.get_site_list({"tenant": "mycompany"})
        """
        raw_sites = await self._fetch_all("dcim/sites/", params)

        result_list: list[dict[str, Any]] = []
        for site in raw_sites:
            d: dict[str, Any] = {
                "id": site["id"],
                "name": site["name"],
                "slug": site["slug"],
                "gns": "tbc",
                "description": site.get("description", ""),
                "display": site.get("display", ""),
            }
            cf = site.get("custom_fields", {})
            if "GNS" in cf:
                d["gns"] = cf["GNS"] or "tbc"
            d["long"] = d["gns"] + "-" + site["slug"]
            result_list.append(d)

        return result_list

    # ------------------------------------------------------------------
    # IP / Prefix → Site
    # ------------------------------------------------------------------

    async def lookup_site_by_ip(
        self,
        device_ip: str = "0.0.0.0",
        api_filter: dict[str, Any] | None = None,
    ) -> str:
        """
        example:
            sites = await nb.lookup_site_by_ip(
            "192.168.178.4", {"role": "network-management"}
        )
        """
        params: dict[str, Any] = {"contains": device_ip}
        if api_filter:
            params.update(api_filter)

        prefix_list = await self._fetch_all("ipam/prefixes/", params)

        # get prefix with biggest match
        if len(prefix_list) >= 1:
            network = prefix_list[-1]

            if has_object_scope(network, ScopeType.SITE):
                return network["scope"]["slug"]
            else:
                raise NetboxScopeTypeNotFound(
                    f"{network.get('prefix', '')} has no netbox ScopeType.SITE '{ScopeType.SITE}' assigned!"
                )
        else:
            raise NetboxCustomLookupError(f"No network found! Adjust api_filter! {str(api_filter)}")

    async def lookup_site_by_ip_full(
        self,
        device_ip: str = "0.0.0.0",
        api_filter: dict[str, Any] | None = None,
    ) -> LookupSiteByIp:
        """
        example:
            sites = await nb.lookup_site_by_ip_full(
            "192.168.178.4", {"role": "network-management"}
        )
        """
        params: dict[str, Any] = {"contains": device_ip}
        if api_filter:
            params.update(api_filter)

        prefix_list = await self._fetch_all("ipam/prefixes/", params)

        # get prefix with biggest match
        if len(prefix_list) >= 1:
            network = prefix_list[-1]

            if has_object_scope(network, ScopeType.SITE):
                return LookupSiteByIp(
                    site_slug=network["scope"]["slug"],
                    api_filter=api_filter or {},
                    subnet=network["prefix"],
                )
            else:
                raise NetboxScopeTypeNotFound(
                    f"{network.get('prefix', '')} has no netbox ScopeType.SITE '{ScopeType.SITE}' assigned!"
                )
        else:
            raise NetboxCustomLookupError(f"No network found! Adjust api_filter! {str(api_filter)}")

    # ------------------------------------------------------------------
    # Devices
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Devices
    # ------------------------------------------------------------------

    async def device_exists_bySerial(
        self,
        serial_number: str,
        device_type: str | None = None,
    ) -> dict[str, Any]:
        try:
            devices = await self._fetch_all("dcim/devices/", {"serial": serial_number})
        except Exception as e:
            raise NetboxCustomLookupError(f"[device_exists by Serial] {e}")

        if len(devices) > 1:
            raise NetboxCustomLookupError(f"[device_exists by Serial] More than one device found for serial {serial_number}!")

        if len(devices) == 0:
            raise NetboxCustomNotFoundError(f"Serial {serial_number} not found in Netbox!")

        device = devices[0]

        if device_type:
            if device["device_type"]["model"] == device_type:
                return device
            else:
                raise NetboxCustomNotFoundError(
                    f"[device_exists_bySerial] Serial number exists, but device type doesn't match! "
                    f"device:{device_type} netbox:{device['device_type']['model']}."
                )

        return device

    async def get_rendered_config_bySerial(self, serial_number: str) -> str:
        device = await self.device_exists_bySerial(serial_number)
        try:
            resp = await self._post(f"dcim/devices/{device['id']}/render-config")
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise NetboxCustomLookupError(str(e))

        data = resp.json()
        if "content" in data:
            return data["content"]
        else:
            raise NetboxCustomLookupError("No content found in netbox answer [get_rendered_config_bySerial]")

    async def createDevices(
        self,
        device_info_list: list[dict[str, Any]],
        site_slug: str = "",
        role_slug: str = "",
        device_create_args: dict[str, Any] | None = None,
        create_vc: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Erzeugt Devices in NetBox; bei >1 Device wird optional ein VC angelegt.

        If a device is already part of a VC, the VC will be deleted, but not the device itself.

        All existing IPs of a device are getting removed!
        """
        # if device_info_list is None:
        #     device_info_list = []
        if device_create_args is None:
            device_create_args = {}

        sites = await self._fetch_all("dcim/sites/", {"slug": site_slug})
        if not sites:
            raise NetboxCustomCreateDeviceError(f'site_slug "{site_slug}" not found in netbox.')
        site = sites[0]

        roles = await self._fetch_all("dcim/device-roles/", {"slug": role_slug})
        if not roles:
            raise NetboxCustomCreateDeviceError(f'role_slug "{role_slug}" not found in netbox.')
        role = roles[0]

        # make sure list is not longer than 15
        if len(device_info_list) > 15:
            raise NetboxCustomGeneralError("List of devices is >15, something is probably wrong!")

        # build and cleanup [list] of dict(s) to create the device(s)
        priority = 15
        for index, dev in enumerate(device_info_list, 1):
            # check for default names!
            if dev["name"] in device_default_names:
                dev["name"] = f"{dev['name']}-{dev['serial']}"

            # add create_args
            dev.update(device_create_args)

            # mandatory parameters
            dev["role"] = role["id"]
            dev["site"] = site["id"]

            if len(device_info_list) > 1:
                if "slot" in dev:
                    dev["vc_position"] = dev["slot"]
                else:
                    dev["vc_position"] = f"{index}"

                if "priority" in dev:
                    dev["vc_priority"] = f"{dev['priority']}"
                else:
                    dev["vc_priority"] = f"{priority}"
                    priority = priority - 1

        device_info_list = build_stack_hostname(device_info_list[0]["name"], device_info_list)

        # contains the created devices
        device_obj_list: list[dict[str, Any]] = []

        for dev in device_info_list:
            found: dict[str, Any] | None = None

            try:
                found = await self.device_exists_bySerial(dev["serial"], device_type=dev["device_type"])
                await self._device_delete_all_ips(found)
                device_obj_list.append(found)

                # device was found, and it is part of a VC, delete the VC, but not the device, it can be used later to
                # build a new VC
                if found.get("virtual_chassis"):
                    vc_id = found["virtual_chassis"]["id"]
                    # await client.delete(f"/api/dcim/virtual-chassis/{vc_id}/")
                    await self._delete_id("dcim/virtual-chassis", vc_id)
            except NetboxCustomNotFoundError:
                pass

            # check if needed device_types exits
            device_types = await self._fetch_all("dcim/device-types/", {"model": dev["device_type"]})
            if not device_types:
                raise NetboxCustomCreateDeviceError(
                    f'Device_Type "{dev["device_type"]}" not found in netbox, please create it before using it.'
                )
            dev["device_type"] = device_types[0]["id"]

            # since device was not found it can be created
            if not found:
                try:
                    resp = await self._post("dcim/devices/", json=dev)
                    resp.raise_for_status()
                    device_obj_list.append(resp.json())
                except httpx.HTTPStatusError as e:
                    raise NetboxCustomCreateDeviceError(f"Netbox error: {e.response.text}")

        if len(device_obj_list) > 1 and create_vc:
            await self._create_vc_from_device_list(device_obj_list, site_id=site["id"])

        return device_obj_list

    # ------------------------------------------------------------------
    # Firmware
    # ------------------------------------------------------------------

    async def lookup_firmware_by_model_type(
        self,
        device_type: str,
        firmware_custom_field: str = "firmware_filename",
    ) -> DeviceType:

        ret = DeviceType(device_type=device_type, firmware_custom_field=firmware_custom_field)

        models = []

        try:
            models = await self._fetch_all("dcim/device-types/", {"model": device_type})
        except Exception as e:
            raise NetboxCustomLookupError(f"firmware_lookup {e}")

        if len(models) == 0:
            raise NetboxCustomLookupError(f"Device type '{device_type}' not found!")
        if len(models) > 1:
            raise NetboxCustomLookupError(f"Multiple device types found for model '{device_type}'!")

        model = models[0]
        cf = model.get("custom_fields", {})

        if firmware_custom_field in cf:
            ret.firmware_filename = cf[firmware_custom_field]
        else:
            raise NetboxCustomFieldMissing(f"Custom field 'firmware_filename' on device_type {device_type} not found!")

        # if default_plaform is found it might be None
        platform_obj: dict[str, Any] | None = model.get("default_platform", None)

        if isinstance(platform_obj, dict):
            ret.platform = (platform_obj.get("name") or "").upper()
        else:
            ret.platform = ""

        if not ret.platform:
            if re.match(r"(C9200|C9300|C940|WS\-C3850)", ret.device_type, flags=re.IGNORECASE):
                ret.platform = "IOS-XE"
            if re.match(r"(WS\-C2960|WS\-C3750|WS\-C6500)", ret.device_type, flags=re.IGNORECASE):
                ret.platform = "IOS"

        if ret.platform == "IOS-XE":
            ret.flash = "bootflash:"
        elif ret.platform == "IOS":
            ret.flash = "flash:"

        return ret

    async def lookup_firmware_list(
        self, model_types: list[str], firmware_custom_field: str = "firmware_filename"
    ) -> list[DeviceType]:

        ret: list[DeviceType] = []

        for model_type in model_types:
            try:
                r = await self.lookup_firmware_by_model_type(model_type, firmware_custom_field)
                ret.append(r)
            except (NetboxCustomLookupError, NetboxCustomFieldMissing) as e:
                ret.append(
                    DeviceType(
                        device_type=model_type,
                        firmware_custom_field=firmware_custom_field,
                        error=str(e),
                    )
                )

        return ret


if __name__ == "__main__":
    pass
