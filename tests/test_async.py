"""
Integration-Tests für AsyncNetboxCustom.
Erfordert NETBOX_ENDPOINT und NETBOX_TOKEN als Umgebungsvariablen.
"""

import os

import pytest

from netboxcustom import (
    NetboxCustomCreateDeviceError,
    NetboxCustomLookupError,
    NetboxCustomNotFoundError,
)
from netboxcustom.helper import has_object_scope, has_object_tenant
from netboxcustom.models import DeviceType, ScopeType

SITE_SLUG = "TEST-SITE"
ROLE_SLUG = "access"
DEVICE_TYPE = "TEST-C9200CX-12P-2X2G"
KNOWN_SITE_IP = "99.99.99.1"
SERIAL_PREFIX = "TEST-ASYNC-"
FIRMWARE_MODEL = os.environ.get("TEST_FIRMWARE_MODEL", DEVICE_TYPE)


def _dev(suffix: str, name: str = "async-test", device_type: str = DEVICE_TYPE) -> dict:
    return {"name": name, "device_type": device_type, "serial": f"{SERIAL_PREFIX}{suffix}"}


# ---------------------------------------------------------------------------
# Token-Erkennung
# ---------------------------------------------------------------------------


class TestNbLogin:
    async def test_v1_token_uses_token_header(self, anb):
        token = os.environ.get("NETBOX_TOKEN", "")
        if not token.startswith("nbt_"):
            assert anb._client.headers["authorization"].startswith("Token ")

    async def test_v2_token_uses_bearer_header(self, anb):
        token = os.environ.get("NETBOX_TOKEN", "")
        if token.startswith("nbt_"):
            assert anb._client.headers["authorization"].startswith("Bearer ")


# ---------------------------------------------------------------------------
# get_site_list
# ---------------------------------------------------------------------------


class TestGetSiteList:
    async def test_returns_list(self, anb):
        result = await anb.get_site_list()
        assert isinstance(result, list)

    async def test_each_entry_has_required_keys(self, anb):
        result = await anb.get_site_list()
        assert len(result) > 0
        for entry in result:
            for key in ("id", "name", "slug", "gns", "long", "description", "display"):
                assert key in entry, f"Key '{key}' fehlt in Site-Eintrag"

    async def test_filter_by_known_slug(self, anb):
        result = await anb.get_site_list({"slug": SITE_SLUG})
        assert len(result) >= 1
        assert all(s["slug"] == SITE_SLUG for s in result)

    async def test_filter_by_unknown_slug_returns_empty(self, anb):
        result = await anb.get_site_list({"slug": "this-slug-does-not-exist-xyz"})
        assert result == []

    async def test_long_field_format(self, anb):
        result = await anb.get_site_list({"slug": SITE_SLUG})
        site = result[0]
        assert site["long"] == f"{site['gns']}-{site['slug']}"


# ---------------------------------------------------------------------------
# device_exists_bySerial
# ---------------------------------------------------------------------------


