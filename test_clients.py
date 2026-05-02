import asyncio
import os

from netboxcustom.netboxcustom_async import AsyncNetboxCustom

#from netboxcustom.netboxcustom import NetboxCustom


async def main():
    NETBOX_TOKEN = os.environ.get("NETBOX_TOKEN", "")
    NETBOX_ENDPOINT = os.environ.get("NETBOX_ENDPOINT", "")

    device_list = [
        {
            "name": "switch",
            "device_type": "C9200L-24P-4G",
            "serial": "SERIAL-1",
            "slot": 1,
        },
        {
            "name": "switch",
            "device_type": "C9200L-24P-4G",
            "serial": "SERIAL-2",
            "slot": 3,
        },
    ]

    async  with AsyncNetboxCustom(NETBOX_ENDPOINT, NETBOX_TOKEN) as nb:
        sites = await nb.createDevices(device_list, "bonn", "access", create_vc=True)

        print(sites)


if __name__ == "__main__":
    asyncio.run(main())
    

