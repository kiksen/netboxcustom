import ipaddress
import os
import re
from enum import StrEnum
from typing import Any

import pynetbox
from pynetbox.core.response import Record

import netboxcustom.iosparser

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


def nb_login(NETBOX_ENDPOINT: str, NETBOX_TOKEN: str | None = None) -> pynetbox.api:
    """
    Verbindet mit der NetBox API.
    Falls kein NETBOX_TOKEN übergeben wird, wird die Umgebungsvariable NETBOX_TOKEN verwendet.

    :param NETBOX_ENDPOINT: URL des NetBox-Endpunkts
    :type NETBOX_ENDPOINT: str
    :param NETBOX_TOKEN: API-Token (optional, Fallback auf ENV)
    :type NETBOX_TOKEN: str | None
    :return: Verbundenes pynetbox API-Objekt
    :rtype: pynetbox.api
    """
    if NETBOX_TOKEN is None:
        token = os.environ.get("NETBOX_TOKEN")
    else:
        token = NETBOX_TOKEN

    return pynetbox.api(NETBOX_ENDPOINT, token=token)


class NetboxCustomBase(Exception):

    def __init__(self, message: str, **kwargs: dict[str, Any]):

        self.message = message
        self.status_code: int = 500
        self.extra = kwargs
        self.status = "1"  # soll String sein!

    def __str__(self):
        result = f"{self.message} ({self.status_code})"
        if self.extra:
            extra_str = " ["
            for k, v in self.extra.items():
                extra_str += f"{k}={v} "
            extra_str = extra_str.rstrip()
            extra_str += "]"
            result += extra_str
        return result

    def as_dict(self):
        result = {
            "message": self.message,
            "status_code": self.status_code,
            "status": self.status,
        }
        result.update(self.extra)
        return result


class NetboxCustomCreateVirtualChassisError(NetboxCustomBase):

    def __init__(self, message: str, **kwargs):
        self.message = message
        super().__init__(f"{message}", **kwargs)
        self.status_code = 400


class NetboxCustomCreateDeviceError(NetboxCustomBase):

    def __init__(self, message: str):
        self.message = message
        super().__init__(f"{message}")
        self.status_code = 400


class NetboxCustomLookupError(NetboxCustomBase):

    def __init__(self, message: str):
        self.message = message
        super().__init__(f"{message}")
        self.status_code = 404


class NetboxCustomNotFoundError(NetboxCustomBase):

    def __init__(self, message: str):
        self.message = message
        super().__init__(f"{message}")
        self.status_code = 404


class NetboxCustomFieldMissing(NetboxCustomBase):

    def __init__(self, message: str):
        self.message = message
        super().__init__(f"{message}")
        self.status_code = 404


# used to consolidate all other errors
class NetboxCustomGeneralError(NetboxCustomBase):
    def __init__(self, message: str):
        self.message = message
        super().__init__(f"{message}")
        self.status_code = 400


def lookup_firmware_by_model_type(
    nb: pynetbox.api,
    model_type: str,
    firmware_custom_field: str = "firmware_filename",
) -> dict[str, Any]:
    """
    Sucht Firmware-Informationen für einen Device-Typ in NetBox.

    :param nb: NetBox API-Objekt
    :type nb: pynetbox.api
    :param model_type: Modellbezeichnung des Gerätetyps
    :type model_type: str
    :param firmware_custom_field: Name des Custom Fields für den Dateinamen
    :type firmware_custom_field: str
    :return: Dict mit firmware_filename, platform und flash
    :rtype: dict[str, Any]
    """
    ret: dict = {}
    ret["firmware_filename"] = None
    ret["platform"] = None
    ret["flash"] = None
    #    ret['firmware_version'] = None

    try:
        model = nb.dcim.device_types.get(model=model_type)
    except ValueError as e:
        raise NetboxCustomLookupError(f"firmware_lookup {e}")

    if "firmware_filename" in model.custom_fields:
        ret[firmware_custom_field] = model.custom_fields[firmware_custom_field]
    else:
        # nichts gefunden. Raus
        raise NetboxCustomFieldMissing(
            f"Custom field 'firmware_filename' on device_type {model_type} not found!"
        )

    # if 'firmware_version' in model.custom_fields:
    #     ret['firmware_version'] = model.custom_fields['firmware_version']
    # else:
    #     raise NetboxCustomFieldMissing(f"Custom field 'firmware_version' on device_type {model_type} not found!")

    if model.default_platform:
        ret["platform"] = model.default_platform.name

        if ret["platform"] == "IOS-XE":
            ret["flash"] = "bootflash:"
        elif ret["platform"] == "IOS":
            ret["flash"] = "flash:"

    return ret


