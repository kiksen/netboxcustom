import re
from typing import Any

import jmespath

from .models import ScopeType


def build_stack_hostname(hostname: str, stack_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Baut Stack-Hostnamen für eine Liste von Devices auf (Suffix -1, -2, ...).
    Ein eventuell vorhandenes Nummernsuffix im Hostnamen (z.B. HOSTNAME-1) wird entfernt.

    :param hostname: Basis-Hostname
    :type hostname: str
    :param stack_list: Liste von Dicts mit Device-Informationen (benötigt 'slot')
    :type stack_list: list[dict[str, Any]]
    :return: Aktualisierte stack_list mit angepassten Namen
    :rtype: list[dict[str, Any]]
    """
    # allen hostnamen ein -1, -2, ... anhängen falls wir einen stack haben
    if len(stack_list) > 1:
        # if "-" at the end of hostname:
        # stakck name remove -1 oder -2. e.g. HOSTNAME-1 or HOSTNAME-SW-2
        # use re.sub damit HOSTNAME-SW-1 auch funktioniert
        if re.search(r"-\d+$", hostname):
            # clean hostname without -1
            hostname = re.sub(r"-\d+$", "", hostname)

        for member in stack_list:
            member["name"] = f"{hostname}-{member['slot']}"

    return stack_list


def has_object_tenant(obj: dict[str, Any]) -> bool:
    """
    General function. Checks if an netbox object has a tenant assigned
    """
    if jmespath.search("tenant.id", obj):
        return True

    return False


def has_object_scope(obj: dict[str, Any], scope_type: ScopeType | None = None) -> bool:
    """
    Checks if a netbox object has a scope e.g. used on a prefix object.
    But the scope object needs to have an id, to be a valid scope!
    """

    # if scope type is not found -> raus
    if not jmespath.search("scope_type", obj):
        return False

    # if scope_type check is set!
    if scope_type is not None:
        type_str = jmespath.search("scope_type", obj)

        if scope_type != type_str:
            return False

    # scope_type found! check if scope has an id (and is not None)
    if jmespath.search("scope.id", obj):
        return True

    return False
