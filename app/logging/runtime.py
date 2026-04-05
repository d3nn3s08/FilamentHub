from typing import Dict

from app.logging_setup import configure_logging


def reconfigure_logging(logging_config: dict) -> Dict[str, bool]:
    return configure_logging(logging_config)