def lookup_site_by_ip(
    nb: pynetbox.api,
    device_ip: str = "0.0.0.0",
    api_filter: dict | None = None,
) -> str:
    """
    Gibt die Site zurück wenn die IP in einem Netzwerk-Management-Prefix gefunden wird.

    :param nb: NetBox API-Objekt
    :type nb: pynetbox.api
    :param device_ip: IP-Adresse des Geräts
    :type device_ip: str
    :param api_filter: Zusätzliche Filter für den Prefix-Lookup
    :type api_filter: dict | None
    :return: Site-Slug
    :rtype: str
    """

    if api_filter is None:
        prefix_list = list(nb.ipam.prefixes.filter(contains=device_ip))
    else:
        prefix_list = list(nb.ipam.prefixes.filter(contains=device_ip, **api_filter))

    if len(prefix_list) >= 1:
        # retun the last network in the list, it should be the one with the best "match"
        network = prefix_list[-1]

        if hasattr(network, "site"):
            return network.site.slug
        elif (
            hasattr(network, "scope")
            and hasattr(network, "scope_type")
            and network.scope_type == "dcim.site"
        ):
            return network.scope.slug
        else:
            raise NetboxCustomLookupError(f"{network} has no netbox site assigned!")
    else:
        raise NetboxCustomLookupError("No network found! Adjust api_filter!")

    # return ""


def update_subnetmask_for_ip(
    nb: pynetbox.api,
    ip_obj: pynetbox.models.ipam.IpAddresses,
    api_filter: dict | None = None,
) -> None:
    """
    Aktualisiert die Subnetzmaske einer IP auf die Maske des zugehörigen Prefixes.
    Der api_filter dient zum Lookup des Prefixes, aus dem die Site geholt wird.

    :param nb: NetBox API-Objekt
    :type nb: pynetbox.api
    :param ip_obj: NetBox IP-Objekt das aktualisiert werden soll
    :type ip_obj: pynetbox.models.ipam.IpAddresses
    :param api_filter: Zusätzliche Filter für den Prefix-Lookup
    :type api_filter: dict | None
    :return: None
    :rtype: None
    """

    if api_filter is None:
        prefix_list = list(nb.ipam.prefixes.filter(contains=ip_obj.address))
    else:
        prefix_list = list(
            nb.ipam.prefixes.filter(contains=ip_obj.address, **api_filter)
        )

    if len(prefix_list) >= 1:
        # retun the last network in the list, it should be the one with the best "match"
        prefix = prefix_list[-1]
    else:
        raise NetboxCustomLookupError("No network found! Adjust api_filter!")

    ipstr = ip_obj.address
    xtmp = ipstr.split("/")[0]
    ip_addr = ipaddress.ip_address(xtmp)
    ip_net = ipaddress.ip_network(ipstr, strict=False)

    prefix_mask = prefix.prefix.split("/")[1]

    # only hostmasks will be changed
    if ip_net.prefixlen == 32:
        # print(f"IP to check: {ip_addr} ({ip_net})   {prefix_mask}")
        ip_obj.address = f"{ip_addr.compressed}/{prefix_mask}"
        ip_obj.save()


def assign_tenant_to_ip(
    nb: pynetbox.api,
    ip_obj: pynetbox.models.ipam.IpAddresses,
    api_filter: dict | None = None,
    tenant_id: int | None = None,
) -> None:
    """
    Weist einer IP einen Tenant zu.
    Falls kein tenant_id übergeben wird, wird der Tenant über die Site der IP ermittelt.

    :param nb: NetBox API-Objekt
    :type nb: pynetbox.api
    :param ip_obj: NetBox IP-Objekt
    :type ip_obj: pynetbox.models.ipam.IpAddresses
    :param api_filter: Zusätzliche Filter für den Site-Lookup
    :type api_filter: dict | None
    :param tenant_id: ID des Tenants (optional)
    :type tenant_id: int | None
    :return: None
    :rtype: None
    """
    if not api_filter:
        api_filter = {}

    if tenant_id is None:
        site_str = lookup_site_by_ip(nb, ip_obj.address, api_filter=api_filter)

        site = nb.dcim.sites.get(slug=site_str)

        if not site:
            raise NetboxCustomLookupError(f"{site_str} not found!")

        if not has_site_tenant(site):
            raise NetboxCustomGeneralError("Site has no tenant assigned!")

        tenant_id = site.tenant.id

    ip_obj.tenant = tenant_id
    ip_obj.save()


