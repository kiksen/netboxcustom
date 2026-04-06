import asyncio
import ipaddress
import os
from typing import Any

import httpx
import jmespath

from netboxcustom.netboxcustom import (
    NetboxCustomCreateDeviceError,
    NetboxCustomFieldMissing,
    NetboxCustomLookupError,
    NetboxCustomNotFoundError,
    ScopeType,
    build_stack_hostname,
    device_default_names,
    switch_position,
)

_client: httpx.AsyncClient | None = None


async def nb_login(
    NETBOX_ENDPOINT: str | None = None,
    NETBOX_TOKEN: str | None = None,
) -> httpx.AsyncClient:
    """
    Erstellt einen gepoolten httpx.AsyncClient und speichert ihn als Modul-Variable.
    Muss vor allen anderen async-Funktionen aufgerufen werden.

    Token-Version wird automatisch erkannt:
      - v2 (nbt_<key>.<token>): Authorization: Bearer <token>
      - v1 (plaintext):         Authorization: Token <token>
    """
    global _client

    if NETBOX_ENDPOINT is None:
        NETBOX_ENDPOINT = os.environ.get("NETBOX_ENDPOINT", "")

    if NETBOX_TOKEN is None:
        NETBOX_TOKEN = os.environ.get("NETBOX_TOKEN", "")

    token_type = "Bearer" if NETBOX_TOKEN.startswith("nbt_") else "Token"
    base_url = NETBOX_ENDPOINT.rstrip("/")

    _client = httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": f"{token_type} {NETBOX_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    return _client


def _get_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError(
            "nb_login() muss vor der Verwendung async-Funktionen aufgerufen werden."
        )
    return _client


async def _fetch_all(path: str, params: dict | None = None) -> list[dict]:
    """
    Lädt alle Seiten eines NetBox-Listenendpunkts (Pagination).
    path: z.B. "dcim/sites/" (ohne führendes /api/)
    """
    client = _get_client()
    results: list[dict] = []
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


async def get_site_list(
    site_slug: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Async Version von get_site_list."""
    if not site_slug:
        site_slug = []

    client = _get_client()

    if len(site_slug) == 0:
        raw_sites = await _fetch_all("dcim/sites/")
    else:
        # NetBox akzeptiert mehrfache slug-Parameter
        raw_sites = []
        url: str | None = "/api/dcim/sites/"
        params = [("slug", s) for s in site_slug]
        while url:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            raw_sites.extend(data.get("results", []))
            url = data.get("next")
            params = []

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


async def device_exists_bySerial(
    serial_number: str,
    device_type: str | None = None,
) -> dict[str, Any]:
    """Async Version von device_exists_bySerial. Gibt ein Device-Dict zurück."""
    try:
        devices = await _fetch_all("dcim/devices/", {"serial": serial_number})
    except Exception as e:
        raise NetboxCustomLookupError(f"[device_exists by Serial] {e}")

    if len(devices) > 1:
        raise NetboxCustomLookupError(
            f"[device_exists by Serial] More than one device found for serial {serial_number}!"
        )

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


async def get_rendered_config_bySerial(serial_number: str) -> str:
    """Async Version von get_rendered_config_bySerial."""
    device = await device_exists_bySerial(serial_number)
    client = _get_client()

    try:
        resp = await client.post(f"/api/dcim/devices/{device['id']}/render-config/")
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise NetboxCustomLookupError(str(e))

    data = resp.json()
    if "content" in data:
        return data["content"]
    else:
        raise NetboxCustomLookupError(
            "No content found in netbox answer [get_rendered_config_bySerial]"
        )


async def lookup_site_by_ip(
    device_ip: str = "0.0.0.0",
    api_filter: dict | None = None,
) -> str:
    """Async Version von lookup_site_by_ip."""
    params: dict[str, Any] = {"contains": device_ip}
    if api_filter:
        params.update(api_filter)

    prefix_list = await _fetch_all("ipam/prefixes/", params)

    # get prefix with biggest match
    if len(prefix_list) >= 1:
        network = prefix_list[-1]

        if has_object_scope(network, ScopeType.SITE):
            return network["scope"]["slug"]
        else:
            raise NetboxCustomLookupError(
                f"{network.get('prefix')} has no netbox ScopeType.SITE '{ScopeType.SITE}' assigned!"
            )
    else:
        raise NetboxCustomLookupError("No network found! Adjust api_filter!")


async def lookup_firmware_by_model_type(
    model_type: str,
    firmware_custom_field: str = "firmware_filename",
) -> dict[str, Any]:
    """Async Version von lookup_firmware_by_model_type."""
    ret: dict[str, Any] = {
        "firmware_filename": None,
        "platform": None,
        "flash": None,
    }

    try:
        models = await _fetch_all("dcim/device-types/", {"model": model_type})
    except Exception as e:
        raise NetboxCustomLookupError(f"firmware_lookup {e}")

    if len(models) == 0:
        raise NetboxCustomLookupError(f"Device type '{model_type}' not found!")
    if len(models) > 1:
        raise NetboxCustomLookupError(
            f"Multiple device types found for model '{model_type}'!"
        )

    model = models[0]
    cf = model.get("custom_fields", {})

    if firmware_custom_field in cf:
        ret[firmware_custom_field] = cf[firmware_custom_field]
    else:
        raise NetboxCustomFieldMissing(
            f"Custom field 'firmware_filename' on device_type {model_type} not found!"
        )

    if model.get("default_platform"):
        platform_name = model["default_platform"]["name"]
        ret["platform"] = platform_name
        if platform_name == "IOS-XE":
            ret["flash"] = "bootflash:"
        elif platform_name == "IOS":
            ret["flash"] = "flash:"

    return ret


# ---------------------------------------------------------------------------
# Interne Hilfsfunktionen für createDevices
# ---------------------------------------------------------------------------


async def _device_delete_all_ips(
    device: dict[str, Any], interface_name: str = "vlan1"
) -> None:
    """Löscht primary_ip4 und alle IPs an einem Interface."""
    client = _get_client()

    if device.get("primary_ip4"):
        ip_id = device["primary_ip4"]["id"]
        await client.delete(f"/api/ipam/ip-addresses/{ip_id}/")

    if interface_name:
        interfaces = await _fetch_all(
            "dcim/interfaces/",
            {"device_id": device["id"], "name": interface_name},
        )
        for iface in interfaces:
            ip_list = await _fetch_all(
                "ipam/ip-addresses/", {"interface_id": iface["id"]}
            )
            for ip in ip_list:
                await client.delete(f"/api/ipam/ip-addresses/{ip['id']}/")


async def _create_vc_from_device_list(
    device_obj_list: list[dict[str, Any]], site_id: int
) -> None:
    """Erstellt ein Virtual Chassis aus einer Device-Liste."""
    client = _get_client()

    try:
        vc_name = device_obj_list[0]["name"]
        resp = await client.post(
            "/api/dcim/virtual-chassis/",
            json={"name": vc_name, "site": site_id, "master": device_obj_list[0]["id"]},
        )
        resp.raise_for_status()
        vc = resp.json()

        for cnt, device in enumerate(device_obj_list, 1):
            patch: dict[str, Any] = {"virtual_chassis": vc["id"]}
            if not device.get("vc_position"):
                patch["vc_position"] = cnt
            if not device.get("vc_priority"):
                patch["vc_priority"] = switch_position[cnt]
            resp = await client.patch(f"/api/dcim/devices/{device['id']}/", json=patch)
            resp.raise_for_status()

    except httpx.HTTPStatusError as e:
        raise NetboxCustomCreateDeviceError(f"VC creation error: {e.response.text}")


async def createDevices(
    device_info_list: list[dict] | None = None,
    site_slug: str = "",
    role_slug: str = "",
    device_create_args: dict[str, Any] | None = None,
    create_vc: bool = False,
) -> list[dict[str, Any]]:
    """
    Async Version von createDevices.
    Erzeugt Devices in NetBox; bei >1 Device wird optional ein VC angelegt.
    """
    if device_info_list is None:
        device_info_list = []
    if device_create_args is None:
        device_create_args = {}

    client = _get_client()

    sites = await _fetch_all("dcim/sites/", {"slug": site_slug})
    if not sites:
        raise NetboxCustomCreateDeviceError(
            f'site_slug "{site_slug}" not found in netbox.'
        )
    site = sites[0]

    roles = await _fetch_all("dcim/device-roles/", {"slug": role_slug})
    if not roles:
        raise NetboxCustomCreateDeviceError(
            f'role_slug "{role_slug}" not found in netbox.'
        )
    role = roles[0]

    # build and cleanup [list] of dict(s) to create the device(s)
    for index, dev in enumerate(device_info_list, 1):
        if dev["name"] in device_default_names:
            dev["name"] = f"{dev['name']}-{dev['serial']}"

        dev["role"] = role["id"]
        dev["site"] = site["id"]
        dev.update(device_create_args)

        if len(device_info_list) > 1:
            if "slot" in dev:
                dev["vc_position"] = dev["slot"]
            else:
                dev["vc_position"] = f"{index}"

            if "priority" in dev:
                dev["vc_priority"] = f"{dev['priority']}"
            else:
                dev["vc_priority"] = f"{switch_position[index]}"

    device_info_list = build_stack_hostname(
        device_info_list[0]["name"], device_info_list
    )

    # contains the created devices
    device_obj_list: list[dict[str, Any]] = []

    for dev in device_info_list:
        found: dict[str, Any] | None = None

        try:
            found = await device_exists_bySerial(
                dev["serial"], device_type=dev["device_type"]
            )
            await _device_delete_all_ips(found)
            device_obj_list.append(found)

            # device was found, and it is part of a VC, delete the VC, but not the device, it can be used later to
            # build a new VC
            if found.get("virtual_chassis"):
                vc_id = found["virtual_chassis"]["id"]
                await client.delete(f"/api/dcim/virtual-chassis/{vc_id}/")
        except NetboxCustomNotFoundError:
            pass

        # check if needed device_types exits
        device_types = await _fetch_all(
            "dcim/device-types/", {"model": dev["device_type"]}
        )
        if not device_types:
            raise NetboxCustomCreateDeviceError(
                f"Device_Type \"{dev['device_type']}\" not found in netbox, please create it before using it."
            )
        dev["device_type"] = device_types[0]["id"]

        # since device was not found it can be created
        if not found:
            try:
                resp = await client.post("/api/dcim/devices/", json=dev)
                resp.raise_for_status()
                device_obj_list.append(resp.json())
            except httpx.HTTPStatusError as e:
                raise NetboxCustomCreateDeviceError(f"Netbox error: {e.response.text}")

    if len(device_obj_list) > 1 and create_vc:
        await _create_vc_from_device_list(device_obj_list, site_id=site["id"])

    return device_obj_list


async def get_next_available_prefix(
    prefix_length: int,
    role_slug: str,
) -> dict[str, Any]:
    """
    Ermittelt das nächste freie Netz einer bestimmten Größe innerhalb von
    Parent-Prefixes, die über role_slug gefiltert werden.

    Returns:
        {
            "prefix": "10.0.0.0/23",
            "parent_prefix": "10.0.0.0/20",
            "parent_id": 123,
        }

    Raises:
        NetboxCustomLookupError: wenn kein passendes freies Netz gefunden wird.
    """
    client = _get_client()

    try:
        parent_prefixes = await _fetch_all("ipam/prefixes/", {"role": role_slug})
    except httpx.HTTPStatusError as e:
        raise NetboxCustomLookupError(f"[get_next_available_prefix] HTTP error: {e}")

    if not parent_prefixes:
        raise NetboxCustomLookupError(
            f"[get_next_available_prefix] No prefixes found for role_slug '{role_slug}'."
        )

    for parent in parent_prefixes:
        parent_id = parent["id"]
        parent_prefix_str = parent["prefix"]

        try:
            resp = await client.get(f"/api/ipam/prefixes/{parent_id}/available-prefixes/")
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise NetboxCustomLookupError(
                f"[get_next_available_prefix] HTTP error fetching available-prefixes for {parent_prefix_str}: {e}"
            )

        available_blocks = resp.json()

        for block in available_blocks:
            network = ipaddress.ip_network(block["prefix"])
            if network.prefixlen <= prefix_length:
                subnet = list(network.subnets(new_prefix=prefix_length))[0]
                return {
                    "prefix": str(subnet),
                    "parent_prefix": parent_prefix_str,
                    "parent_id": parent_id,
                }

    raise NetboxCustomLookupError(
        f"[get_next_available_prefix] No free /{prefix_length} block found in prefixes with role_slug '{role_slug}'."
    )


def has_object_tenant(obj: dict[str, Any]) -> bool:
    """
    General function. Checks if an netbox object has a tenant assigned
    """
    if jmespath.search("tenant.id", obj):
        return True

    return False


def has_object_scope(obj: dict[str, Any], scope_type: ScopeType | None = None) -> bool:
    """
    Checks if a netbox object has a scope e.g. used on a prefix object.
    But the scope object needs to have an id, to be a valid scope!
    """

    # if scope type is not found -> raus
    if not jmespath.search("scope_type", obj):
        return False

    # if scope_type check is set!
    if scope_type is not None:
        type_str = jmespath.search("scope_type", obj)

        if scope_type != type_str:
            return False

    # scope_type found! check if scope has an id (and is not None)
    if jmespath.search("scope.id", obj):
        return True

    return False
