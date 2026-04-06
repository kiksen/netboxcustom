"""Unit-Tests für iosparser.py — keine Netzwerkverbindung erforderlich."""
import pathlib

import pytest

from netboxcustom.iosparser import parse_hostname, parse_show_version

FIXTURES_DIR = pathlib.Path(__file__).parent.parent / "test_data"


@pytest.fixture(scope="module")
def show_version_ios_xe_stack() -> str:
    return (FIXTURES_DIR / "sh-version-ios-xe.txt").read_text()


# ---------------------------------------------------------------------------
# parse_show_version
# ---------------------------------------------------------------------------

SINGLE_SWITCH_SHOW = """
Model Number                       : WS-C2960X-48FPD-L
System Serial Number               : FOC1234ABCD
Base Ethernet MAC Address          : aa:bb:cc:dd:ee:ff
"""

SINGLE_SWITCH_SHOW_WITH_TRAILING_SPACES = """
Model Number                       : WS-C2960X-48FPD-L
System Serial Number               : FOC1234ABCD
Base Ethernet MAC Address          : aa:bb:cc:dd:ee:ff
"""


class TestParseShowVersion:

    def test_empty_string_returns_empty_list(self):
        assert parse_show_version("") == []

    def test_single_switch_returns_one_entry(self):
        result = parse_show_version(SINGLE_SWITCH_SHOW)
        assert len(result) == 1

    def test_single_switch_serial(self):
        result = parse_show_version(SINGLE_SWITCH_SHOW)
        assert result[0]["serial"] == "FOC1234ABCD"

    def test_single_switch_device_type(self):
        result = parse_show_version(SINGLE_SWITCH_SHOW)
        assert result[0]["device_type"] == "WS-C2960X-48FPD-L"

    def test_single_switch_mac(self):
        result = parse_show_version(SINGLE_SWITCH_SHOW)
        assert result[0]["base_mac"] == "aa:bb:cc:dd:ee:ff"

    def test_single_switch_slot_is_1(self):
        result = parse_show_version(SINGLE_SWITCH_SHOW)
        assert result[0]["slot"] == 1

    def test_trailing_whitespace_is_stripped(self):
        result = parse_show_version(SINGLE_SWITCH_SHOW_WITH_TRAILING_SPACES)
        assert result[0]["serial"] == "FOC1234ABCD"
        assert result[0]["device_type"] == "WS-C2960X-48FPD-L"
        assert result[0]["base_mac"] == "aa:bb:cc:dd:ee:ff"

    def test_stack_returns_two_entries(self, show_version_ios_xe_stack):
        result = parse_show_version(show_version_ios_xe_stack)
        assert len(result) == 2

    def test_stack_serials(self, show_version_ios_xe_stack):
        result = parse_show_version(show_version_ios_xe_stack)
        serials = [r["serial"] for r in result]
        assert "FCW2233FFG3" in serials
        assert "FCW1234F88V" in serials

    def test_stack_models(self, show_version_ios_xe_stack):
        result = parse_show_version(show_version_ios_xe_stack)
        assert all(r["device_type"] == "C9500-40X" for r in result)

    def test_stack_macs(self, show_version_ios_xe_stack):
        result = parse_show_version(show_version_ios_xe_stack)
        macs = [r["base_mac"] for r in result]
        assert "ac:a0:a8:ad:b5:80" in macs
        assert "70:65:a9:ad:a0:60" in macs

    def test_stack_slot_numbering(self, show_version_ios_xe_stack):
        result = parse_show_version(show_version_ios_xe_stack)
        slots = [r["slot"] for r in result]
        assert slots == [1, 2]

    def test_mismatched_model_serial_count_returns_empty(self):
        show = """
Model Number                       : WS-C2960X-48FPD-L
Model Number                       : WS-C2960X-24PD-L
System Serial Number               : FOC1234ABCD
Base Ethernet MAC Address          : aa:bb:cc:dd:ee:ff
"""
        assert parse_show_version(show) == []


# ---------------------------------------------------------------------------
# parse_hostname
# ---------------------------------------------------------------------------


class TestParseHostname:

    def test_string_input(self):
        assert parse_hostname("hostname MYROUTER") == "MYROUTER"

    def test_list_input(self):
        assert parse_hostname(["blabla", "hostname TEST-sw", "end"]) == "TEST-sw"

    def test_hostname_with_hyphens(self):
        assert parse_hostname("hostname SZDEMHGX-01") == "SZDEMHGX-01"

    def test_hostname_buried_in_multiline_string(self):
        show = "interface Gi0/0\n ip address 1.2.3.4\nhostname CORE-SW\nend"
        assert parse_hostname(show) == "CORE-SW"

    def test_case_insensitive_keyword(self):
        assert parse_hostname("HOSTNAME myrouter") == "myrouter"

    def test_no_hostname_line_returns_empty(self):
        assert parse_hostname("interface Gi0/0\n ip address 1.2.3.4\n") == ""

    def test_empty_string_returns_empty(self):
        assert parse_hostname("") == ""

    def test_empty_list_returns_empty(self):
        assert parse_hostname([]) == ""