class TestDeviceExistsBySerial:
    async def test_raises_not_found_for_unknown_serial(self, anb):
        with pytest.raises(NetboxCustomNotFoundError):
            await anb.device_exists_bySerial("SERIAL-DOES-NOT-EXIST-XYZ-123")

    async def test_returns_dict_with_correct_serial(self, anb, cleanup_devices):
        serial = f"{SERIAL_PREFIX}ES-001"
        cleanup_devices.append(serial)
        await anb.createDevices(
            device_info_list=[_dev("ES-001", name="async-serial-check")],
            site_slug=SITE_SLUG,
            role_slug=ROLE_SLUG,
        )
        result = await anb.device_exists_bySerial(serial)
        assert result["serial"] == serial

    async def test_result_is_dict(self, anb, cleanup_devices):
        serial = f"{SERIAL_PREFIX}ES-002"
        cleanup_devices.append(serial)
        await anb.createDevices(
            device_info_list=[_dev("ES-002", name="async-dict-check")],
            site_slug=SITE_SLUG,
            role_slug=ROLE_SLUG,
        )
        result = await anb.device_exists_bySerial(serial)
        assert isinstance(result, dict)
        assert "id" in result

    async def test_raises_not_found_on_wrong_device_type(self, anb, cleanup_devices):
        serial = f"{SERIAL_PREFIX}ES-003"
        cleanup_devices.append(serial)
        await anb.createDevices(
            device_info_list=[_dev("ES-003", name="async-type-mismatch")],
            site_slug=SITE_SLUG,
            role_slug=ROLE_SLUG,
        )
        with pytest.raises(NetboxCustomNotFoundError, match="device type doesn't match"):
            await anb.device_exists_bySerial(serial, device_type="WRONG-MODEL-XYZ")

    async def test_returns_device_with_correct_type(self, anb, cleanup_devices):
        serial = f"{SERIAL_PREFIX}ES-004"
        cleanup_devices.append(serial)
        await anb.createDevices(
            device_info_list=[_dev("ES-004", name="async-type-match")],
            site_slug=SITE_SLUG,
            role_slug=ROLE_SLUG,
        )
        result = await anb.device_exists_bySerial(serial, device_type=DEVICE_TYPE)
        assert result["device_type"]["model"] == DEVICE_TYPE


# ---------------------------------------------------------------------------
# createDevices
# ---------------------------------------------------------------------------


class TestCreateDevicesSingle:
    async def test_creates_single_device(self, anb, cleanup_devices):
        serial = f"{SERIAL_PREFIX}CD-001"
        cleanup_devices.append(serial)
        result = await anb.createDevices(
            device_info_list=[_dev("CD-001", name="async-single")],
            site_slug=SITE_SLUG,
            role_slug=ROLE_SLUG,
        )
        assert len(result) == 1
        assert result[0]["serial"] == serial

    async def test_created_device_has_correct_site(self, anb, cleanup_devices):
        serial = f"{SERIAL_PREFIX}CD-002"
        cleanup_devices.append(serial)
        result = await anb.createDevices(
            device_info_list=[_dev("CD-002", name="async-site-check")],
            site_slug=SITE_SLUG,
            role_slug=ROLE_SLUG,
        )
        assert result[0]["site"]["slug"] == SITE_SLUG

    async def test_created_device_has_correct_role(self, anb, cleanup_devices):
        serial = f"{SERIAL_PREFIX}CD-003"
        cleanup_devices.append(serial)
        result = await anb.createDevices(
            device_info_list=[_dev("CD-003", name="async-role-check")],
            site_slug=SITE_SLUG,
            role_slug=ROLE_SLUG,
        )
        assert result[0]["role"]["slug"] == ROLE_SLUG

    async def test_default_name_gets_serial_appended(self, anb, cleanup_devices):
        serial = f"{SERIAL_PREFIX}CD-004"
        cleanup_devices.append(serial)
        result = await anb.createDevices(
            device_info_list=[{"name": "switch", "device_type": DEVICE_TYPE, "serial": serial}],
            site_slug=SITE_SLUG,
            role_slug=ROLE_SLUG,
        )
        assert result[0]["name"] == f"switch-{serial}"

    async def test_device_findable_after_creation(self, anb, cleanup_devices):
        serial = f"{SERIAL_PREFIX}CD-005"
        cleanup_devices.append(serial)
        await anb.createDevices(
            device_info_list=[_dev("CD-005", name="async-find-after-create")],
            site_slug=SITE_SLUG,
            role_slug=ROLE_SLUG,
        )
        found = await anb.device_exists_bySerial(serial)
        assert found["serial"] == serial

    async def test_extra_create_args_applied(self, anb, cleanup_devices):
        serial = f"{SERIAL_PREFIX}CD-006"
        cleanup_devices.append(serial)
        result = await anb.createDevices(
            device_info_list=[_dev("CD-006", name="async-extra-args")],
            site_slug=SITE_SLUG,
            role_slug=ROLE_SLUG,
            device_create_args={"comments": "pytest-async-created"},
        )
        assert result[0]["comments"] == "pytest-async-created"


