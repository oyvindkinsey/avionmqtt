import asyncio
import logging

from avionmesh import MeshCommand, MeshStatus, mesh_handler
from avionmesh.Mesh import apply_overrides_from_settings
from bleak import BleakScanner

from .Http import http_list_devices
from .mqtt_handler import mqtt_handler

logger = logging.getLogger(__name__)


class AvionMqttService:
    """Main service that orchestrates MQTT and BLE handlers."""

    def __init__(self, settings: dict):
        self.settings = settings
        self.command_queue: asyncio.Queue[MeshCommand] = asyncio.Queue()
        self.status_queue: asyncio.Queue[MeshStatus] = asyncio.Queue()

    async def run(self):
        """Run the service."""
        try:
            # Apply mesh overrides
            apply_overrides_from_settings(self.settings)

            # Get device information
            avion_settings = self.settings["avion"]
            email = avion_settings["email"]
            password = avion_settings["password"]

            logger.info("Fetching devices from Avion API")
            locations = await http_list_devices(email, password)

            if not locations:
                raise ValueError("No locations found for this account")

            if len(locations) > 1:
                logger.warning(f"Multiple locations found ({len(locations)}), using first")

            location = locations[0]
            passphrase = location["passphrase"]
            target_devices = [d["mac_address"].upper() for d in location["devices"]]

            logger.info(f"Resolved {len(target_devices)} devices for {email}")

            # Run both handlers concurrently
            async with asyncio.TaskGroup() as tg:
                tg.create_task(
                    mqtt_handler(
                        self.settings,
                        location,
                        self.command_queue,
                        self.status_queue,
                    )
                )
                # Create a scanner instance and pass it into mesh_handler so
                # callers (including Home Assistant) can provide a shared scanner.
                scanner = BleakScanner()
                tg.create_task(
                    mesh_handler(
                        passphrase,
                        target_devices,
                        self.command_queue,
                        self.status_queue,
                        scanner,
                    )
                )
                logger.info("Service started successfully")

        except KeyboardInterrupt:
            logger.info("Received shutdown signal, stopping gracefully...")
        except Exception:
            logger.exception("Fatal error in service")
            raise
            raise
