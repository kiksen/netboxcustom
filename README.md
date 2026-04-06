# netboxcustom

A pynetbox wrapper and helper library for NetBox automation I use for a few personal projects. Provides synchronous (`netboxcustom`) and asynchronous (`netboxcustom.aio`) APIs for device management, IP address handling, site lookups, firmware queries, and Cisco IOS parsing.

## Installation

```bash
pip install git+https://github.com/user/repo.git

# or with uv:
uv add git+https://github.com/kiksen/netboxcustom.git
```

## Requirements

- Python >= 3.8
- A running NetBox instance
- Environment variables: `NETBOX_ENDPOINT`, `NETBOX_TOKEN`

---

## Quick Start

```python
from netboxcustom import nb_login, get_site_list, createDevices

nb = nb_login("https://netbox.example.com", "your-token")

sites = get_site_list(nb)
# [{'id': 1, 'name': 'Munich', 'slug': 'munich', 'gns': 'MUC', 'long': 'MUC-munich', ...}]
```

**Async:**

```python
import asyncio
from netboxcustom import aio

async def main():
    await aio.nb_login("https://netbox.example.com", "nbt_your.token")
    sites = await aio.get_site_list()

asyncio.run(main())
```

---

## Modules

| Module | Description |
|---|---|
| `netboxcustom` | Synchronous API (uses pynetbox) |
| `netboxcustom.aio` | Asynchronous API (uses httpx) |
| `netboxcustom.iosparser` | Cisco IOS/IOS-XE `show version` parser |

---

## Authentication

### Sync

```python
from netboxcustom import nb_login

# Token via parameter
nb = nb_login("https://netbox.example.com", "abc123")

# Token via environment variable NETBOX_TOKEN
nb = nb_login("https://netbox.example.com")
```

### Async

```python
from netboxcustom import aio

# Token-type is auto-detected:
#   nbt_<key>.<token>  →  Authorization: Bearer <token>
#   anything else      →  Authorization: Token <token>

await aio.nb_login("https://netbox.example.com", "nbt_abc.xyz")  # Bearer
await aio.nb_login("https://netbox.example.com", "abc123")       # Token
```

---

## Site Functions

### `get_site_list`

Returns site information as a list of dicts. Optionally filter by slug(s).

```python
# All sites
sites = get_site_list(nb)

# Filter by slug
sites = get_site_list(nb, site_slug=["munich", "berlin"])
```

**Returns** (each entry):

| Key | Type | Description |
|---|---|---|
| `id` | int | NetBox site ID |
| `name` | str | Display name |
| `slug` | str | URL slug |
| `gns` | str | GNS custom field value (`"tbc"` if unset) |
| `description` | str | Site description |
| `display` | str | Display label |
| `long` | str | Combined `gns-slug` string |

**Example:**

```python
[
    {
        'id': 1,
        'name': 'Munich',
        'slug': 'munich',
        'gns': 'MUC',
        'description': 'HQ Munich',
        'display': 'Munich',
        'long': 'MUC-munich'
    }
]
```

---

## Device Functions

### `createDevices`

Creates one or more devices in NetBox. Idempotent — if a device with the same serial and type already exists, it is reused (existing IPs are cleared).

```python
from netboxcustom import createDevices

devices = createDevices(
    nb,
    device_info_list=[
        {
            "name": "switch",
            "device_type": "C9200L-48P-4G",
            "serial": "FCW2345ABCD",
        }
    ],
    site_slug="munich",
    role_slug="access",
)
```

**Stack example** (two switches → Virtual Chassis):

```python
devices = createDevices(
    nb,
    device_info_list=[
        {"name": "CORE-SW", "device_type": "C9500-40X", "serial": "FCW2233FFG3", "slot": 1},
        {"name": "CORE-SW", "device_type": "C9500-40X", "serial": "FCW1234F88V", "slot": 2},
    ],
    site_slug="munich",
    role_slug="access",
    create_vc=True,
)
# Creates devices named CORE-SW-1 and CORE-SW-2, linked in a Virtual Chassis
```

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `nb` | `pynetbox.api` | — | NetBox connection |
| `device_info_list` | `list[dict]` | `[]` | Device specs (see below) |
| `site_slug` | `str` | `""` | Target site slug |
| `role_slug` | `str` | `""` | Device role slug |
| `device_create_args` | `dict` | `{}` | Extra fields passed to NetBox on creation |
| `create_vc` | `bool` | `False` | Create Virtual Chassis when >1 device |

**`device_info_list` entry fields:**

