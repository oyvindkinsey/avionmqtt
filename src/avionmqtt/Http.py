import asyncio
from typing import List, Optional

import aiohttp

HTTP_HOST = "https://api.avi-on.com"


def util_format_mac_address(mac_address: str) -> str:
    iterator = iter(mac_address.lower())
    pairs = zip(iterator, iterator)
    return ":".join(a + b for a, b in pairs)


async def http_make_request(
    host: str,
    path: str,
    body: Optional[dict] = None,
    auth_token: Optional[str] = None,
):
    method = "GET" if body is None else "POST"
    url = host + path

    headers = {}
    if auth_token:
        headers["Accept"] = "application/api.avi-on.v3"
        headers["Authorization"] = f"Token {auth_token}"

    async with aiohttp.ClientSession() as session:
        async with session.request(method, url, json=body, headers=headers) as response:
            return await response.json()


async def http_load_devices(host: str, auth_token: str, location_id: int) -> List[dict]:
    response = await http_make_request(
        host, f"locations/{location_id}/abstract_devices", auth_token=auth_token
    )
    raw_devices = response["abstract_devices"]
    devices = []

    for raw_device in raw_devices:
        if raw_device["type"] != "device":
            continue

        pid = raw_device["pid"]
        product_id = raw_device["product_id"]
        avid = raw_device["avid"]
        name = raw_device["name"]
        mac_address = util_format_mac_address(raw_device["friendly_mac_address"])
        device = {
            "pid": pid,
            "product_id": product_id,
            "avid": avid,
            "name": name,
            "mac_address": mac_address,
        }
        devices.append(device)

    return devices


async def http_get_devices_in_group(host: str, auth_token: str, group_id: int):
    response = await http_make_request(host, f"groups/{group_id}", auth_token=auth_token)
    raw_response = response["group"]
    return raw_response["devices"]


async def http_load_groups(host: str, auth_token: str, location_id: int) -> List[dict]:
    response = await http_make_request(
        host, f"locations/{location_id}/groups", auth_token=auth_token
    )
    raw_groups = response["groups"]
    groups = []

    for raw_group in raw_groups:
        pid = raw_group["pid"]
        avid = raw_group["avid"]
        name = raw_group["name"]
        devices = await http_get_devices_in_group(host, auth_token, pid)
        group = {"pid": pid, "product_id": 0, "avid": avid, "name": name, "devices": devices}
        groups.append(group)

    return groups


async def http_load_location(host: str, auth_token: str, location_id: int) -> dict:
    response = await http_make_request(host, f"locations/{location_id}", auth_token=auth_token)
    raw_location = response["location"]
    devices, groups = await asyncio.gather(
        http_load_devices(host, auth_token, location_id),
        http_load_groups(host, auth_token, location_id),
    )
    return {
        "passphrase": raw_location["passphrase"],
        "devices": devices,
        "groups": groups,
    }


async def http_load_locations(host: str, auth_token: str) -> List[dict]:
    response = await http_make_request(host, "user/locations", auth_token=auth_token)
    locations = []
    for raw_location in response["locations"]:
        location = await http_load_location(host, auth_token, raw_location["pid"])
        locations.append(location)

    return locations


async def http_list_devices(
    email: str,
    password: str,
    host: str = HTTP_HOST,
) -> List[dict]:
    if not host.endswith("/"):
        host += "/"

    login_body = {"email": email, "password": password}
    response = await http_make_request(host, "sessions", login_body)
    if "credentials" not in response:
        raise Exception("Invalid credentials for HALO Home")
    auth_token = response["credentials"]["auth_token"]

    return await http_load_locations(host, auth_token)
