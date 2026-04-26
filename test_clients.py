import asyncio
import os

from netboxcustom.netboxcustom_async import NetboxAsyncClient


async def main():
    NETBOX_TOKEN = os.environ.get("NETBOX_TOKEN", "")
    NETBOX_ENDPOINT = os.environ.get("NETBOX_ENDPOINT", "")

    device_list = [
        {
            "name": "switch",
            "device_type": "C9200L-24P-4G",
            "serial": "FOC-B-Horn",
            "slot": 1,
        },
        {
            "name": "switch",
            "device_type": "C9200L-24P-4G",
            "serial": "FOC-C-Horn",
            "slot": 3,
        },
    ]

    async with NetboxAsyncClient(NETBOX_ENDPOINT, NETBOX_TOKEN) as nb:
        sites = await nb.createDevices(device_list, "bonn", "access")
        print(sites)

        pass
    # await aio.createDevices(device_list, "bonn", "access", None, True)


if __name__ == "__main__":
    asyncio.run(main())
    pass
    pass
    pass
