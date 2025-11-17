import asyncio
import logging
from typing import Optional

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

from .Mesh import Mesh
from .mqtt_handler import MeshCommand, MeshStatus

logger = logging.getLogger(__name__)
BLE_RETRY_INTERVAL = 10
BLE_CONNECT_TIMEOUT = 30


async def mac_ordered_by_rssi(scanner: BleakScanner):
    """Scan for BLE devices using the provided scanner and return MACs ordered by signal strength."""
    scanned_devices = await scanner.discover(return_adv=True)
    # `scanned_devices` is a mapping of address -> (device, advertisement_data)
    sorted_devices = sorted(scanned_devices.items(), key=lambda d: d[1][1].rssi, reverse=True)
    return [d[0].upper() for d in sorted_devices]


async def mesh_handler(  # noqa: C901
    passphrase: str,
    target_devices: list[str],
    command_queue: asyncio.Queue,
    status_queue: asyncio.Queue,
    scanner: BleakScanner,
):
    """Handle BLE mesh connection with automatic reconnection."""
    while True:
        ble_client: Optional[BleakClient] = None
        connected_mac: Optional[str] = None

        try:
            logger.info("Scanning for BLE devices")
            available_macs = set(await mac_ordered_by_rssi(scanner)).intersection(target_devices)

            if not available_macs:
                logger.warning("No target devices found in scan")
                await asyncio.sleep(BLE_RETRY_INTERVAL)
                continue

            # Try to connect to devices in order of signal strength
            for mac in available_macs:
                logger.info(f"Attempting connection to {mac}")
                try:
                    # Use the provided scanner instance to locate the device
                    ble_device = await asyncio.wait_for(
                        scanner.find_device_by_address(mac), timeout=10.0
                    )

                    if ble_device is None:
                        logger.info(f"Could not find {mac}, trying next device")
                        continue

                    ble_client = BleakClient(ble_device)
                    await asyncio.wait_for(ble_client.connect(), timeout=BLE_CONNECT_TIMEOUT)

                    connected_mac = mac
                    logger.info(f"Connected to BLE device {mac}")
                    break

                except asyncio.TimeoutError:
                    logger.warning(f"Timeout connecting to {mac}")
                    if ble_client and ble_client.is_connected:
                        await ble_client.disconnect()
                    continue

                except BleakError as e:
                    logger.warning(f"BLE error connecting to {mac}: {e}")
                    continue

            if not ble_client or not ble_client.is_connected:
                logger.warning("Failed to connect to any device")
                await asyncio.sleep(BLE_RETRY_INTERVAL)
                continue

            # Successfully connected, create mesh and handle communication
            mesh = Mesh(ble_client, passphrase)

            async with asyncio.TaskGroup() as tg:
                tg.create_task(mesh_status_listener(mesh, status_queue))
                tg.create_task(mesh_command_processor(mesh, command_queue))
                tg.create_task(mesh_set_network_time(mesh))

        except asyncio.TimeoutError:
            logger.warning("BLE operation timed out")
        except BleakError as e:
            logger.warning(f"BLE error: {e}")
        except Exception:
            logger.exception("Unhandled exception in BLE handler")
        finally:
            if ble_client and ble_client.is_connected:
                try:
                    await ble_client.disconnect()
                    logger.info(f"Disconnected from {connected_mac}")
                except Exception as e:
                    logger.warning(f"Error during disconnect: {e}")

            logger.info(f"Reconnecting in {BLE_RETRY_INTERVAL}s")
            await asyncio.sleep(BLE_RETRY_INTERVAL)


async def mesh_set_network_time(mesh: Mesh):
    """Keeps the connection alive by periodically sending out timestamp updates"""
    while True:
        try:
            await mesh.set_network_time()
            await asyncio.sleep(60 * 60 * 24)
        except asyncio.CancelledError:
            logger.info("Mesh set network time cancelled")
            raise


async def mesh_status_listener(mesh: Mesh, status_queue: asyncio.Queue):
    """Subscribe to mesh status updates and forward to MQTT."""
    try:

        async def status_callback(data):
            await status_queue.put(MeshStatus(data=data))
            logger.debug(f"Status update queued: {data}")

        await mesh.subscribe(status_callback)
    except asyncio.CancelledError:
        logger.info("Mesh status listener cancelled")
        raise


async def mesh_command_processor(mesh: Mesh, command_queue: asyncio.Queue):
    """Process commands from queue and send to mesh."""
    try:
        while True:
            command: MeshCommand = await command_queue.get()
            try:
                await mesh.send_command(command.data)

            except Exception as e:
                logger.error(f"Error sending command: {e}")
                raise
            finally:
                command_queue.task_done()
    except asyncio.CancelledError:
        logger.info("Mesh command processor cancelled")
        raise
