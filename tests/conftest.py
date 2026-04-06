import os

import pynetbox
import pytest

from netboxcustom.netboxcustom import ScopeType, nb_login


@pytest.fixture(scope="session")
def nb():
    endpoint = os.environ.get("NETBOX_ENDPOINT", "")
    token = os.environ.get("NETBOX_TOKEN", "")
    assert endpoint, "NETBOX_ENDPOINT env var nicht gesetzt"
    assert token, "NETBOX_TOKEN env var nicht gesetzt"
    return nb_login(endpoint, token)


@pytest.fixture(scope="session", autouse=True)
def ensure_netbox_testdata(nb):
    """Stellt sicher, dass alle für die Tests benötigten NetBox-Objekte existieren.
    Legt fehlende Objekte an, löscht sie aber nicht."""

    # Site
    site = nb.dcim.sites.get(slug="TEST-SITE")
    if not site:
        site = nb.dcim.sites.create(name="TEST-SITE", slug="TEST-SITE")

    # Device Role
    role = nb.dcim.device_roles.get(slug="access")
    if not role:
        nb.dcim.device_roles.create(name="access", slug="access", color="000000")

    # Manufacturer (Voraussetzung für Device Type)
    manufacturer = nb.dcim.manufacturers.get(slug="test-manufacturer")
    if not manufacturer:
        manufacturer = nb.dcim.manufacturers.create(
            name="TEST-MANUFACTURER", slug="test-manufacturer"
        )

    # Device Type
    device_type = nb.dcim.device_types.get(model="TEST-C9200CX-12P-2X2G")
    if not device_type:
        nb.dcim.device_types.create(
            manufacturer=manufacturer.id,
            model="TEST-C9200CX-12P-2X2G",
            slug="test-c9200cx-12p-2x2g",
        )

    # Tenant
    tenant = nb.tenancy.tenants.get(name="TEST-TENANT")
    if not tenant:
        nb.tenancy.tenants.create(name="TEST-TENANT", slug="test-tenant")

    # Prefix für lookup_site_by_ip (99.99.99.1 → TEST-SITE)
    existing = list(nb.ipam.prefixes.filter(prefix="99.99.99.0/24"))
    if not existing:
        nb.ipam.prefixes.create(
            prefix="99.99.99.0/24",
            scope_type=str(ScopeType.SITE),
            scope_id=site.id,
        )


@pytest.fixture
def cleanup_devices(nb):
    """Löscht nach jedem Test alle Devices mit den übergebenen Seriennummern.
    VC-Mitgliedschaft wird vorher aufgelöst."""
    created_serials = []

    yield created_serials

    # Zuerst alle betroffenen VCs einsammeln und löschen
    vc_ids_to_delete = set()
    devices_to_delete = []

    for serial in created_serials:
        devices = list(nb.dcim.devices.filter(serial=serial))
        for device in devices:
            if device.virtual_chassis:
                vc_ids_to_delete.add(device.virtual_chassis.id)
            devices_to_delete.append(device)

    for vc_id in vc_ids_to_delete:
        vc = nb.dcim.virtual_chassis.get(id=vc_id)
        if vc:
            vc.delete()

    # Devices neu laden (VC-Referenz entfernt) und löschen
    for device in devices_to_delete:
        fresh = nb.dcim.devices.get(id=device.id)
        if fresh:
            fresh.delete()

    pass
