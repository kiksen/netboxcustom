import asyncio
import os
import re

from netboxcustom.netboxcustom_async import AsyncNetboxCustom


async def main():
    NETBOX_TOKEN = os.environ.get("NETBOX_TOKEN", "")
    NETBOX_ENDPOINT = os.environ.get("NETBOX_API", "")

    device_info_list = [
        {
            "name": "max",
            "device_type": "C9200L-24P-4G",
            "serial": "SERIAL-1",
            "slot": 1,
        },
        # {
        #     "name": "switch",
        #     "device_type": "C9200L-24P-4G",
        #     "serial": "SERIAL-2",
        #     "slot": 3,
        # },
    ]

    async with AsyncNetboxCustom(NETBOX_ENDPOINT, NETBOX_TOKEN) as nb:
        #sites = await nb.lookup_firmware_list(["C9200CX-12P-2X2G", "C3850-ABC", "C2960CX-8PC-Lx", "C9200L-24P-4G"], "firmware_filename")
        #site = await nb.lookup_site_by_ip_full("10.200.0.145")
        #sites = await nb.get_site_list(params={ "limit":3 })

        #await nb.createDevices(        device_info_list,        site_slug="bonn",        role_slug="access", default_device_names=["switch","max"]        )
        config = await nb.get_device_types(api_filter={"manufacturer" : "cisco"},firmware_custom_field="firmware_filename",version_custom_field="firmware_version")


        print(config)
        #print("Cont interface: ",  len(re.findall("interface ", config))    )    
        pass




if __name__ == "__main__":
    asyncio.run(main())
