import logging

import yaml

logger = logging.getLogger(__name__)


def load_settings(file: str) -> dict:
    """Load and validate settings from YAML file."""
    try:
        with open(file) as stream:
            settings = yaml.safe_load(stream)
            validate_settings(settings)
            return settings  # type: ignore[no-any-return]
    except yaml.YAMLError:
        logger.exception("Failed to parse YAML settings file")
        raise
    except FileNotFoundError:
        logger.error(f"Settings file not found: {file}")
        raise
    raise "Failed to load settings"


def validate_settings(settings: dict):
    """Validate required settings are present."""
    required = ["avion", "mqtt"]
    for key in required:
        if key not in settings:
            raise ValueError(f"Missing required setting: {key}")

    if "email" not in settings["avion"] or "password" not in settings["avion"]:
        raise ValueError("Missing avion email or password")

    if "host" not in settings["mqtt"]:
        raise ValueError("Missing mqtt host")