def get_rendered_config_bySerial(nb: pynetbox.api, serial_number: str) -> str:
    """
    Liefert die gerenderte Konfiguration eines Geräts anhand der Seriennummer.

    :param nb: NetBox API-Objekt
    :type nb: pynetbox.api
    :param serial_number: Seriennummer des Geräts
    :type serial_number: str
    :return: Gerenderter Konfigurationstext
    :rtype: str
    """
    config = {}
    device = device_exists_bySerial(nb, serial_number=serial_number)

    # device not found
    if not device:
        raise NetboxCustomNotFoundError(f"Device not found by serial {serial_number}")

    try:
        config = nb.dcim.devices.get(id=device.id).render_config.create()
    except pynetbox.core.query.RequestError as e:
        raise NetboxCustomLookupError(f"{e}")

    if "content" in config:
        return config["content"]
    else:
        raise NetboxCustomLookupError(
            "No content found in netbox answer [get_rendered_config_bySerial]"
        )


def device_exists_bySerial(
    nb: pynetbox.api, serial_number: str, device_type: str | None = None
) -> pynetbox.models.dcim.Devices:
    """
    Prüft ob eine Seriennummer in NetBox existiert und lädt das Device.
    Wenn device_type übergeben wird, wird dieser zusätzlich geprüft.

    :param nb: NetBox API-Objekt
    :type nb: pynetbox.api
    :param serial_number: Seriennummer des Geräts
    :type serial_number: str
    :param device_type: Erwarteter Modelltyp (optional)
    :type device_type: str | None
    :return: NetBox Device-Objekt
    :rtype: pynetbox.models.dcim.Devices
    """

    device = None

    try:
        found_device = list(nb.dcim.devices.filter(serial=serial_number))
    except ValueError as e:
        raise NetboxCustomLookupError(f"[device_exists by Serial] {e}")

    # more than one device found
    if len(found_device) > 1:
        raise NetboxCustomLookupError(
            f"[device_exists by Serial]More than one device found for serial {serial_number}!"
        )

    # kein Device found
    if len(found_device) == 0:
        raise NetboxCustomNotFoundError(f"Serial {serial_number} not found in Netbox!")

    # one device found! Return - len is now one!
    device = found_device[0]

    # hier  prüfen ob der Model_Type stimmt!
    if device_type:
        if device.device_type.model == device_type:
            # der device_type entspricht dem device_type des gefundenen devices.
            return device
        else:
            raise NetboxCustomNotFoundError(
                f"[device_exists_bySerial] Serial number exists, but device type doesn't match! device:{device_type} netbox:{device.device_type.model}."
            )
    else:
        # der device_type wird nicht geprüft und es wird das gefundene Device zurückgegeben.
        return device


def device_delete_all_ips(
    nb: pynetbox.api, device, interfaceName: str = "vlan1"
) -> None:
    """
    Löscht die primary_ip4 und alle IPs am angegebenen Interface (Standard: vlan1).

    :param nb: NetBox API-Objekt
    :type nb: pynetbox.api
    :param device: NetBox Device-Objekt
    :param interfaceName: Name des Interfaces dessen IPs gelöscht werden
    :type interfaceName: str
    :return: None
    :rtype: None
    """
    # if device.primary_ip:
    #     device.primary_ip.delete()
    #     #device.

    if device.primary_ip4:
        device.primary_ip4.delete()

    # Interface suchen
    if interfaceName:
        interface = nb.dcim.interfaces.get(device_id=device.id, name=interfaceName)

        if interface:
            # vorhandene IPs suchen und löschen
            interface_ips = list(nb.ipam.ip_addresses.filter(interface_id=interface.id))

            if len(interface_ips) > 0:
                # es gibt eine oder mehrere vorhandene IPs.
                # IP löschen und neu erzeugen damit die neue IP im richtigen Subnetz ist
                for last_ip in interface_ips:
                    last_ip.delete()

    # anlegen falls nicht vorhanden
    # if interface == None:
    #     interface = nb.dcim.interfaces.create(device=device.id, name="vlan1", type="virtual")

    pass


