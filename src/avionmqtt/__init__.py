import halohome
from argparse import ArgumentParser
import asyncio
import yaml
import json
import aiomqtt
import logging
import csrmesh
from bleak import BleakClient, BleakScanner, BleakGATTCharacteristic
from bleak.exc import BleakError
from binascii import unhexlify, hexlify
from enum import Enum
import signal
import sys


def signal_handler(sig, frame):
    print("You pressed Ctrl+C!")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)

MQTT_RETRY_INTERVAL = 5
CHARACTERISTIC_LOW = "c4edc000-9daf-11e3-8003-00025b000b00"
CHARACTERISTIC_HIGH = "c4edc000-9daf-11e3-8004-00025b000b00"


class Verb(Enum):
    WRITE = 0
    READ = 1
    INSERT = 2
    TRUNCATE = 3
    COUNT = 4
    DELETE = 5
    PING = 6
    SYNC = 7
    OTA = 8
    PUSH = 11
    SCAN_WIFI = 12
    CANCEL_DATASTREAM = 13
    UPDATE = 16
    TRIM = 17
    DISCONNECT_OTA = 18
    UNREGISTER = 20
    MARK = 21
    REBOOT = 22
    RESTART = 23
    OPEN_SSH = 32
    NONE = 255


class Noun(Enum):
    DIMMING = 10
    FADE_TIME = 25
    COUNTDOWN = 9
    DATE = 21
    TIME = 22
    SCHEDULE = 7
    GROUPS = 3
    SUNRISE_SUNSET = 6
    ASSOCIATION = 27
    WAKE_STATUS = 28
    COLOR = 29
    CONFIG = 30
    WIFI_NETWORKS = 31
    DIMMING_TABLE = 17
    ASSOCIATED_WIFI_NETWORK = 32
    ASSOCIATED_WIFI_NETWORK_STATUS = 33
    SCENES = 34
    SCHEDULE_2 = 35
    RAB_IP = 36
    RAB_ENV = 37
    RAB_CONFIG = 38
    THERMOMETER = 39
    FIRMWARE_VERSION = 40
    LUX_VALUE = 41
    TEST_MODE = 42
    HARCODED_STRING = 43
    RAB_MARKS = 44
    MOTION_SENSOR = 45
    ALS_DIMMING = 46
    ASSOCIATION_2 = 48
    RTC_SUN_RISE_SET_TABLE = 71
    RTC_DATE = 72
    RTC_TIME = 73
    RTC_DAYLIGHT_SAVING_TIME_TABLE = 74
    AVION_SENSOR = 91
    NONE = 255


def settings_get(file: str):
    with open(file) as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)


async def mqtt_register(client: aiomqtt.Client, avid: int, name: str):
    await client.publish(
        f"homeassistant/light/avid_{avid}/config",
        json.dumps(
            {
                "component": "light",
                "name": name,
                "object_id": f"avid_{avid}",
                "schema": "json",
                "payload_off": "OFF",
                "payload_on": "ON",
                "brightness": True,
                "color_mode": True,
                "supported_color_modes": ["color_temp"],
                "effect": False,
                "retain": False,
                "state_topic": f"hmd/light/avid/{avid}/state",
                "json_attributes_topic": f"hmd/light/avid/{avid}/attributes",
                "command_topic": f"hmd/light/avid/{avid}/command",
            }
        ),
    )


def create_packet(target_id: int, verb: Verb, noun: Noun, value_bytes: bytearray) -> bytes:
    if target_id < 32896:
        group_id = target_id
        target_id = 0
    else:
        group_id = 0

    target_bytes = bytearray(target_id.to_bytes(2, byteorder="big"))
    group_bytes = bytearray(group_id.to_bytes(2, byteorder="big"))
    return bytes(
        [
            target_bytes[1],
            target_bytes[0],
            0x73,
            verb.value,
            noun.value,
            group_bytes[0],
            group_bytes[1],
            0,  # id
            *value_bytes,
            0,
            0,
        ]
    )


async def mesh_write_gatt(mesh: BleakClient, packet: bytes, key: str) -> bool:
    print("-".join(map(lambda b: format(b, "02x"), packet)))

    csrpacket = csrmesh.crypto.make_packet(key, csrmesh.crypto.random_seq(), packet)
    low = csrpacket[:20]
    high = csrpacket[20:]
    await mesh.write_gatt_char(CHARACTERISTIC_LOW, low)
    await mesh.write_gatt_char(CHARACTERISTIC_HIGH, high)
    return True


