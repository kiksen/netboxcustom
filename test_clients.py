import asyncio
import os

from netboxcustom.netboxcustom_async import AsyncNetboxCustom


async def main():
    NETBOX_TOKEN = os.environ.get("NETBOX_TOKEN", "")
    NETBOX_ENDPOINT = os.environ.get("NETBOX_ENDPOINT", "")

    # device_list = [
    #     {
    #         "name": "switch",
    #         "device_type": "C9200L-24P-4G",
    #         "serial": "SERIAL-1",
    #         "slot": 1,
    #     },
    #     {
    #         "name": "switch",
    #         "device_type": "C9200L-24P-4G",
    #         "serial": "SERIAL-2",
    #         "slot": 3,
    #     },
    # ]

    async with AsyncNetboxCustom(NETBOX_ENDPOINT, NETBOX_TOKEN) as nb:
        #sites = await nb.lookup_firmware_list(["C9200CX-12P-2X2G", "C3850-ABC", "C2960CX-8PC-Lx", "C9200L-24P-4G"], "firmware_filename")
        #site = await nb.lookup_site_by_ip_full("10.200.0.145")

        sites = await nb.get_site_list(params={ "limit":3 })

        print(sites)
        pass




if __name__ == "__main__":
    asyncio.run(main())
