import logging
from argparse import ArgumentParser

from aiorun import run

from .config import load_settings
from .service import AvionMqttService


def parse_args():
    """Parse command-line arguments."""
    parser = ArgumentParser(
        prog="avionmqtt", description="Bridge Avion Bluetooth mesh lights to MQTT/Home Assistant"
    )
    parser.add_argument(
        "-s",
        "--settings",
        dest="settings",
        required=True,
        help="YAML file to read settings from",
        metavar="FILE",
    )
    parser.add_argument(
        "--log",
        default="WARNING",
        help="Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    return parser.parse_args()


def main():
    """Main CLI entry point."""
    args = parse_args()

    # Configure logging
    logging.basicConfig(
        level=args.log.upper(), format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Load settings
    settings = load_settings(args.settings)

    # Create and run service
    service = AvionMqttService(settings)
    run(service.run())
