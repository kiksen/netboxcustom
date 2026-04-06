"""
Integration-Tests für createDevices().
Erfordert NETBOX_ENDPOINT und NETBOX_TOKEN als Umgebungsvariablen.
"""
import pytest
import pynetbox

from netboxcustom.netboxcustom import (
    createDevices,
    NetboxCustomCreateDeviceError,
    NetboxCustomNotFoundError,
    device_exists_bySerial,
)

# Fixtures – müssen in der Netbox-Testinstanz vorhanden sein
SITE_SLUG = "TEST-SITE"
ROLE_SLUG = "access"
DEVICE_TYPE = "TEST-C9200CX-12P-2X2G"
SERIAL_PREFIX = "TEST-CD-"


# ---------------------------------------------------------------------------
# Hilfsfunktion
# ---------------------------------------------------------------------------

def _device_info(suffix: str, name: str = "test-device", device_type: str = DEVICE_TYPE) -> dict:
    return {
        "name": name,
        "device_type": device_type,
        "serial": f"{SERIAL_PREFIX}{suffix}",
    }


# ---------------------------------------------------------------------------
# Tests: Erfolgsfälle
# ---------------------------------------------------------------------------

class TestCreateDeviceSingle:

    def test_creates_single_device(self, nb, cleanup_devices):
        serial = f"{SERIAL_PREFIX}001"
        cleanup_devices.append(serial)

        device_info = [_device_info("001", name="pytest-single")]
        result = createDevices(nb, device_info, site_slug=SITE_SLUG, role_slug=ROLE_SLUG)

        assert len(result) == 1
        assert result[0].serial == serial
        assert result[0].site.slug == SITE_SLUG

    def test_created_device_has_correct_role(self, nb, cleanup_devices):
        serial = f"{SERIAL_PREFIX}002"
        cleanup_devices.append(serial)

        device_info = [_device_info("002", name="pytest-role-check")]
        result = createDevices(nb, device_info, site_slug=SITE_SLUG, role_slug=ROLE_SLUG)

        assert result[0].role.slug == ROLE_SLUG

    def test_created_device_has_correct_device_type(self, nb, cleanup_devices):
        serial = f"{SERIAL_PREFIX}003"
        cleanup_devices.append(serial)

        device_info = [_device_info("003", name="pytest-dtype-check")]
        result = createDevices(nb, device_info, site_slug=SITE_SLUG, role_slug=ROLE_SLUG)

        assert result[0].device_type.model == DEVICE_TYPE

    def test_device_exists_in_netbox_after_creation(self, nb, cleanup_devices):
        serial = f"{SERIAL_PREFIX}004"
        cleanup_devices.append(serial)

        device_info = [_device_info("004", name="pytest-exists-check")]
        createDevices(nb, device_info, site_slug=SITE_SLUG, role_slug=ROLE_SLUG)

        found = device_exists_bySerial(nb, serial_number=serial)
        assert found is not None
        assert found.serial == serial

    def test_default_name_gets_enriched_with_serial(self, nb, cleanup_devices):
        """Devices mit einem 'default name' (z.B. 'switch') sollen die Seriennummer bekommen."""
        serial = f"{SERIAL_PREFIX}005"
        cleanup_devices.append(serial)

        device_info = [{"name": "switch", "device_type": DEVICE_TYPE, "serial": serial}]
        result = createDevices(nb, device_info, site_slug=SITE_SLUG, role_slug=ROLE_SLUG)

        assert result[0].name == f"switch-{serial}"

    def test_extra_create_args_are_applied(self, nb, cleanup_devices):
        """DEVICE_CREATE_ARGS sollen auf das erstellte Device übertragen werden."""
        serial = f"{SERIAL_PREFIX}006"
        cleanup_devices.append(serial)

        device_info = [_device_info("006", name="pytest-extra-args")]
        result = createDevices(
            nb,
            device_info,
            site_slug=SITE_SLUG,
            role_slug=ROLE_SLUG,
            device_create_args={"comments": "pytest-created"},
        )

        assert result[0].comments == "pytest-created"


class TestCreateDeviceIdempotency:

    def test_existing_device_is_reused_not_duplicated(self, nb, cleanup_devices):
        """Wenn ein Device mit gleicher Seriennummer bereits existiert, darf kein Duplikat entstehen."""
        serial = f"{SERIAL_PREFIX}010"
        cleanup_devices.append(serial)

        # Frische Dicts für jeden Aufruf – createDevices mutiert device_info (device_type → ID)
        result1 = createDevices(nb, [_device_info("010", name="pytest-idem")], site_slug=SITE_SLUG, role_slug=ROLE_SLUG)
        result2 = createDevices(nb, [_device_info("010", name="pytest-idem")], site_slug=SITE_SLUG, role_slug=ROLE_SLUG)

        assert len(result1) == 1
        assert len(result2) == 1
        assert result1[0].id == result2[0].id

    def test_existing_device_found_by_serial_and_type(self, nb, cleanup_devices):
        serial = f"{SERIAL_PREFIX}011"
        cleanup_devices.append(serial)

        device_info = [_device_info("011", name="pytest-serial-type")]
        createDevices(nb, device_info, site_slug=SITE_SLUG, role_slug=ROLE_SLUG)

        found = device_exists_bySerial(nb, serial_number=serial, device_type=DEVICE_TYPE)
        assert found.serial == serial


