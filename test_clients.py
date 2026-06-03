import asyncio
import os

from netboxcustom.netboxcustom_async import AsyncNetboxCustom

# from netboxcustom.netboxcustom import NetboxCustom


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

    async with AsyncNetboxCustom(NETBOX_ENDPOINT, NETBOX_TOKEN) as nb:
        sites = await nb.lookup_firmware_list(["C9200CX-12P-2X2G", "C3850-ABC", "C2960CX-8PC-Lx", "C9200L-24P-4G"], "firmware_filename")

        print(sites)


if __name__ == "__main__":
    asyncio.run(main())
