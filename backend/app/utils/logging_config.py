"""Structured logging so Render log drains stay parseable."""

import logging
import sys

from app.config import settings


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S")
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # Quieten noisy third-party loggers on free-tier instances.
    for name in ("httpx", "httpcore", "fastembed", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)
