import asyncio
import logging

import aiomqtt
from avionmesh import MeshCommand, MeshStatus

from .Mqtt import Mqtt

logger = logging.getLogger(__name__)
MQTT_RETRY_INTERVAL = 5


async def mqtt_handler(
    settings: dict,
    location: dict,
    command_queue: asyncio.Queue,
    status_queue: asyncio.Queue,
):
    """Handle MQTT connection with automatic reconnection."""
    mqtt_settings = settings["mqtt"]
    mqtt_client = aiomqtt.Client(
        hostname=mqtt_settings["host"],
        username=mqtt_settings.get("username"),
        password=mqtt_settings.get("password"),
    )

    while True:
        try:
            logger.info("Connecting to MQTT broker")
            async with mqtt_client as mqtt:
                integration = Mqtt(mqtt)
                await integration.register_lights(settings, location)
                logger.info("MQTT connection established and lights registered")

                async with asyncio.TaskGroup() as tg:
                    tg.create_task(
                        mqtt_command_listener(integration, settings, location, command_queue)
                    )
                    tg.create_task(mqtt_status_publisher(integration, status_queue))

        except aiomqtt.MqttError as e:
            logger.warning(f"MQTT connection lost ({e}), reconnecting in {MQTT_RETRY_INTERVAL}s")
            await asyncio.sleep(MQTT_RETRY_INTERVAL)
        except Exception:
            logger.exception("Unhandled exception in MQTT handler")
            await asyncio.sleep(MQTT_RETRY_INTERVAL)


async def mqtt_command_listener(
    mqtt: Mqtt,
    settings: dict,
    location: dict,
    command_queue: asyncio.Queue,
):
    """Subscribe to MQTT commands and forward to mesh."""
    try:
        async for command in mqtt.listen_for_commands(settings, location):
            await command_queue.put(MeshCommand(data=command))
            logger.debug(f"Command queued: {command}")
    except asyncio.CancelledError:
        logger.info("MQTT command listener cancelled")
        raise


async def mqtt_status_publisher(
    mqtt: Mqtt,
    status_queue: asyncio.Queue,
):
    """Consume status updates from mesh and publish to MQTT."""
    try:
        while True:
            status: MeshStatus = await status_queue.get()
            await mqtt.publish_status(status.data)
            logger.debug(f"Status published: {status.data}")
            status_queue.task_done()
    except asyncio.CancelledError:
        logger.info("MQTT status publisher cancelled")
        raise
