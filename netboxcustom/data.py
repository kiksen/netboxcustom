from enum import StrEnum

device_roll_slug: str = "access"
network_roll_slug: str = "network-management"
default_config_template_id: int = 1
anonymous_config_template: int = 5

switch_position: dict = {
    1: 15,
    2: 14,
    3: 13,
    4: 12,
    5: 10,
    6: 9,
    7: 8,
    8: 7,
    9: 6,
    10: 5,
}
device_default_names: list[str] = ["switch", "router"]


class ScopeType(StrEnum):
    """
    Gültige scope_type-Werte für NetBox IPAM Prefixes (ab v4.2).
    Format: <app_label>.<model_name>
    """

    REGION = "dcim.region"
    SITE_GROUP = "dcim.sitegroup"
    SITE = "dcim.site"
    LOCATION = "dcim.location"
