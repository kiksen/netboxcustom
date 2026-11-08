from dataclasses import dataclass, field
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
    Returned by get_device_type / get_device_types
    """
    device_type: str
    firmware_custom_field: str
    firmware_filename: str = ""
    # optional second custom field (target version), empty if not requested or not set
    firmware_version: str = ""
    platform: str = ""
    flash: str = ""
    error: str = ""


@dataclass
class VcDevice:
    """
    Device inside a virtual chassis. ``device`` holds the complete NetBox device object.
    """
    id: int
    name: str
    vc_position: int | None = None
    vc_priority: int | None = None
    device: dict[str, Any] = field(default_factory=dict)


@dataclass
class VcMember(VcDevice):
    """
    Member of a virtual chassis, includes the VC master
    """
    master: VcDevice | None = None


@dataclass
class VirtualChassis:
    """
    Returned by get_vc_members_by_device_id
    """
    id: int
    name: str
    master: VcDevice | None = None
    members: list[VcMember] = field(default_factory=list)
