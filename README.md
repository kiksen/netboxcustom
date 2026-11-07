# netboxcustom

A helper library for NetBox automation I use for a few personal projects. It talks to the NetBox REST API via `httpx2` and provides device management, site lookups by IP, device-type/firmware queries, rendered configs, and a Cisco IOS parser.

There are two clients with the same methods:

- `AsyncNetboxCustom` — the reference implementation (`netboxcustom.netboxcustom_async`)
- `NetboxCustom` — a blocking wrapper around the async client (`netboxcustom.netboxcustom`)

## Installation

```bash
pip install git+https://github.com/user/repo.git

# or with uv:
uv add git+https://github.com/kiksen/netboxcustom.git
```

## Requirements

- Python >= 3.14
- A running NetBox instance (scope-based prefix lookups need NetBox >= 4.2)
- Dependencies: `httpx2`, `jmespath`, `rich`

---

## Quick Start

**Async:**

```python
import asyncio
from netboxcustom import AsyncNetboxCustom

async def main():
    async with AsyncNetboxCustom("https://netbox.example.com", "nbt_your.token") as nb:
        sites = await nb.get_site_list()
        # [{'id': 1, 'name': 'Munich', 'slug': 'munich', 'gns': 'MUC', 'long': 'MUC-munich', ...}]

asyncio.run(main())
```

**Sync:**

```python
from netboxcustom import NetboxCustom

with NetboxCustom("https://netbox.example.com", "nbt_your.token") as nb:
    sites = nb.get_site_list()
```

Both clients must be used as a context manager. The sync client keeps one event loop alive for the lifetime of the `with` block, so the underlying HTTP client stays open across calls.

---

## Modules

| Module | Description |
|---|---|
| `netboxcustom.NetboxCustom` | Synchronous client |
| `netboxcustom.AsyncNetboxCustom` | Asynchronous client |
| `netboxcustom.models` | `DeviceInfo`, `DeviceType`, `LookupSiteByIp`, `ScopeType` |
| `netboxcustom.helper` | `build_stack_hostname`, `has_object_tenant`, `has_object_scope` |
| `netboxcustom.iosparser` | Cisco IOS/IOS-XE `show version` / hostname parser |
| `netboxcustom.exceptions` | All exception classes (also exported from `netboxcustom`) |

---

## Authentication

The token type is detected automatically:

| Token | Header |
|---|---|
| `nbt_<key>.<token>` | `Authorization: Bearer <token>` |
| anything else | `Authorization: Token <token>` |

The endpoint and token are passed to the constructor. Reading them from the environment (`NETBOX_ENDPOINT`, `NETBOX_TOKEN`) is only done by the tests.

---

## Method Overview

All methods exist on both clients. On the async client they are coroutines (`await nb.method(...)`), on the sync client they block.

| Method | Description |
|---|---|
| `get_site_list` | Sites as simplified dicts |
| `lookup_site_by_ip` / `lookup_site_by_ip_full` | Site slug of the most specific prefix containing an IP |
| `device_exists_bySerial` | Find a device by serial number |
| `get_rendered_config_bySerial` | Rendered config of a device |
| `createDevices` / `createDevicesFromModels` | Create devices, optionally as Virtual Chassis |
| `get_device_type` / `get_device_types` / `get_device_types_by_names` | Device types with firmware metadata |

Every method returns plain `dict`s (or dataclasses from `netboxcustom.models`) and handles API pagination automatically.

---

## Site Functions

### `get_site_list`

Returns site information as a list of dicts. `params` are passed to NetBox as query filters.

```python
sites = await nb.get_site_list()
sites = await nb.get_site_list({"slug": "munich"})
sites = await nb.get_site_list({"tenant": "mycompany"})
```

**Returns** (each entry):

| Key | Type | Description |
|---|---|---|
| `id` | int | NetBox site ID |
| `name` | str | Display name |
| `slug` | str | URL slug |
| `gns` | str | `GNS` custom field value (`"tbc"` if unset) |
| `description` | str | Site description |
| `display` | str | Display label |
| `long` | str | Combined `gns-slug` string |

