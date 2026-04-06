# from pyats_genie_command_parse import GenieCommandParse
# parse_obj = GenieCommandParse(nos='ios')
# data = parse_obj.parse_file(show_command='show version', file_name_and_path='./show_version.txt')
# print(data)

import re
from typing import Any

from rich import print as print


def parse_show_version(show: str) -> list[dict[str, Any]]:
    """
    parses show version ios/ios-xe output. Supports stacked switches.
    returns a list which is for netboxcustom.build_stack_hostname and create Devcie by List
    Return: list of dicts
    """
    output = list()

    model_matches = re.findall(
        r"Model Number\s*:\s*(.*)$", show, re.MULTILINE | re.IGNORECASE
    )
    serial_matches = re.findall(
        r"System Serial Number\s*:\s*(.*)$", show, re.MULTILINE | re.IGNORECASE
    )
    mac_matches = re.findall(
        r"Base ethernet MAC Address\s*:\s*(.*)$", show, re.MULTILINE | re.IGNORECASE
    )

    # print(model_matches)
    # print(serial_matches)

    if len(model_matches) == len(serial_matches):
        for index, m in enumerate(model_matches):
            output.append(
                {
                    "serial": serial_matches[index].strip(),
                    "device_type": m.strip(),
                    "base_mac": mac_matches[index].strip(),
                    "slot": index + 1,
                }
            )

    return output


def parse_hostname(show_result: str | list[str]) -> str:
    """
    parses show running | inc hostname
    show_result can be a string or a list of strings

    returns the hostname as string. If the hostname was not found an empty string is returned

    """
    if isinstance(show_result, list):
        result = "\n".join(show_result)
    else:
        result = show_result

    hostname = ""
    m = re.search(
        r"hostname ([A-Za-z0-9-]+)", result, flags=re.IGNORECASE | re.MULTILINE
    )

    if m:
        hostname = m.group(1)

    return hostname


if __name__ == "__main__":

    # with open("sh-version-ios-xe.txt", "r") as f:
    #     show = f.read()

    # # with open("sh-version-ios3.txt", "r") as f:
    # #     show = f.read()

    # stack_list = parse_show_version(show)

    hostname = "SZDEMHGX-"

    show_result = """
    blabla
    asdasdf
    hostname TEST-de
    asdfasdf
    """

    show_result = show_result.split("\n")

    hostname = parse_hostname(show_result)

    # System Serial.*\n
    pass
