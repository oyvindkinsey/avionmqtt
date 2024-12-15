import json
import logging
from enum import Enum

import csrmesh
from bleak import BleakClient, BleakGATTCharacteristic

from .Integration import Integration

logger = logging.getLogger(__name__)

CHARACTERISTIC_LOW = "c4edc000-9daf-11e3-8003-00025b000b00"
CHARACTERISTIC_HIGH = "c4edc000-9daf-11e3-8004-00025b000b00"

CAPABILITIES = {"dimming": {0, 90, 93, 94, 97, 134, 137, 162}, "color_temp": {0, 93, 134, 137, 162}}
PRODUCT_NAMES = {
    0: "Group",
    90: "Lamp Dimmer",
    93: "Recessed Downlight (RL)",
    94: "Light Adapter",
    97: "Smart Dimmer",
    134: "Smart Bulb (A19)",
    137: "Surface Downlight (BLD)",
    162: "MicroEdge (HLB)",
    167: "Smart Switch",
}


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


def _parse_data(target_id: int, data: bytearray) -> dict:
    logger.info(f"mesh: parsing data {data} from {target_id}")

    if data[0] == 0 and data[1] == 0:
        logger.warning(f"empty data")
        return

    try:
        verb = Verb(data[0])
        noun = Noun(data[1])

        if verb == Verb.WRITE:
            target_id = target_id if target_id else int.from_bytes(bytes([data[2], data[3]]), byteorder="big")
            value_bytes = data[4:]
        else:
            value_bytes = data[2:]

        logger.info(f"mesh: target_id({target_id}), verb({verb}), noun({noun}), value:{value_bytes})")

        if noun == Noun.DIMMING:
            brightness = int.from_bytes(value_bytes[1:2], byteorder="big")
            return {"avid": target_id, "brightness": brightness}
        elif noun == Noun.COLOR:
            temp = int.from_bytes(value_bytes[2:4], byteorder="big")
            return {"avid": target_id, "color_temp": temp}
        else:
            logger.warning(f"unknown noun {noun}")
    except Exception as e:
        logger.exception(f"mesh: Exception parsing {data} from {target_id}")


# BLEBridge.decryptMessage
def _parse_command(source: int, data: bytearray):
    hex = "-".join(map(lambda b: format(b, "01x"), data))
    logger.info(f"mesh: parsing notification {hex}")
    if data[2] == 0x73:
        if data[0] == 0x0 and data[1] == 0x80:
            return _parse_data(source, data[3:])
        else:
            return _parse_data(int.from_bytes(bytes([data[1], data[0]]), byteorder="big"), data[3:])
    else:
        logger.warning(f"Unable to handle {data[2]}")


def _create_packet(target_id: int, verb: Verb, noun: Noun, value_bytes: bytearray) -> bytes:
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


def _get_color_temp_packet(target_id: int, color: int) -> bytearray:
    return _create_packet(
        target_id,
        Verb.WRITE,
        Noun.COLOR,
        bytes([0x01, *bytearray(color.to_bytes(2, byteorder="big"))]),
    )


def _get_brightness_packet(target_id: int, brightness: int) -> bytearray:
    return _create_packet(target_id, Verb.WRITE, Noun.DIMMING, bytes([brightness, 0, 0]))


def apply_overrides_from_settings(settings: dict):
    capabilities_overrides = settings.get("capabilities_overrides")
    if capabilities_overrides is not None:
        dimming_overrides = capabilities_overrides.get("dimming")
        if dimming_overrides is not None:
            for product_id in dimming_overrides:
                CAPABILITIES["dimming"].add(product_id)
        color_temp_overrides = capabilities_overrides.get("color_temp")
        if color_temp_overrides is not None:
            for product_id in color_temp_overrides:
                CAPABILITIES["color_temp"].add(product_id)


class Mesh:
    def __init__(self, mesh: BleakClient, passphrase: str) -> None:
        super().__init__()
        self._mesh = mesh

        self._key = csrmesh.crypto.generate_key(passphrase.encode("ascii") + b"\x00\x4d\x43\x50")

    async def _write_gatt(self, packet: bytes) -> bool:
        logger.debug("-".join(map(lambda b: format(b, "02x"), packet)))

        csrpacket = csrmesh.crypto.make_packet(self._key, csrmesh.crypto.random_seq(), packet)
        low = csrpacket[:20]
        high = csrpacket[20:]
        await self._mesh.write_gatt_char(CHARACTERISTIC_LOW, low)
        await self._mesh.write_gatt_char(CHARACTERISTIC_HIGH, high)
        return True

    async def read_all(self):
        packet = _create_packet(0, Verb.READ, Noun.DIMMING, bytearray(3))
        await self._write_gatt(packet)

    async def subscribe(self, integration: Integration):
        async def cb(charactheristic: BleakGATTCharacteristic, data: bytearray):
            if charactheristic.uuid == CHARACTERISTIC_LOW:
                self._low_bytes = data
            elif charactheristic.uuid == CHARACTERISTIC_HIGH:
                encrypted = bytes([*self._low_bytes, *data])
                decoded = csrmesh.crypto.decrypt_packet(self._key, encrypted)
                parsed = _parse_command(decoded["source"], decoded["decpayload"])
                if parsed:
                    await integration.update_state(parsed)

        await self._mesh.start_notify(CHARACTERISTIC_LOW, cb)
        await self._mesh.start_notify(CHARACTERISTIC_HIGH, cb)
        logger.info("mesh: reading all")
        await self.read_all()

    async def send(self, avid: int, raw_payload: str, integration: Integration) -> bool:
        payload = json.loads(raw_payload)
        if "brightness" in payload:
            packet = _get_brightness_packet(avid, payload["brightness"])
        elif "color_temp" in payload:
            mired = payload["color_temp"]
            kelvin = (int)(1000000 / mired)
            logger.info(f"mesh: Converting mired({mired}) to kelvin({kelvin})")
            packet = _get_color_temp_packet(avid, kelvin)
        elif "state" in payload:
            packet = _get_brightness_packet(avid, 255 if payload["state"] == "ON" else 0)
        else:
            logger.warning("mesh: Unknown payload")
            return False

        if await self._write_gatt(packet):
            logger.info("mesh: Acknowedging directly")
            parsed = _parse_command(avid, packet)
            if parsed:
                await integration.update_state(parsed)
