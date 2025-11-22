import json
import logging
from typing import AsyncIterator, List, Optional

import aiomqtt

from .Mesh import CAPABILITIES, PRODUCT_NAMES

logger = logging.getLogger(__name__)


class Mqtt:
    def __init__(self, mqtt: aiomqtt.Client) -> None:
        super().__init__()
        self.mqtt = mqtt

    async def _register(self, use_single_device: bool, entity: dict):
        product_id = entity["product_id"]
        pid = entity["pid"]
        avid = entity["avid"]
        name = entity["name"]

        # https://www.home-assistant.io/integrations/light.mqtt/
        config = {
            "component": "light",
            "object_id": f"avid_{avid}",
            "unique_id": pid,
            "schema": "json",
            "payload_off": "OFF",
            "payload_on": "ON",
            "brightness": product_id in CAPABILITIES["dimming"],
            "color_mode": product_id in CAPABILITIES["color_temp"],
            "effect": False,
            "retain": False,
            "state_topic": f"hmd/light/avid/{avid}/state",
            "json_attributes_topic": f"hmd/light/avid/{avid}/attributes",
            "command_topic": f"hmd/light/avid/{avid}/command",
        }
        if use_single_device:
            config["name"] = name
            config["device"] = {"identifiers": ["avionmqtt"], "name": "Avi-on MQTT Bridge"}
        else:
            config["device"] = {
                "identifiers": [pid],
                "name": name,
                "manufacturer": "Avi-on",
                "model": PRODUCT_NAMES.get(product_id, f"Unknown product ({product_id})"),
                "serial_number": pid,
            }

        if product_id in CAPABILITIES["color_temp"]:
            config["supported_color_modes"] = ["color_temp"]
            config["color_temp_kelvin"] = True
            config["min_kelvin"] = 2700
            config["max_kelvin"] = 5000

        await self.mqtt.publish(
            f"homeassistant/light/avid_{avid}/config",
            json.dumps(config),
        )

    async def _register_category(self, use_single_device: bool, settings: dict, list: List[dict]):
        if settings["import"]:
            include = settings.get("include", None)
            exclude = settings.get("exclude", {})
            for entity in list:
                pid = entity["pid"]
                if (include is not None and pid in include) or pid not in exclude:
                    await self._register(use_single_device, entity)

    async def register_lights(self, settings: dict, location: dict):
        logger.info("mqtt: Registering devices")
        use_single_device = settings.get("single_device", False)
        await self._register_category(use_single_device, settings["groups"], location["groups"])

        if settings["devices"].get("exclude_in_group"):
            exclude = settings["devices"].get("exclude", set())
            for group in location["groups"]:
                devices = group["devices"]
                exclude |= set(devices)
            settings["devices"]["exclude"] = exclude
        await self._register_category(use_single_device, settings["devices"], location["devices"])
        if "all" in settings:
            await self._register(
                use_single_device,
                {"pid": "avion_all", "product_id": 0, "avid": 0, "name": settings["all"]["name"]},
            )

    async def handle_homeassistant_status(self, settings: dict, location: dict, message):
        if message.payload.decode() == "online":
            logger.info("mqtt: Home Assistant back online")
            await self.register_lights(settings, location)
        else:
            logger.info("mqtt: Home Assistant offline")

    async def handle_light_command(self, message) -> Optional[dict]:
        decoded = message.payload.decode()
        if decoded is None or len(decoded) == 0:
            # empty payloads are used for deletes
            return None
        avid = int(message.topic.value.split("/")[3])
        logger.info(f"mqtt: received {decoded} for {avid}")
        return {"avid": avid, "command": "update", "json": decoded}

    async def handle_avionmqtt_command(self, message) -> Optional[dict]:
        if message.payload.decode() == "poll_mesh":
            logger.info("mqtt: polling mesh")
            return {"avid": 0, "command": "read_all"}
        return None

    async def listen_for_commands(
        self,
        settings: dict,
        location: dict,
    ) -> AsyncIterator[dict]:
        await self.mqtt.subscribe("homeassistant/status")
        await self.mqtt.subscribe("hmd/light/avid/+/command")
        await self.mqtt.subscribe("avionmqtt")

        async for message in self.mqtt.messages:
            try:
                if message.topic.matches("homeassistant/status"):
                    await self.handle_homeassistant_status(settings, location, message)
                elif message.topic.matches("hmd/light/avid/+/command"):
                    result = await self.handle_light_command(message)
                    if result:
                        yield result
                elif message.topic.matches("avionmqtt"):
                    result = await self.handle_avionmqtt_command(message)
                    if result:
                        yield result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse command payload: {e}")
            except Exception as e:
                logger.error(f"Error processing command: {e}")

    async def publish_status(self, message: dict):
        # TODO: Only send update if we've actually registered this device
        avid = message["avid"]
        state_topic = f"hmd/light/avid/{avid}/state"
        if "brightness" in message:
            brightness = message["brightness"]
            payload = {
                "state": "ON" if brightness != 0 else "OFF",
                "brightness": brightness,
            }
        elif "color_temp" in message:
            payload = {"color_temp": message["color_temp"]}
        else:
            return
        logger.info(f"mqtt: publishing status to {state_topic}: {payload}")
        await self.mqtt.publish(state_topic, json.dumps(payload), retain=True)