def clean_up_vc_membership(nb: pynetbox.api, device_obj_list: list):
    """
    Entfernt Devices aus einem Virtual Chassis.

    :param nb: NetBox API-Objekt
    :type nb: pynetbox.api
    :param device_obj_list: Liste von NetBox Device-Objekten
    :type device_obj_list: list
    :return: None
    :rtype: None
    """
    for device in device_obj_list:
        if device.virtual_chassis:
            try:
                device.virtual_chassis.delete()
            except Exception:
                pass

        pass
        # device.save()
        # device.save()


def create_vc_from_device_list(nb: pynetbox.api, device_obj_list: list, site_id: int):
    """
    Erstellt ein Virtual Chassis aus einer Liste von Devices.
    Der erste Eintrag wird VC-Master. Die Priority wird über switch_position vergeben.

    :param nb: NetBox API-Objekt
    :type nb: pynetbox.api
    :param device_obj_list: Liste von NetBox Device-Objekten (erster Eintrag = Master)
    :type device_obj_list: list
    :param site_id: ID der Site
    :type site_id: int
    :return: None
    :rtype: None
    """
    try:
        vc_name = device_obj_list[0].name
        vc = nb.dcim.virtual_chassis.create(
            name=vc_name, site=site_id, master=device_obj_list[0].id
        )

        cnt = 1
        for device in device_obj_list:
            print(f"{device.name} {switch_position[cnt]}")

            # wenn vc_postion und vc_priority nicht vorbefüllt wurden, dann setzen
            if not device.vc_position:
                device.vc_position = cnt
            if not device.vc_priority:
                device.vc_priority = switch_position[cnt]

            device.virtual_chassis = vc

            device.save()
            cnt = cnt + 1
    except Exception as e:
        raise NetboxCustomCreateVirtualChassisError(str(e))

    pass


def load_devices_from_vc(nb: pynetbox.api, device) -> list[Any]:
    """
    Lädt alle Mitglieder eines Virtual Chassis.

    :param nb: NetBox API-Objekt
    :type nb: pynetbox.api
    :param device: NetBox Device-Objekt
    :return: Liste aller VC-Mitglieder, oder [device] falls kein VC
    :rtype: list[Any]
    """

    if device.virtual_chassis:
        vc = nb.dcim.virtual_chassis.get(id=device.virtual_chassis.id)

        members = vc.members
    else:
        return [device]

    return members


def rename_device_interfaces(nb: pynetbox.api, device_obj_list: list[Any]):
    """
    Benennt physische Device-Interfaces nach der VC-Position um.

    :param nb: NetBox API-Objekt
    :type nb: pynetbox.api
    :param device_obj_list: Liste von NetBox Device-Objekten
    :type device_obj_list: list[Any]
    :return: None
    :rtype: None
    """
    pass


def build_stack_hostname(
    hostname: str, stack_list: list[dict[str, Any]]
) -> list[dict[str, Any]]:
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