def mesh_get_color_temp_packet(target_id: int, color: int) -> bytearray:
    return create_packet(
        target_id,
        Verb.WRITE,
        Noun.COLOR,
        bytes([0x01, *bytearray(color.to_bytes(2, byteorder="big"))]),
    )


def mesh_get_brightness_packet(target_id: int, brightness: int) -> bytearray:
    return create_packet(target_id, Verb.WRITE, Noun.DIMMING, bytes([brightness, 0, 0]))


async def mesh_send(avid: int, raw_payload: str, mqtt: aiomqtt.Client, mesh: BleakClient, key: str) -> bool:
    payload = json.loads(raw_payload)
    if "brightness" in payload:
        packet = mesh_get_brightness_packet(avid, payload["brightness"])
    elif "color_temp" in payload:
        mired = payload["color_temp"]
        kelvin = (int)(1000000 / mired)
        print(f"mesh: Converting mired({mired}) to kelvin({kelvin})")
        packet = mesh_get_color_temp_packet(avid, kelvin)
    elif "state" in payload:
        packet = mesh_get_brightness_packet(avid, 255 if payload["state"] == "ON" else 0)
    else:
        print("mesh: Unknown payload")
        return False

    if await mesh_write_gatt(mesh, packet, key):
        print("mesh: Acknowedging directly")

        parsed = mesh_parse_command(avid, packet)
        if parsed:
            await mqtt_send_state(mqtt, parsed)


async def mqtt_subscribe(mqtt: aiomqtt.Client, mesh: BleakClient, key: str):
    await mqtt.subscribe("hmd/light/avid/+/command")
    async for message in mqtt.messages:
        json = message.payload.decode()
        avid = int(message.topic.value.split("/")[3])
        print(f"mqtt: received {json} for {avid}")
        await mesh_send(avid, json, mqtt, mesh, key)


async def mqtt_send_state(mqtt: aiomqtt.Client, message: dict):
    print(f"mqtt: sending update for {message}")
    avid = message["avid"]
    state_topic = f"hmd/light/avid/{avid}/state"
    if "brightness" in message:
        brightness = message["brightness"]
        payload = {
            "state": "ON" if brightness != 0 else "OFF",
            "brightness": brightness,
        }
        await mqtt.publish(state_topic, json.dumps(payload))
    elif "color_temp" in message:
        color_temp = message["color_temp"]
        payload = {"color_temp": color_temp}
        await mqtt.publish(state_topic, json.dumps(payload))


async def mac_ordered_by_rssi():
    scanned_devices = await BleakScanner.discover(return_adv=True)
    sorted_devices = sorted(scanned_devices.items(), key=lambda d: d[1][1].rssi)
    sorted_devices.reverse()
    return [d[0].lower() for d in sorted_devices]


def mesh_parse_data(target_id: int, data: bytearray) -> dict:
    print(f"mesh: parsing data {data} from {target_id}")

    if data[0] == 0 and data[1] == 0:
        print(f"empty data")
        return

    verb = Verb(data[0])
    noun = Noun(data[1])

    if verb == Verb.WRITE:
        target_id = target_id if target_id else int.from_bytes(bytes([data[2], data[3]]), byteorder="big")
        value_bytes = data[4:]
    else:
        value_bytes = data[2:]

    print(f"mesh: target_id({target_id}), verb({verb}), noun({noun}), value:{value_bytes})")

    if noun == Noun.DIMMING:
        brightness = int.from_bytes(value_bytes[1:2], byteorder="big")
        return {"avid": target_id, "brightness": brightness}
    elif noun == Noun.COLOR:
        temp = int.from_bytes(value_bytes[2:4], byteorder="big")
        return {"avid": target_id, "color_temp": temp}

    else:
        print(f"unknown noun {noun}")


# BLEBridge.decryptMessage
def mesh_parse_command(source: int, data: bytearray):
    hex = "-".join(map(lambda b: format(b, "01x"), data))
    print(f"mesh: parsing notification {hex}")
    if data[2] == 0x73:
        if data[0] == 0x0 and data[1] == 0x80:
            return mesh_parse_data(source, data[3:])
        else:
            return mesh_parse_data(int.from_bytes(bytes([data[1], data[0]]), byteorder="big"), data[3:])
    else:
        print(f"Unable to handle {data[2]}")


