from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ScopeType(StrEnum):
    """
    Gültige scope_type-Werte für NetBox IPAM Prefixes (ab v4.2).
    Format: <app_label>.<model_name>
    """

    REGION = "dcim.region"
    SITE_GROUP = "dcim.sitegroup"
    SITE = "dcim.site"
    LOCATION = "dcim.location"



@dataclass
class LookupSiteByIp:
    """
    This class is returned from lookup_site_by_ip_full
    """
    site_slug: str
    api_filter: dict[str, Any]

    # returns the subnet which matches the IP
    subnet: str

    # return all subnets
    subnet_list: list[str]


@dataclass
class DeviceInfo:
    name: str
    serial: str
    device_type: str
    slot: int | None = None
    priority: int | None = None


@dataclass
class DeviceType:
    """
    Returned by lookup_firmware_by_model_type
    """
    device_type: str
    firmware_custom_field: str
    firmware_filename: str = ""
    platform: str = ""
    flash: str = ""
    error: str = ""