def createDevices(
    nb: pynetbox.api,
    device_info_list: list[dict[str, str | int]] | None = None,
    site_slug: str = "",
    role_slug: str = "",
    device_create_args: dict[str, Any] | None = None,
    create_vc: bool = False,
) -> list[object]:
    """
    Erzeugt ein oder mehrere Devices in NetBox.
    Bei mehr als einem Device wird optional ein Virtual Chassis angelegt.

    device_info_list = [
        {
            'name': 'switch', 'device_type': 'C9200L-4P-4G', 'serial': 'FOC-B-Horn',
            'slot': 1  # optional, Pflicht bei Stacks
        }
    ]

    vc_position und vc_priority werden immer als String gespeichert.

    :param nb: NetBox API-Objekt
    :type nb: pynetbox.api
    :param device_info_list: Liste mit Device-Informationen
    :type device_info_list: list[dict[str, str | int]] | None
    :param site_slug: Slug der Site
    :type site_slug: str
    :param role_slug: Slug der Device-Rolle
    :type role_slug: str
    :param device_create_args: Zusätzliche Argumente für die Device-Erstellung
    :type device_create_args: dict[str, Any] | None
    :param create_vc: Virtual Chassis anlegen falls mehrere Devices
    :type create_vc: bool
    :return: Liste der erstellten/gefundenen Device-Objekte
    :rtype: list[object]
    """
    if device_info_list is None:
        device_info_list = list()

    if device_create_args is None:
        device_create_args = {}

    # praise Device Info
    device_obj_list = list()

    # load site
    site = nb.dcim.sites.get(slug=site_slug)
    if not site:
        raise NetboxCustomCreateDeviceError(
            f'site_slug "{site_slug}" not found in netbox.'
        )

    # load role
    role = nb.dcim.device_roles.get(slug=role_slug)
    if not role:
        raise NetboxCustomCreateDeviceError(
            f'role_slug "{role_slug}" not found in netbox.'
        )

    # update device_info_list hostnames if they are part of device_default_names
    for index, dev in enumerate(device_info_list, 1):

        # Default Namen mit der Seriennummer anreichern
        # diese wird später evtl. von buildstacklist überschrieben
        if dev["name"] in device_default_names:
            dev["name"] = f"{dev['name']}-{dev['serial']}"

        # Rolle, Site und device_create_args hinzufügen
        dev["role"] = role.id
        dev["site"] = site.id
        dev.update(device_create_args)

        # vc position - only in
        if len(device_info_list) > 1:
            # Stack-Hostname
            # if "slot" in dev:
            #     dev["name"] += f"-{dev['slot']}"
            # else:
            #     dev["name"] += f"-{index}"

            # VC-Position
            if "slot" in dev:
                dev["vc_position"] = dev["slot"]
            else:
                dev["vc_position"] = f"{index}"

            # VC-Priority
            if "priority" in dev:
                dev["vc_priority"] = f"{dev['priority']}"
            else:
                dev["vc_priority"] = f"{switch_position[index]}"

    device_info_list = build_stack_hostname(
        device_info_list[0]["name"], device_info_list
    )

    for dev in device_info_list:
        # reset found for each round
        found = None

        # is used if no slot key is found to create aco
        try:
            #
            # wenn device existert, dann IPs löschen, sonst anlegen
            # device_obj_list enthält alle Objekte der Devices
            #
            found = device_exists_bySerial(
                nb, serial_number=dev["serial"], device_type=dev["device_type"]
            )

            device_delete_all_ips(nb, found)
            device_obj_list.append(found)
            # sicherheitshalber eine mögliche VC Membership löschen
            clean_up_vc_membership(nb, [found])

        except NetboxCustomNotFoundError as e:
            pass

        # device type needs to be checked in the loop because a stack can be build vom different model_types
        device_type = nb.dcim.device_types.get(model=dev["device_type"])
        if not device_type:
            raise NetboxCustomCreateDeviceError(
                f"Device_Type \"{dev['device_type']}\" not found in netbox."
            )

        # to create a device we need to use the id now
        dev["device_type"] = device_type.id

        if not found:
            try:
                device = nb.dcim.devices.create(**dev)
                device_obj_list.append(device)
            except pynetbox.RequestError as e:
                raise NetboxCustomCreateDeviceError(f"Netbox error: {e.error}")

    # mehr als ein Device! Also VC nötig!
    if len(device_obj_list) > 1 and create_vc:
        create_vc_from_device_list(nb, device_obj_list=device_obj_list, site_id=site.id)

    return device_obj_list


def get_device_list(
    nb: pynetbox.api, site_slug: str, args: dict[str, Any] | None = None
):
    """
    Gibt die Geräte-Liste für eine Site zurück.

    :param nb: NetBox API-Objekt
    :type nb: pynetbox.api
    :param site_slug: Slug der Site
    :type site_slug: str
    :param args: Zusätzliche Filter-Argumente
    :type args: dict[str, Any] | None
    :return: Liste mit Device-Informationen als Dicts
    :rtype: list
    """
    resultList = list()
    if args is None:
        args = {}

    device_list = list(nb.dcim.devices.filter(site=site_slug, **args))

    for device in device_list:
        d = {}
        d["id"] = device.id
        d["name"] = device.name
        d["comment"] = device.comments
        d["serial_number"] = device.serial
        d["description"] = device.description
        d["device_type"] = device.device_type.model
        d["url"] = device.url
        d["ip"] = None
        d["stack"] = False

        if device.primary_ip:
            print(device.primary_ip.address)
            ip = device.primary_ip.address.split("/")
            d["ip"] = ip[0]

        if device.virtual_chassis:
            d["stack"] = True

        resultList.append(d)
        pass

    return resultList


