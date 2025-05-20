import asyncio
import logging
from argparse import ArgumentParser

import aiomqtt
import yaml
from aiorun import run
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

from avionhttp import http_list_devices

from .Mesh import Mesh, apply_overrides_from_settings
from .MqttIntegration import MqttIntegration

MQTT_RETRY_INTERVAL = 5
logger = logging.getLogger(__name__)


def settings_get(file: str):
    with open(file) as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            logger.exception(exc)


async def mac_ordered_by_rssi():
    scanned_devices = await BleakScanner.discover(return_adv=True)
    sorted_devices = sorted(scanned_devices.items(), key=lambda d: d[1][1].rssi)
    sorted_devices.reverse()
    return [d[0].lower() for d in sorted_devices]


async def main():
    parser = ArgumentParser()
    parser.add_argument("-s", "--settings", dest="settings", help="yaml file to read settings from", metavar="FILE")
    parser.add_argument(
        "--log", default="WARNING", help="Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    args = parser.parse_args()

    logging.basicConfig(level=args.log.upper(), format="%(levelname)s: %(message)s")

    settings = settings_get(args.settings)
    apply_overrides_from_settings(settings)
    avion_settings = settings["avion"]
    email = avion_settings["email"]
    password = avion_settings["password"]
    mqtt_settings = settings["mqtt"]

    logger.info("avion: Fetching devices")
    locations = await http_list_devices(email, password)
    assert len(locations) == 1
    location = locations[0]
    passphrase = location["passphrase"]

    print(f"Resolved devices for {email} with passphrase {passphrase}")

    target_devices = [d["mac_address"].lower() for d in location["devices"]]

    mqtt = aiomqtt.Client(
        hostname=mqtt_settings["host"],
        username=mqtt_settings["username"],
        password=mqtt_settings["password"],
    )

    running = True
    # connect to mqtt
    while running:
        try:
            print("connecting to MQTT and mesh")
            logger.info("mqtt: Connecting to broker")
            async with mqtt:
                integration = MqttIntegration(mqtt)
                # register the lights
                await integration.register_lights(settings, location)
                # now connect the mesh
                logger.info("mesh: Connecting to mesh")
                while running:
                    try:
                        ble = None
                        logger.info("mesh: Scanning for devices")
                        for mac in set(await mac_ordered_by_rssi()).intersection(target_devices):
                            logger.info(f"mesh: connecting to {mac}")
                            try:
                                ble_device = await BleakScanner.find_device_by_address(mac)
                                if ble_device is None:
                                    logger.info(f"mesh: Could not find {mac}, moving on to the next device")
                                    continue
                                ble = BleakClient(mac)
                                await ble.connect()
                            except BleakError:
                                logger.warning(f"mesh: Error connecting to {mac}")
                                continue
                            except Exception:
                                logger.warning(f"mesh: Error connecting to {mac}")
                                continue
                            logger.info(f"mesh: Connected to {mac}")
                            print("Connected to MQTT and mesh")

                            mesh = Mesh(ble, passphrase)
                            # subscribe to updates from the mesh
                            await mesh.subscribe(integration)
                            # subscribe to commands from Home Assistant (this also keeps the loop going)
                            await integration.connect(mesh, settings, location)

                    except asyncio.CancelledError:
                        running = False
                        print("Terminating")

                    except BleakError:
                        logger.warning("mesh: Error connecting to device")

                    finally:
                        logger.info("mesh: Done")
                        if ble and ble.is_connected:
                            await ble.disconnect()
                            logger.info(f"mesh: Disconnected from {mac}")

        except aiomqtt.MqttError:
            logger.warning(f"mqtt: Connection lost; Reconnecting in {MQTT_RETRY_INTERVAL} seconds ...")
            await asyncio.sleep(MQTT_RETRY_INTERVAL)

        except Exception:
            logger.exception("Unhandled exception")

        finally:
            logger.info("mqtt: Done")


# create a new event loop (low-level api)
run(main())