---

### `lookup_site_by_ip` / `lookup_site_by_ip_full`

Finds the site for an IP address by looking it up in IPAM prefixes (`contains` filter). The last prefix in the NetBox result (the most specific one) wins. Its scope must be a site (`ScopeType.SITE`).

```python
from netboxcustom import NetboxCustomLookupError, NetboxScopeTypeNotFound

try:
    slug = await nb.lookup_site_by_ip("10.10.10.1")
    # "munich"

    # With additional prefix filter (e.g. by role)
    slug = await nb.lookup_site_by_ip("10.10.10.1", api_filter={"role": "network-management"})

    # Full result
    result = await nb.lookup_site_by_ip_full("10.10.10.1")
    result.site_slug    # "munich"
    result.subnet       # "10.10.10.0/24"  (matching prefix)
    result.subnet_list  # all prefixes containing the IP
    result.api_filter   # the filter used
except NetboxCustomLookupError:
    ...  # no prefix found
except NetboxScopeTypeNotFound:
    ...  # prefix found, but its scope is not a site
```

---

## Device Functions

### `createDevices`

Creates one or more devices. Idempotent: if a device with the same serial already exists, it is reused (its primary IPs and any IP on `vlan1` are deleted, and an existing Virtual Chassis is deleted, the device itself is kept).

```python
devices = await nb.createDevices(
    device_info_list=[
        {"name": "switch", "device_type": "C9200L-48P-4G", "serial": "FCW2345ABCD"},
    ],
    site_slug="munich",
    role_slug="access",
)
```

**Stack example** (two switches → Virtual Chassis):

```python
devices = await nb.createDevices(
    device_info_list=[
        {"name": "CORE-SW", "device_type": "C9500-40X", "serial": "FCW2233FFG3", "slot": 1},
        {"name": "CORE-SW", "device_type": "C9500-40X", "serial": "FCW1234F88V", "slot": 2},
    ],
    site_slug="munich",
    role_slug="access",
    create_vc=True,
)
# Creates CORE-SW-1 and CORE-SW-2, linked in a Virtual Chassis
```

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `device_info_list` | `list[dict]` | — | Device specs (see below), at most 15 entries |
| `site_slug` | `str` | `""` | Target site slug |
| `role_slug` | `str` | `""` | Device role slug |
| `device_create_args` | `dict \| None` | `None` | Extra fields merged into every device on creation |
| `create_vc` | `bool` | `False` | Create a Virtual Chassis when more than one device is given |
| `default_device_names` | `list[str] \| None` | `["switch", "router"]` | Names that get `-<serial>` appended |
| `compare_lowercase` | `bool` | `False` | Lowercase all device names and `default_device_names` before comparing |

**`device_info_list` entry fields:**

| Key | Required | Description |
|---|---|---|
| `name` | yes | Device name |
| `device_type` | yes | NetBox device type model (e.g. `"C9500-40X"`) |
| `serial` | yes | Unique serial number (used for idempotency) |
| `slot` | no | Stack slot, sets `vc_position` (default: position in the list) |
| `priority` | no | Stack priority, sets `vc_priority` (default: descending from 15) |

The input dicts are modified in place. With more than one device, names get a `-<slot>` suffix; an existing numeric suffix on the first name is stripped first (`CORE-SW-1` → `CORE-SW`).

**Raises:** `NetboxCustomCreateDeviceError` (site, role or device type not found, creation failed), `NetboxCustomGeneralError` (more than 15 devices).

### `createDevicesFromModels`

Same as `createDevices`, but takes `DeviceInfo` dataclasses (`name`, `serial`, `device_type`, `slot=None`, `priority=None`).

