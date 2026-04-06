import asyncio

from netboxcustom import aio


async def main():

    client = await aio.nb_login()

    site_list = await aio.get_site_list()

    site = await aio.lookup_site_by_ip("192.168.178.33")

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

    await aio.createDevices(device_list, "bonn", "access", None, True)

    pass


if __name__ == "__main__":
    asyncio.run(main())
    pass