| Key | Required | Description |
|---|---|---|
| `name` | yes | Device name. Names in `["switch", "router"]` get serial appended automatically |
| `device_type` | yes | NetBox model name (e.g. `"C9500-40X"`) |
| `serial` | yes | Unique serial number (used for idempotency) |
| `slot` | no | Stack slot number, sets `vc_position` |

**Default name behaviour:**

```python
# name "switch" → "switch-FCW2345ABCD"
{"name": "switch", "device_type": "C9200L-48P-4G", "serial": "FCW2345ABCD"}

# name is kept as-is
{"name": "CORE-SW-01", "device_type": "C9200L-48P-4G", "serial": "FCW2345ABCD"}
```

---

### `device_exists_bySerial`

Checks whether a device exists in NetBox by serial number. Optionally validates the device type.

```python
from netboxcustom import device_exists_bySerial
from netboxcustom.netboxcustom import NetboxCustomNotFoundError

try:
    device = device_exists_bySerial(nb, "FCW2233FFG3")
    print(device.name, device.id)

    # With type check
    device = device_exists_bySerial(nb, "FCW2233FFG3", device_type="C9500-40X")
except NetboxCustomNotFoundError as e:
    print(f"Not found: {e}")
```

**Raises:**
- `NetboxCustomNotFoundError` — serial not found, or device type mismatch
- `NetboxCustomLookupError` — multiple devices with same serial

---

### `get_device_list`

Returns all devices for a site as a list of dicts.

```python
devices = get_device_list(nb, site_slug="munich")
```

**Returns** (each entry):

| Key | Type | Description |
|---|---|---|
| `id` | int | Device ID |
| `name` | str | Device name |
| `serial_number` | str | Serial number |
| `device_type` | str | Model name |
| `ip` | str \| None | Primary IPv4 (without prefix length) |
| `stack` | bool | `True` if part of a Virtual Chassis |
| `url` | str | NetBox URL |
| `comment` | str | Comments |
| `description` | str | Description |

---

### `get_rendered_config_bySerial`

Returns the rendered configuration text for a device, looked up by serial number.

```python
config = get_rendered_config_bySerial(nb, "FCW2233FFG3")
print(config)
```

**Raises:**
- `NetboxCustomNotFoundError` — device not found
- `NetboxCustomLookupError` — no config template assigned

---

### `build_stack_hostname`

Assigns numbered hostnames (`-1`, `-2`, ...) to a stack device list. Strips existing numeric suffixes before adding new ones.

```python
from netboxcustom import build_stack_hostname

stack = [
    {"name": "CORE-SW", "serial": "AAA", "slot": 1},
    {"name": "CORE-SW", "serial": "BBB", "slot": 2},
]
result = build_stack_hostname("CORE-SW", stack)
# [{"name": "CORE-SW-1", ...}, {"name": "CORE-SW-2", ...}]

# Existing suffix is stripped first:
result = build_stack_hostname("CORE-SW-1", stack)
# [{"name": "CORE-SW-1", ...}, {"name": "CORE-SW-2", ...}]
```

---

## IP Address Functions

### `createOrUpdateIP`

Creates a new IP address or updates an existing one (matched by address without prefix length).

```python
from netboxcustom import createOrUpdateIP

ip = createOrUpdateIP(nb, {
    "address": "10.10.10.1/24",
    "description": "Core switch management",
    "dns_name": "core-sw.example.com",
    "status": "active",
})
```

---

### `lookup_site_by_ip`

Finds the site slug for a given IP address by looking it up in IPAM prefixes. Returns the best-matching (most specific) prefix's site.

Supports both legacy `site` attribute and NetBox v4.2+ `scope`/`scope_type`.

```python
from netboxcustom import lookup_site_by_ip
from netboxcustom.netboxcustom import NetboxCustomLookupError

try:
    slug = lookup_site_by_ip(nb, "10.10.10.1")
    # "munich"

    # With additional prefix filter (e.g. by role)
    slug = lookup_site_by_ip(nb, "10.10.10.1", api_filter={"role": "network-management"})
except NetboxCustomLookupError as e:
    print(f"Site not found: {e}")
```

---

### `update_subnetmask_for_ip`

Updates an IP address's prefix length to match its containing prefix. Only modifies `/32` host addresses.

```python
from netboxcustom import update_subnetmask_for_ip

ip_obj = nb.ipam.ip_addresses.get(address="10.10.10.1/32")
update_subnetmask_for_ip(nb, ip_obj)
# ip_obj.address becomes e.g. "10.10.10.1/24" if contained in 10.10.10.0/24
```

---