class TestCreateDevicesIdempotency:
    async def test_existing_device_reused_not_duplicated(self, anb, cleanup_devices):
        serial = f"{SERIAL_PREFIX}ID-001"
        cleanup_devices.append(serial)
        result1 = await anb.createDevices(
            device_info_list=[_dev("ID-001", name="async-idem")],
            site_slug=SITE_SLUG,
            role_slug=ROLE_SLUG,
        )
        result2 = await anb.createDevices(
            device_info_list=[_dev("ID-001", name="async-idem")],
            site_slug=SITE_SLUG,
            role_slug=ROLE_SLUG,
        )
        assert result1[0]["id"] == result2[0]["id"]


class TestCreateDevicesStack:
    async def test_creates_two_devices_for_stack(self, anb, cleanup_devices):
        s1, s2 = f"{SERIAL_PREFIX}SK-001", f"{SERIAL_PREFIX}SK-002"
        cleanup_devices.extend([s1, s2])
        result = await anb.createDevices(
            device_info_list=[
                {"name": "async-stack", "device_type": DEVICE_TYPE, "serial": s1, "slot": 1},
                {"name": "async-stack", "device_type": DEVICE_TYPE, "serial": s2, "slot": 2},
            ],
            site_slug=SITE_SLUG,
            role_slug=ROLE_SLUG,
        )
        assert len(result) == 2

    async def test_stack_devices_get_numbered_names(self, anb, cleanup_devices):
        s1, s2 = f"{SERIAL_PREFIX}SK-003", f"{SERIAL_PREFIX}SK-004"
        cleanup_devices.extend([s1, s2])
        result = await anb.createDevices(
            device_info_list=[
                {"name": "async-stackname", "device_type": DEVICE_TYPE, "serial": s1, "slot": 1},
                {"name": "async-stackname", "device_type": DEVICE_TYPE, "serial": s2, "slot": 2},
            ],
            site_slug=SITE_SLUG,
            role_slug=ROLE_SLUG,
        )
        names = {d["name"] for d in result}
        assert "async-stackname-1" in names
        assert "async-stackname-2" in names

    async def test_vc_created_when_flag_set(self, anb, cleanup_devices, nb):
        s1, s2 = f"{SERIAL_PREFIX}SK-005", f"{SERIAL_PREFIX}SK-006"
        cleanup_devices.extend([s1, s2])
        result = await anb.createDevices(
            device_info_list=[
                {"name": "async-vc", "device_type": DEVICE_TYPE, "serial": s1, "slot": 1},
                {"name": "async-vc", "device_type": DEVICE_TYPE, "serial": s2, "slot": 2},
            ],
            site_slug=SITE_SLUG,
            role_slug=ROLE_SLUG,
            create_vc=True,
        )
        reloaded = [nb.dcim.devices.get(id=d["id"]) for d in result]
        assert all(d.virtual_chassis is not None for d in reloaded)

    async def test_no_vc_when_flag_false(self, anb, cleanup_devices, nb):
        s1, s2 = f"{SERIAL_PREFIX}SK-007", f"{SERIAL_PREFIX}SK-008"
        cleanup_devices.extend([s1, s2])
        result = await anb.createDevices(
            device_info_list=[
                {"name": "async-novc", "device_type": DEVICE_TYPE, "serial": s1, "slot": 1},
                {"name": "async-novc", "device_type": DEVICE_TYPE, "serial": s2, "slot": 2},
            ],
            site_slug=SITE_SLUG,
            role_slug=ROLE_SLUG,
            create_vc=False,
        )
        reloaded = [nb.dcim.devices.get(id=d["id"]) for d in result]
        assert all(d.virtual_chassis is None for d in reloaded)