async def mesh_read_all(mesh: BleakClient, key: str):
    packet = create_packet(0, Verb.READ, Noun.DIMMING, bytearray(3))
    await mesh_write_gatt(mesh, packet, key)


async def mesh_subscribe(mqtt: aiomqtt.Client, mesh: BleakClient, key: str):
    async def cb(charactheristic: BleakGATTCharacteristic, data: bytearray):
        if charactheristic.uuid == CHARACTERISTIC_LOW:
            mesh.low_bytes = data
        elif charactheristic.uuid == CHARACTERISTIC_HIGH:
            encrypted = bytes([*mesh.low_bytes, *data])
            decoded = csrmesh.crypto.decrypt_packet(key, encrypted)
            parsed = mesh_parse_command(decoded["source"], decoded["decpayload"])
            if parsed:
                await mqtt_send_state(mqtt, parsed)

    await mesh.start_notify(CHARACTERISTIC_LOW, cb)
    await mesh.start_notify(CHARACTERISTIC_HIGH, cb)
    print("mesh: reading all")
    await mesh_read_all(mesh, key)


async def main():
    parser = ArgumentParser()
    parser.add_argument("-s", "--settings", dest="settings", help="yaml file to read settings from", metavar="FILE")
    args = parser.parse_args()

    settings = settings_get(args.settings)
    avion_settings = settings["avion"]
    mqtt_settings = settings["mqtt"]

    print("avion: Fetching devices")
    locations = await halohome.list_devices(avion_settings["email"], avion_settings["password"])
    assert len(locations) == 1
    location = locations[0]

    target_devices = [d["mac_address"].lower() for d in location["devices"]]

    mqtt = aiomqtt.Client(
        hostname=mqtt_settings["host"],
        username=mqtt_settings["username"],
        password=mqtt_settings["password"],
    )
    # connect to mqtt
    while True:
        try:
            print("mqtt: Connecting to broker")
            async with mqtt:
                if settings["groups"]["import"]:
                    for group in location["groups"]:
                        await mqtt_register(mqtt, group["group_id"], group["group_name"])
                if settings["devices"]["import"]:
                    for device in location["devices"]:
                        await mqtt_register(mqtt, device["device_id"], device["device_name"])

                # now connect the mesh
                print("mesh: Connecting to mesh")
                while True:
                    try:
                        mesh = None
                        print("mesh: Scanning for devices")
                        for mac in set(await mac_ordered_by_rssi()).intersection(target_devices):
                            print(f"mesh: connecting to {mac}")
                            try:
                                ble_device = await BleakScanner.find_device_by_address(mac)
                                print(ble_device)
                                if ble_device is None:
                                    print(f"mesh: Could not find {mac}, moving on to the next device")
                                    continue
                                mesh = BleakClient(mac)
                                await mesh.connect()
                            except BleakError as e:
                                print(f"mesh: Error connecting to {mac}")
                                continue
                            except Exception as e:
                                print(f"mesh: Error connecting to {mac}")
                                continue
                            print(f"mesh: Connected to {mac}")
                            key = csrmesh.crypto.generate_key(
                                location["passphrase"].encode("ascii") + b"\x00\x4d\x43\x50"
                            )
                            print("subscribe")
                            await mesh_subscribe(mqtt, mesh, key)
                            await mqtt_subscribe(mqtt, mesh, key)
                            print("done?")

                    except BleakError as e:
                        print(f"mesh: Error connecting to {mac}")

                    except Exception as e:
                        print("mesh: Exception")
                        # this isn't printing
                        print(e)

                    finally:
                        if mesh and mesh.is_connected:
                            await mesh.disconnect()
                            print("mesh: Disconnected from {mac}")

        except aiomqtt.MqttError:
            print(f"mqtt: Connection lost; Reconnecting in {MQTT_RETRY_INTERVAL} seconds ...")
            await asyncio.sleep(MQTT_RETRY_INTERVAL)


# create a new event loop (low-level api)
loop = asyncio.new_event_loop()
# schedule our coroutine
loop.create_task(main())
# run the event loop until stopped
loop.run_forever()