### `assign_tenant_to_ip`

Assigns a tenant to an IP address. If no `tenant_id` is given, the tenant is resolved from the IP's containing prefix → site → site tenant.

```python
from netboxcustom import assign_tenant_to_ip

ip_obj = nb.ipam.ip_addresses.get(address="10.10.10.1/24")

# Auto-resolve tenant from site
assign_tenant_to_ip(nb, ip_obj)

# Or provide tenant_id directly
assign_tenant_to_ip(nb, ip_obj, tenant_id=5)
```

---

## Firmware Functions

### `lookup_firmware_by_model_type`

Returns firmware metadata for a device type, read from a custom field and the type's default platform.

```python
from netboxcustom import lookup_firmware_by_model_type

fw = lookup_firmware_by_model_type(nb, "C9500-40X")
# {
#     "firmware_filename": "cat9k_iosxe.17.06.05.SPA.bin",
#     "platform": "IOS-XE",
#     "flash": "bootflash:"
# }

fw = lookup_firmware_by_model_type(nb, "WS-C2960X-48FPD-L")
# {
#     "firmware_filename": "c2960x-universalk9-mz.152-7.E6.bin",
#     "platform": "IOS",
#     "flash": "flash:"
# }
```

**Returns:**

| Key | Description |
|---|---|
| `firmware_filename` | Value of the `firmware_filename` custom field |
| `platform` | Default platform name (e.g. `"IOS-XE"`, `"IOS"`) |
| `flash` | Flash location: `"bootflash:"` (IOS-XE) or `"flash:"` (IOS) |

**Raises:**
- `NetboxCustomLookupError` — device type not found
- `NetboxCustomFieldMissing` — `firmware_filename` custom field missing on device type

---

## Virtual Chassis Functions

### `create_vc_from_device_list`

Creates a Virtual Chassis from a list of devices. The first device becomes the VC master. Position and priority are assigned automatically from the `switch_position` table.

```python
from netboxcustom import create_vc_from_device_list

create_vc_from_device_list(nb, device_obj_list=[dev1, dev2], site_id=1)
```

### `clean_up_vc_membership`

Removes devices from their current Virtual Chassis (deletes the VC).

```python
from netboxcustom import clean_up_vc_membership

clean_up_vc_membership(nb, [device1, device2])
```

### `load_devices_from_vc`

Returns all members of the Virtual Chassis a device belongs to. Returns `[device]` if the device is not in a VC.

```python
from netboxcustom import load_devices_from_vc

members = load_devices_from_vc(nb, device)
```

---

## Helper / Inspection Functions

### `has_object_tenant`

```python
from netboxcustom import has_object_tenant

has_object_tenant(device)  # True / False
```

### `has_site_tenant`

```python
from netboxcustom import has_site_tenant

site = nb.dcim.sites.get(slug="munich")
has_site_tenant(site)  # True / False
```

### `has_object_scope`

Checks whether a NetBox object has a scope assigned. Optionally validates the scope type.

```python
from netboxcustom import has_object_scope
from netboxcustom.netboxcustom import ScopeType

prefix = nb.ipam.prefixes.get(id=1)

has_object_scope(prefix)                 # True if any scope
has_object_scope(prefix, ScopeType.SITE) # True only if scope_type == "dcim.site"
has_object_scope(prefix, "dcim.site")    # same, using raw string
```

**`ScopeType` enum values:**

| Constant | Value |
|---|---|
| `ScopeType.REGION` | `"dcim.region"` |
| `ScopeType.SITE_GROUP` | `"dcim.sitegroup"` |
| `ScopeType.SITE` | `"dcim.site"` |
| `ScopeType.LOCATION` | `"dcim.location"` |

---

## Async API (`netboxcustom.aio`)

All synchronous functions have async equivalents in `netboxcustom.aio`. Key differences:

- Uses `httpx.AsyncClient` instead of pynetbox
- Returns `dict` instead of pynetbox model objects
- Auto-handles API pagination
- Token type detected automatically (`nbt_` prefix → Bearer, else Token)

```python
from netboxcustom import aio

async def main():
    await aio.nb_login()  # reads NETBOX_ENDPOINT + NETBOX_TOKEN from env

    # Sites
    sites = await aio.get_site_list(["munich", "berlin"])

    # Device lookup
    device = await aio.device_exists_bySerial("FCW2233FFG3", device_type="C9500-40X")

    # Rendered config
    config = await aio.get_rendered_config_bySerial("FCW2233FFG3")

    # Site from IP
    slug = await aio.lookup_site_by_ip("10.10.10.1")

    # Firmware info
    fw = await aio.lookup_firmware_by_model_type("C9500-40X")

    # Create devices
    devices = await aio.createDevices(
        device_info_list=[
            {"name": "switch", "device_type": "C9500-40X", "serial": "FCW2233FFG3", "slot": 1},
            {"name": "switch", "device_type": "C9500-40X", "serial": "FCW1234F88V", "slot": 2},
        ],
        site_slug="munich",
        role_slug="access",
        create_vc=True,
    )
```