class TestCreateDevicesErrors:
    async def test_raises_on_invalid_site_slug(self, anb):
        with pytest.raises(NetboxCustomCreateDeviceError, match="site_slug"):
            await anb.createDevices(
                device_info_list=[_dev("ERR-001", name="async-bad-site")],
                site_slug="does-not-exist-xxx",
                role_slug=ROLE_SLUG,
            )

    async def test_raises_on_invalid_role_slug(self, anb):
        with pytest.raises(NetboxCustomCreateDeviceError, match="role_slug"):
            await anb.createDevices(
                device_info_list=[_dev("ERR-002", name="async-bad-role")],
                site_slug=SITE_SLUG,
                role_slug="does-not-exist-xxx",
            )

    async def test_raises_on_invalid_device_type(self, anb):
        with pytest.raises(NetboxCustomCreateDeviceError, match="Device_Type"):
            await anb.createDevices(
                device_info_list=[
                    {"name": "async-bad-dtype", "device_type": "INVALID-MODEL-XYZ", "serial": f"{SERIAL_PREFIX}ERR-003"}
                ],
                site_slug=SITE_SLUG,
                role_slug=ROLE_SLUG,
            )

    async def test_empty_device_list_raises_index_error(self, anb):
        with pytest.raises(IndexError):
            await anb.createDevices(device_info_list=[], site_slug=SITE_SLUG, role_slug=ROLE_SLUG)

    async def test_none_device_list_raises_type_error(self, anb):
        with pytest.raises(TypeError):
            await anb.createDevices(device_info_list=None, site_slug=SITE_SLUG, role_slug=ROLE_SLUG)


# ---------------------------------------------------------------------------
# lookup_site_by_ip
# ---------------------------------------------------------------------------


class TestLookupSiteByIp:
    async def test_raises_for_ip_not_in_any_prefix(self, anb):
        with pytest.raises(NetboxCustomLookupError):
            await anb.lookup_site_by_ip("240.0.0.1")

    async def test_returns_site_slug_for_known_ip(self, anb):
        result = await anb.lookup_site_by_ip(KNOWN_SITE_IP)
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# lookup_firmware_by_model_type
# ---------------------------------------------------------------------------


class TestLookupFirmwareByModelType:
    async def test_raises_for_unknown_model(self, anb):
        with pytest.raises(NetboxCustomLookupError):
            await anb.lookup_firmware_by_model_type("MODEL-THAT-DOES-NOT-EXIST-XYZ")

    @pytest.mark.skipif(
        not os.environ.get("TEST_FIRMWARE_MODEL"),
        reason="TEST_FIRMWARE_MODEL nicht gesetzt",
    )
    async def test_returns_device_type_with_expected_fields(self, anb):
        result = await anb.lookup_firmware_by_model_type(FIRMWARE_MODEL)
        assert isinstance(result, DeviceType)
        assert result.firmware_filename is not None
        assert result.platform is not None
        assert result.flash is not None


# ---------------------------------------------------------------------------
# has_object_scope / has_object_tenant (Unit-Tests, kein NetBox nötig)
# ---------------------------------------------------------------------------


class TestHasObjectHelpers:
    def test_site_scope_detected(self):
        obj = {
            "scope_type": str(ScopeType.SITE),
            "scope": {"id": 1, "slug": "TEST-SITE"},
            "tenant": {"id": 42, "name": "TEST-TENANT"},
        }
        assert has_object_scope(obj, ScopeType.SITE) is True

    def test_wrong_scope_type_returns_false(self):
        obj = {"scope_type": str(ScopeType.SITE), "scope": {"id": 1}}
        assert has_object_scope(obj, ScopeType.REGION) is False

    def test_missing_scope_returns_false(self):
        obj = {"tenant": {"id": 1}}
        assert has_object_scope(obj, ScopeType.SITE) is False

    def test_tenant_present(self):
        obj = {"tenant": {"id": 42}}
        assert has_object_tenant(obj) is True

    def test_tenant_absent(self):
        obj = {"tenant": None}
        assert has_object_tenant(obj) is False

    def test_tenant_key_missing(self):
        obj = {"scope_type": str(ScopeType.SITE)}
        assert has_object_tenant(obj) is False