def get_site_list(
    nb: pynetbox.api, site_slug: list[str] | None = None
) -> list[dict[str, Any]]:
    """
    Gibt Site-Informationen für einen oder mehrere Slugs zurück.

    :param nb: NetBox API-Objekt
    :type nb: pynetbox.api
    :param site_slug: Liste von Site-Slugs (leer = alle Sites)
    :type site_slug: list[str] | None
    :return: Liste mit Site-Informationen als Dicts
    :rtype: list[dict[str, Any]]
    """
    if not site_slug:
        site_slug = []

    resultList = list()

    # accepting 0 can be a security issue!
    if len(site_slug) == 0:
        site_list = list(nb.dcim.sites.all())
    else:
        site_list = list(nb.dcim.sites.filter(slug=site_slug))

    for site in site_list:
        d = {}
        d["id"] = site.id
        d["name"] = site.name
        d["slug"] = site.slug
        d["gns"] = "tbc"
        d["description"] = site.description
        d["display"] = site.display
        if "GNS" in site.custom_fields:
            d["gns"] = site.custom_fields["GNS"]
            # falls None zurückgegeben wird
            if d["gns"] is None:
                d["gns"] = "tbc"

        d["long"] = d["gns"] + "-" + site.slug

        pass
        # d['comment'] = device.comments
        # d['serial'] = device.serial
        # d['device_type'] = device.device_type.model
        resultList.append(d)
        pass

    return resultList


def createOrUpdateIP(nb: pynetbox.api, ip_add_dict: dict[str, Any]):
    """
    Legt eine IP-Adresse in NetBox an oder aktualisiert eine vorhandene.

    ip_add_dict muss folgende Felder enthalten::

        ip_add_dict["address"] = ...
        ip_add_dict["description"] = ...
        ip_add_dict["dns_name"] = ...
        ip_add_dict["status"] = ...

    :param nb: NetBox API-Objekt
    :type nb: pynetbox.api
    :param ip_add_dict: Dict mit IP-Adress-Informationen
    :type ip_add_dict: dict[str, Any]
    :return: Erstelltes oder aktualisiertes IP-Objekt
    """
    # Netz /x entfernen
    ip = ip_add_dict["address"]
    ip = ip.split("/")[0]

    # IP suchen (ohne Maske)
    result = list(nb.ipam.ip_addresses.filter(q=ip))

    # falls nicht gefunden, dann
    if len(result) == 0:
        # anlegen
        result = nb.ipam.ip_addresses.create(ip_add_dict)
        return result

    else:
        # oder updaten
        ip = result[0]
        ip.address = ip_add_dict["address"]
        ip.description = ip_add_dict["description"]
        ip.dns_name = ip_add_dict["dns_name"]
        ip.status = ip_add_dict["status"]
        ip.save()

        return ip


def has_site_tenant(site: Record) -> bool:
    """
    Prüft ob einem Site-Objekt ein Tenant zugewiesen ist.

    :param site: NetBox Site-Objekt
    :type site: Record
    :return: True wenn ein Tenant vorhanden ist
    :rtype: bool
    """
    if hasattr(site, "tenant"):
        if hasattr(site.tenant, "id"):
            return True
    return False


def has_object_tenant(obj: Any) -> bool:
    """
    Prüft ob einem beliebigen NetBox-Objekt ein Tenant zugewiesen ist.

    :param obj: NetBox-Objekt
    :type obj: Any
    :return: True wenn ein Tenant vorhanden ist
    :rtype: bool
    """
    if hasattr(obj, "tenant"):
        if hasattr(obj.tenant, "id"):
            return True
    return False


def has_object_scope(obj: Any, scope_type: str | None = None) -> bool:
    """
    Prüft ob ein NetBox-Objekt einen Scope hat (z.B. bei Prefix-Objekten).
    Der Scope muss eine gültige id besitzen.

    :param obj: NetBox-Objekt (z.B. Prefix)
    :type obj: Any
    :param scope_type: Erwarteter Scope-Typ, z.B. 'dcim.site'
    :type scope_type: str | None
    :return: True wenn ein gültiger Scope vorhanden ist
    :rtype: bool
    """

    # if scope_type is set, check scope_type string! Otherwiese just check if there is an scope object
    if scope_type:
        if hasattr(obj, "scope_type"):
            if obj.scope_type != scope_type:
                return False

    if hasattr(obj, "scope"):
        if hasattr(obj.scope, "id"):
            return True
    return False


if __name__ == "__main__":

    class Scope:
        id: int = 123

    class Test:
        scope_type: str = "dcim.site"
        scope: Scope = Scope()

    t = Test()

    #  with open("sh-version-ios-xe.txt", "r") as f:
    #     show = f.read()

    #   stack_list = iosparser.parse_show_version(show)

    #    build_stack_hostname("HOSTNAME-SW-2", stack_list)
    has = has_object_scope(t, "dcim.site")
    has = has_object_scope(t, "dcim.site")