```python
from netboxcustom.models import DeviceInfo

devices = await nb.createDevicesFromModels(
    [DeviceInfo(name="CORE-SW", serial="FCW2233FFG3", device_type="C9500-40X", slot=1),
     DeviceInfo(name="CORE-SW", serial="FCW1234F88V", device_type="C9500-40X", slot=2)],
    site_slug="munich",
    role_slug="access",
    create_vc=True,
)
```

---

### `device_exists_bySerial`

Finds a device by serial number and optionally checks the device type. Returns the device as a dict.

```python
from netboxcustom import NetboxCustomNotFoundError

try:
    device = await nb.device_exists_bySerial("FCW2233FFG3")
    print(device["name"], device["id"])

    # With type check
    device = await nb.device_exists_bySerial("FCW2233FFG3", device_type="C9500-40X")
except NetboxCustomNotFoundError as e:
    print(f"Not found: {e}")
```

**Raises:**
- `NetboxCustomNotFoundError` — serial not found, or device type mismatch
- `NetboxCustomLookupError` — multiple devices with the same serial

---

### `get_rendered_config_bySerial`

Returns the rendered configuration text of a device, looked up by serial number. With `load_vc_master=True` and a device that is part of a Virtual Chassis, the config of the VC master is returned instead.

```python
config = await nb.get_rendered_config_bySerial("FCW2233FFG3")
config = await nb.get_rendered_config_bySerial("FCW2233FFG3", load_vc_master=True)
```

**Raises:**
- `NetboxCustomNotFoundError` — device not found
- `NetboxCustomLookupError` — render failed, no content, or the VC has no master

---

## Device Types / Firmware

Device types are returned as `DeviceType` dataclasses, built from a custom field of the device type and its default platform.

| Field | Description |
|---|---|
| `device_type` | Model name |
| `firmware_custom_field` | Name of the custom field that was read |
| `firmware_filename` | Value of that custom field |
| `firmware_version` | Value of `version_custom_field` (empty if not requested or not set) |
| `platform` | Default platform name, uppercased (`"IOS-XE"`, `"IOS"`); guessed from the model for C9200/C9300/C940/WS-C3850 (IOS-XE) and WS-C2960/3750/6500 (IOS) if unset |
| `flash` | `"bootflash:"` (IOS-XE) or `"flash:"` (IOS) |
| `error` | Error message, set only by `get_device_types` / `get_device_types_by_names` |

### `get_device_type`

Returns exactly one device type.

```python
fw = await nb.get_device_type("C9500-40X")
# DeviceType(device_type='C9500-40X', firmware_custom_field='firmware_filename',
#            firmware_filename='cat9k_iosxe.17.06.05.SPA.bin', platform='IOS-XE', flash='bootflash:', ...)

fw = await nb.get_device_type(
    "c9500-40x",
    firmware_custom_field="firmware_filename",
    version_custom_field="firmware_version",
    search_from=("model", "part_number", "slug"),  # tried in order, first match wins
    ignore_case=True,                               # NetBox __ie lookup
)
```

**Raises:** `NetboxCustomLookupError` (not found, multiple matches, invalid `search_from`), `NetboxCustomFieldMissing` (firmware custom field missing).

### `get_device_types`

Returns all device types matching an API filter. A type without the firmware custom field is returned with `error` set instead of raising.

```python
types = await nb.get_device_types({"manufacturer": "cisco"})
```

### `get_device_types_by_names`

Looks up a list of device types by model name (via `get_device_type`). Types that are not found or lack the firmware field are returned with `error` set instead of raising.

```python
types = await nb.get_device_types_by_names(["C9500-40X", "WS-C2960X-48FPD-L"])
```

> Renamed from `lookup_firmware_list`; the parameter `model_types` is now `device_types`.

---

## Helper Functions (`netboxcustom.helper`)

These work on plain dicts from the API.

### `build_stack_hostname`

Assigns numbered hostnames (`-<slot>`) to a stack device list (each entry needs `slot`). Only applies to lists with more than one entry. A numeric suffix on the base hostname is stripped first.

