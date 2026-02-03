"""Utilities for per-bot logging levels and quiet mode."""
import logging
from typing import Dict

LOG_LEVELS: Dict[str, int] = {}
QUIET_MODE = False


def get_logger(name: str) -> logging.Logger:
    level = LOG_LEVELS.get(name, logging.INFO)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(name)s: %(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    if QUIET_MODE and level < logging.ERROR:
        logger.disabled = True
    return logger
