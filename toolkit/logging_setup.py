"""Rotating-file logger bootstrap per ADR-0011."""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

# MSIX family name — must match AppxManifest Identity Name + publisher suffix.
_MSIX_FAMILY_NAME = "SchoolTool_vurctne"
_LOG_FILENAME = "sftk.log"
_MAX_BYTES = 1 * 1024 * 1024  # 1 MB
_BACKUP_COUNT = 5


def _log_dir() -> Path:
    """Return the platform-appropriate log directory (creating it if needed)."""
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            base = Path(local_app_data) / "Packages" / _MSIX_FAMILY_NAME / "LocalCache" / "logs"
        else:
            base = Path.home() / "AppData" / "Local" / _MSIX_FAMILY_NAME / "LocalCache" / "logs"
    else:
        # Linux / macOS — used in CI and development
        base = Path.home() / ".local" / "share" / "school-tool" / "logs"

    base.mkdir(parents=True, exist_ok=True)
    return base


def configure_logging() -> Path:
    """Bootstrap the rotating file logger per ADR-0011.

    Returns the resolved log-file path so callers can display it in error
    banners without needing to reconstruct it.
    """
    debug = os.environ.get("SFTK_DEBUG", "").strip() == "1"
    level = logging.DEBUG if debug else logging.INFO

    log_dir = _log_dir()
    log_path = log_dir / _LOG_FILENAME

    root_logger = logging.getLogger()
    # Avoid adding duplicate handlers if called more than once (e.g., in tests).
    if any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root_logger.handlers):
        return log_path

    root_logger.setLevel(level)

    fmt = logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)
    root_logger.addHandler(file_handler)

    # Console handler for development / CI visibility
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_handler.setFormatter(fmt)
    root_logger.addHandler(console_handler)

    logging.getLogger(__name__).info(
        "Logging initialised → %s (level=%s)", log_path, logging.getLevelName(level)
    )

    return log_path