### `get_next_available_prefix` (async only)

Finds the next free subnet of a given size within parent prefixes filtered by role slug.

```python
result = await aio.get_next_available_prefix(prefix_length=23, role_slug="loopbacks")
# {
#     "prefix": "10.0.2.0/23",
#     "parent_prefix": "10.0.0.0/20",
#     "parent_id": 42
# }
```

**Raises:** `NetboxCustomLookupError` if no free block is available.

---

## IOS Parser (`netboxcustom.iosparser`)

### `parse_show_version`

Parses the output of `show version` from Cisco IOS and IOS-XE devices. Supports single devices and stacked switches.

```python
from netboxcustom.iosparser import parse_show_version

show = """
Model Number                       : WS-C2960X-48FPD-L
System Serial Number               : FOC1234ABCD
Base Ethernet MAC Address          : aa:bb:cc:dd:ee:ff
"""

result = parse_show_version(show)
# [{'serial': 'FOC1234ABCD', 'device_type': 'WS-C2960X-48FPD-L', 'base_mac': 'aa:bb:cc:dd:ee:ff', 'slot': 1}]
```

**Stack example** (two Catalyst 9500s — from `test_data/sh-version-ios-xe.txt`):

```python
result = parse_show_version(open("test_data/sh-version-ios-xe.txt").read())
# [
#     {'serial': 'FCW2233FFAB', 'device_type': 'C9500-40X', 'base_mac': 'ac:a0:a8:ad:b5:80', 'slot': 1},
#     {'serial': 'FCW1234F88V', 'device_type': 'C9500-40X', 'base_mac': '70:65:a9:ad:a0:60', 'slot': 2},
# ]
```

**Returns** (each entry):

| Key | Type | Description |
|---|---|---|
| `serial` | str | System serial number |
| `device_type` | str | Model number |
| `base_mac` | str | Base Ethernet MAC address |
| `slot` | int | Stack slot (1-based) |

Returns `[]` if the number of found models and serials don't match.

---

### `parse_hostname`

Parses hostname from `show running-config | include hostname` output. Accepts a string or a list of lines.

```python
from netboxcustom.iosparser import parse_hostname

parse_hostname("hostname CORE-SW-01")
# "CORE-SW-01"

parse_hostname(["interface Gi0/0", "hostname DIST-SW", "end"])
# "DIST-SW"

parse_hostname("interface Gi0/0\nhostname CORE-SW\nend")
# "CORE-SW"

parse_hostname("no hostname line here")
# ""
```

---

## Exceptions

All exceptions inherit from `NetboxCustomBase` and have a `.message`, `.status_code`, and `.as_dict()` method.

| Exception | Status | When raised |
|---|---|---|
| `NetboxCustomNotFoundError` | 404 | Resource not found by serial, slug, etc. |
| `NetboxCustomLookupError` | 404 | Lookup failed (no result, ambiguous result) |
| `NetboxCustomFieldMissing` | 404 | Expected custom field not present on object |
| `NetboxCustomCreateDeviceError` | 400 | Device creation failed |
| `NetboxCustomCreateVirtualChassisError` | 400 | Virtual Chassis creation failed |
| `NetboxCustomGeneralError` | 400 | Catch-all for other errors |

```python
from netboxcustom.netboxcustom import NetboxCustomNotFoundError

try:
    device = device_exists_bySerial(nb, "UNKNOWN-SERIAL")
except NetboxCustomNotFoundError as e:
    print(e)           # "Serial UNKNOWN-SERIAL not found in Netbox! (404)"
    print(e.as_dict()) # {'message': '...', 'status_code': 404, 'status': '1'}
```

---

## Running Tests

Tests require a running NetBox instance and the following environment variables:

```bash
export NETBOX_ENDPOINT="https://netbox.example.com"
export NETBOX_TOKEN="your-token"
```

```bash
# Run all tests
pytest -v

# Only unit tests (no NetBox required)
pytest tests/test_iosparser.py -v

# Async integration tests
pytest tests/test_async.py -v

# Collect tests without running
pytest tests/test_async.py --co
```
