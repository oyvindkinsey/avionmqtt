import json
import logging
from typing import List

import aiomqtt

from .Integration import Integration
from .Mesh import CAPABILITIES, PRODUCT_NAMES, Mesh

logger = logging.getLogger(__name__)


class MqttIntegration(Integration):
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
                use_single_device, {"pid": "avion_all", "product_id": 0, "avid": 0, "name": settings["all"]["name"]}
            )

    async def connect(self, mesh: Mesh, settings: dict, location: dict):
        await self.mqtt.subscribe("homeassistant/status")
        await self.mqtt.subscribe("hmd/light/avid/+/command")
        await self.mqtt.subscribe("avionmqtt")
        async for message in self.mqtt.messages:
            if message.topic.matches("homeassistant/status"):
                if message.payload.decode() == "online":
                    logger.info("mqtt: Home Assistant back online")
                    await self.register_lights(settings, location)
                else:
                    logger.info("mqtt: Home Assistant offline")
            elif message.topic.matches("hmd/light/avid/+/command"):
                json = message.payload.decode()
                avid = int(message.topic.value.split("/")[3])
                logger.info(f"mqtt: received {json} for {avid}")
                await mesh.send(avid, json, self)
            elif message.topic.matches("avionmqtt"):
                if message.payload.decode() == "poll_mesh":
                    logger.info("mqtt: polling mesh")
                    await mesh.read_all()

    async def update_state(self, message: dict):
        # TODO: Only send update if we've actually registered this device
        logger.info(f"mqtt: sending update for {message}")
        avid = message["avid"]
        state_topic = f"hmd/light/avid/{avid}/state"
        if "brightness" in message:
            brightness = message["brightness"]
            payload = {
                "state": "ON" if brightness != 0 else "OFF",
                "brightness": brightness,
            }
        elif "color_temp" in message:
            color_temp = message["color_temp"]
            payload = {"color_temp": color_temp}
        else:
            return

        await self.mqtt.publish(state_topic, json.dumps(payload), retain=True)