# ---------------------------------------------------------------------------
# Tests: Stack / Virtual Chassis
# ---------------------------------------------------------------------------

class TestCreateDeviceStack:

    def test_creates_two_devices_for_stack(self, nb, cleanup_devices):
        serial1 = f"{SERIAL_PREFIX}020"
        serial2 = f"{SERIAL_PREFIX}021"
        cleanup_devices.extend([serial1, serial2])

        device_info = [
            {"name": "pytest-stack", "device_type": DEVICE_TYPE, "serial": serial1, "slot": 1},
            {"name": "pytest-stack", "device_type": DEVICE_TYPE, "serial": serial2, "slot": 2},
        ]
        result = createDevices(nb, device_info, site_slug=SITE_SLUG, role_slug=ROLE_SLUG)

        assert len(result) == 2

    def test_stack_devices_get_numbered_names(self, nb, cleanup_devices):
        serial1 = f"{SERIAL_PREFIX}022"
        serial2 = f"{SERIAL_PREFIX}023"
        cleanup_devices.extend([serial1, serial2])

        device_info = [
            {"name": "pytest-stackname", "device_type": DEVICE_TYPE, "serial": serial1, "slot": 1},
            {"name": "pytest-stackname", "device_type": DEVICE_TYPE, "serial": serial2, "slot": 2},
        ]
        result = createDevices(nb, device_info, site_slug=SITE_SLUG, role_slug=ROLE_SLUG)

        names = {d.name for d in result}
        assert "pytest-stackname-1" in names
        assert "pytest-stackname-2" in names

    def test_stack_vc_is_created_when_flag_set(self, nb, cleanup_devices):
        serial1 = f"{SERIAL_PREFIX}024"
        serial2 = f"{SERIAL_PREFIX}025"
        cleanup_devices.extend([serial1, serial2])

        device_info = [
            {"name": "pytest-vc", "device_type": DEVICE_TYPE, "serial": serial1, "slot": 1},
            {"name": "pytest-vc", "device_type": DEVICE_TYPE, "serial": serial2, "slot": 2},
        ]
        result = createDevices(
            nb, device_info, site_slug=SITE_SLUG, role_slug=ROLE_SLUG, create_vc=True
        )

        # Nach VC-Erstellung müssen wir die Objekte neu laden
        reloaded = [nb.dcim.devices.get(id=d.id) for d in result]
        assert all(d.virtual_chassis is not None for d in reloaded)

    def test_stack_no_vc_created_when_flag_false(self, nb, cleanup_devices):
        serial1 = f"{SERIAL_PREFIX}026"
        serial2 = f"{SERIAL_PREFIX}027"
        cleanup_devices.extend([serial1, serial2])

        device_info = [
            {"name": "pytest-novc", "device_type": DEVICE_TYPE, "serial": serial1, "slot": 1},
            {"name": "pytest-novc", "device_type": DEVICE_TYPE, "serial": serial2, "slot": 2},
        ]
        result = createDevices(
            nb, device_info, site_slug=SITE_SLUG, role_slug=ROLE_SLUG, create_vc=False
        )

        reloaded = [nb.dcim.devices.get(id=d.id) for d in result]
        assert all(d.virtual_chassis is None for d in reloaded)


# ---------------------------------------------------------------------------
# Tests: Fehlerfälle
# ---------------------------------------------------------------------------

class TestCreateDeviceErrors:

    def test_raises_on_invalid_site_slug(self, nb):
        device_info = [_device_info("ERR-001", name="pytest-bad-site")]
        with pytest.raises(NetboxCustomCreateDeviceError, match="site_slug"):
            createDevices(nb, device_info, site_slug="does-not-exist-xxx", role_slug=ROLE_SLUG)

    def test_raises_on_invalid_role_slug(self, nb):
        device_info = [_device_info("ERR-002", name="pytest-bad-role")]
        with pytest.raises(NetboxCustomCreateDeviceError, match="role_slug"):
            createDevices(nb, device_info, site_slug=SITE_SLUG, role_slug="does-not-exist-xxx")

    def test_raises_on_invalid_device_type(self, nb):
        device_info = [
            {
                "name": "pytest-bad-dtype",
                "device_type": "INVALID-MODEL-XYZ",
                "serial": f"{SERIAL_PREFIX}ERR-003",
            }
        ]
        with pytest.raises(NetboxCustomCreateDeviceError, match="Device_Type"):
            createDevices(nb, device_info, site_slug=SITE_SLUG, role_slug=ROLE_SLUG)

    def test_empty_device_list_raises_index_error(self, nb):
        """createDevices() wirft bei leerer Liste einen IndexError (bekannter Bug in build_stack_hostname)."""
        with pytest.raises(IndexError):
            createDevices(nb, [], site_slug=SITE_SLUG, role_slug=ROLE_SLUG)

    def test_none_device_list_raises_index_error(self, nb):
        """None wird intern zu [] normalisiert, dann gleicher IndexError wie bei leerem Array."""
        with pytest.raises(IndexError):
            createDevices(nb, None, site_slug=SITE_SLUG, role_slug=ROLE_SLUG)

    def test_device_exists_raises_on_wrong_serial(self, nb):
        with pytest.raises(NetboxCustomNotFoundError):
            device_exists_bySerial(nb, serial_number="SERIAL-THAT-DOES-NOT-EXIST-XYZ")
