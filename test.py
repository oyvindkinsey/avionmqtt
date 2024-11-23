import halohome
from halohome import Device, Group
import asyncio
import yaml
import logging
import time
import json
from ha_mqtt_discoverable import Settings
from ha_mqtt_discoverable.sensors import Light, LightInfo
from paho.mqtt import client as mqtt_client


async def my_async_callback(device: Device, message):
    payload = json.loads(message.payload.decode())
    print(payload)
    my_light = device.cmp
    if "brightness" in payload:
        brightness = payload["brightness"]
        updated = await device.set_brightness(brightness)
        if updated:
            my_light.brightness(payload["brightness"])
    elif "color_temp" in payload:
        color_temp = (int)(1000000 / payload["color_temp"])
        updated = await device.set_color_temp(color_temp)
        if updated:
            my_light.color("color_temp", payload["color_temp"])
    elif "state" in payload:
        brightness = 255 if payload["state"] == "ON" else 0
        updated = await device.set_brightness(brightness)
        if updated:
            if payload["state"] == "ON":
                my_light.on()
            else:
                my_light.off()
    else:
        print("Unknown payload")


def get_settings():
    with open("settings.yaml") as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)


async def setup(loop, queue):
    settings = get_settings()
    avion = settings["avion"]
    devices = await halohome.list_devices(avion["email"], avion["password"])
    connection = halohome.Connection(devices)

    mqtt = settings["mqtt"]
    mqtt_settings = Settings.MQTT(
        host=mqtt["host"],
        username=mqtt["username"],
        password=mqtt["password"],
    )

    def my_callback(client: mqtt_client, device: Device, message):
        loop.call_soon_threadsafe(queue.put_nowait, (device, message))

    device_settings = settings["devices"]
    if device_settings["import"]:
        for device in connection.devices:
            light_info = LightInfo(
                name=device.device_name,
                object_id=f"avid_{device.device_id}",
                brightness=True,
                color_mode=True,
                supported_color_modes=["color_temp"],
            )
            settings = Settings(mqtt=mqtt_settings, entity=light_info)
            my_light = Light(settings, my_callback, device)
            device.cmp = my_light
            my_light.write_config()

    group_settings = settings["groups"]
    if group_settings["import"]:
        for group in connection.groups:
            light_info = LightInfo(
                name=group.group_name,
                object_id=f"avid_{group.group_id}",
                brightness=True,
                color_mode=True,
                supported_color_modes=["color_temp"],
            )
            settings = Settings(mqtt=mqtt_settings, entity=light_info)
            my_light = Light(settings, my_callback, group)
            group.cmp = my_light
            my_light.write_config()


async def main():
    queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    loop.create_task(setup(loop, queue))
    while True:
        message = await queue.get()
        if message:
            await my_async_callback(message[0], message[1])


asyncio.run(main())