```python
from netboxcustom.helper import build_stack_hostname

stack = [
    {"name": "CORE-SW", "serial": "AAA", "slot": 1},
    {"name": "CORE-SW", "serial": "BBB", "slot": 2},
]
build_stack_hostname("CORE-SW-1", stack)
# [{"name": "CORE-SW-1", ...}, {"name": "CORE-SW-2", ...}]
```

### `has_object_tenant`

```python
from netboxcustom.helper import has_object_tenant

has_object_tenant(device)  # True if device["tenant"]["id"] is set
```

### `has_object_scope`

Checks whether an object (e.g. a prefix) has a scope with an `id`. Optionally checks the scope type.

```python
from netboxcustom import ScopeType
from netboxcustom.helper import has_object_scope

has_object_scope(prefix)                 # any scope
has_object_scope(prefix, ScopeType.SITE) # only scope_type == "dcim.site"
```

**`ScopeType` values:**

| Constant | Value |
|---|---|
| `ScopeType.REGION` | `"dcim.region"` |
| `ScopeType.SITE_GROUP` | `"dcim.sitegroup"` |
| `ScopeType.SITE` | `"dcim.site"` |
| `ScopeType.LOCATION` | `"dcim.location"` |

---

## IOS Parser (`netboxcustom.iosparser`)

### `parse_show_version`

Parses `show version` output of Cisco IOS and IOS-XE devices. Supports stacked switches. The result can be passed to `createDevices` after adding a `name`.

```python
from netboxcustom.iosparser import parse_show_version

show = """
Model Number                       : WS-C2960X-48FPD-L
System Serial Number               : FOC1234ABCD
Base Ethernet MAC Address          : aa:bb:cc:dd:ee:ff
"""

parse_show_version(show)
# [{'serial': 'FOC1234ABCD', 'device_type': 'WS-C2960X-48FPD-L', 'base_mac': 'aa:bb:cc:dd:ee:ff', 'slot': 1}]
```

Returns `[]` if the number of found models and serials differs.

### `parse_hostname`

Parses the hostname from `show running-config | include hostname` output. Accepts a string or a list of lines. Returns `""` if none is found.

```python
from netboxcustom.iosparser import parse_hostname

parse_hostname("hostname CORE-SW-01")                       # "CORE-SW-01"
parse_hostname(["interface Gi0/0", "hostname DIST-SW"])     # "DIST-SW"
```

---

## Exceptions

All exceptions inherit from `NetboxCustomBase` and have `.message`, `.status_code` and `.as_dict()`. They are importable from `netboxcustom`.

| Exception | Status | When raised |
|---|---|---|
| `NetboxCustomNotFoundError` | 404 | Resource not found (serial, device type mismatch) |
| `NetboxCustomLookupError` | 404 | Lookup failed (no result, ambiguous result) |
| `NetboxScopeTypeNotFound` | 404 | Prefix has no scope of the expected type |
| `NetboxCustomFieldMissing` | 404 | Expected custom field not present on object |
| `NetboxCustomCreateDeviceError` | 400 | Device creation failed |
| `NetboxCustomCreateVirtualChassisError` | 400 | Virtual Chassis creation failed |
| `NetboxCustomGeneralError` | 400 | Catch-all for other errors |
| `NetboxCustomConnectionError` | 0 | NetBox not reachable or HTTP error while listing |

```python
from netboxcustom import NetboxCustomNotFoundError

try:
    await nb.device_exists_bySerial("UNKNOWN-SERIAL")
except NetboxCustomNotFoundError as e:
    print(e)           # "Serial UNKNOWN-SERIAL not found in Netbox! (404)"
    print(e.as_dict()) # {'message': '...', 'status_code': 404, 'status': '1'}
```

---

## Running Tests

Integration tests need a running NetBox instance:

```bash
export NETBOX_ENDPOINT="https://netbox.example.com"
export NETBOX_TOKEN="your-token"
```

```bash
pytest -v                          # all tests
pytest tests/test_iosparser.py -v  # unit tests only, no NetBox required
pytest tests/test_async.py -v      # async integration tests
```
