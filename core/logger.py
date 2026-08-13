"""
core/logger.py
==============
Application-wide logging configuration.

Usage anywhere in the project:
    from core.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Something happened")
    logger.error("Something went wrong: %s", error)

Log files are written to:  <project_root>/logs/attendance_system.log
  - Rotated at 5 MB, keeping the last 5 files.
  - Console handler level is controlled by config.LOG_LEVEL.
  - File handler always captures DEBUG and above.
"""

import logging
import logging.handlers
from pathlib import Path

import config

# ── Constants ─────────────────────────────────────────────────────────────────
_ROOT_LOGGER_NAME = "attendance_system"
_LOG_FILE         = config.LOG_DIR / "attendance_system.log"
_MAX_BYTES        = 5 * 1024 * 1024   # 5 MB per log file
_BACKUP_COUNT     = 5                 # keep last 5 rotated files

_FILE_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
)
_CONSOLE_FORMAT = "%(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# ── Internal Setup ────────────────────────────────────────────────────────────

def _build_root_logger() -> logging.Logger:
    """
    Configure the root application logger exactly once.
    Subsequent calls return the already-configured logger without adding
    duplicate handlers.
    """
    root = logging.getLogger(_ROOT_LOGGER_NAME)

    if root.handlers:
        # Already configured — avoid adding duplicate handlers.
        return root

    root.setLevel(logging.DEBUG)  # capture everything; handlers filter

    # ── Console Handler ───────────────────────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_level   = getattr(logging, config.LOG_LEVEL, logging.INFO)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(
        logging.Formatter(_CONSOLE_FORMAT)
    )

    # ── Rotating File Handler ─────────────────────────────────────────────────
    file_handler = logging.handlers.RotatingFileHandler(
        _LOG_FILE,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(_FILE_FORMAT, datefmt=_DATE_FORMAT)
    )

    root.addHandler(console_handler)
    root.addHandler(file_handler)

    root.info(
        "Logger initialised — file: %s | console level: %s",
        _LOG_FILE,
        config.LOG_LEVEL,
    )
    return root


# ── Public API ────────────────────────────────────────────────────────────────

def get_logger(name: str) -> logging.Logger:
    """
    Return a named child logger under the application root.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A configured :class:`logging.Logger` instance.

    Example::

        from core.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Employee %s checked in.", emp_id)
    """
    _build_root_logger()  # idempotent
    return logging.getLogger(f"{_ROOT_LOGGER_NAME}.{name}")
