"""
config.py
=========
Centralised project configuration.

All values are loaded from the .env file in the project root.
If a variable is absent from .env, a safe default is used.

Usage:
    import config
    print(config.DB_HOST)

Never import secrets (DB_PASSWORD, etc.) from anywhere except this module.
"""

import os
from datetime import time as _time
from pathlib import Path

from dotenv import load_dotenv

# ── Load .env ────────────────────────────────────────────────────────────────
# Finds the .env file in the same directory as this config.py file.
_BASE_DIR = Path(__file__).resolve().parent
load_dotenv(_BASE_DIR / ".env")

# ── Helpers ──────────────────────────────────────────────────────────────────

def _get(key: str, default: str = "") -> str:
    """Read an env variable; strip whitespace."""
    return os.getenv(key, default).strip()


def _get_int(key: str, default: int) -> int:
    try:
        return int(_get(key, str(default)))
    except ValueError:
        return default


def _get_float(key: str, default: float) -> float:
    try:
        return float(_get(key, str(default)))
    except ValueError:
        return default


def _parse_time(value: str, default: _time) -> _time:
    try:
        h, m = map(int, value.split(":"))
        return _time(h, m)
    except (ValueError, AttributeError):
        return default

# ── MySQL ─────────────────────────────────────────────────────────────────────
DB_HOST     = _get("DB_HOST",     "Local instance")
DB_USER     = _get("DB_USER",     "root")
DB_PASSWORD = _get("DB_PASSWORD", "")
DB_NAME     = _get("DB_NAME",     "facial_attendance")

# Connection pool — number of concurrent DB connections available.
# Increase if you add more background threads (e.g. multi-camera).
DB_POOL_SIZE = _get_int("DB_POOL_SIZE", 5)

# ── Camera ────────────────────────────────────────────────────────────────────
CAMERA_INDEX = _get_int("CAMERA_INDEX", 0)

# ── Face Recognition ──────────────────────────────────────────────────────────
# Cosine similarity threshold: faces with score >= this are considered a match.
# Raise to reduce false positives; lower to reduce false negatives.
SIMILARITY_THRESHOLD = _get_float("SIMILARITY_THRESHOLD", 0.5)

# InsightFace detection input size.
# (320, 320) is fast enough for real-time attendance; (640, 640) is more accurate.
DETECTION_SIZE = (320, 320)

# InsightFace model name — preserved as buffalo_l per project requirements.
INSIGHTFACE_MODEL = "buffalo_l"

# ── Blink / Liveness Detection ────────────────────────────────────────────────
# Eye Aspect Ratio threshold below which a blink is detected.
# Absorbed from blinkconfig.py (that file is kept for backward compat).
EAR_THRESHOLD    = _get_float("EAR_THRESHOLD",    0.21)
CONSECUTIVE_FRAMES = _get_int("CONSECUTIVE_FRAMES", 3)

# ── Attendance Rules ──────────────────────────────────────────────────────────
# Cooldown: seconds before the same employee can be recognised again in the
# live camera loop. Prevents duplicate check-ins from a single standing session.
ATTENDANCE_COOLDOWN = _get_int("ATTENDANCE_COOLDOWN", 5)

# Employees who check in after this time are flagged as late.
LATE_THRESHOLD_TIME: _time = _parse_time(
    _get("LATE_THRESHOLD", "10:00"),
    default=_time(10, 0),
)
# ── Registration ──────────────────────────────────────────────────────────────
# Number of face samples to capture and average during employee registration.
IMAGES_TO_CAPTURE = _get_int("IMAGES_TO_CAPTURE", 20)

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = _get("LOG_LEVEL", "INFO").upper()

# ── Folder Paths ──────────────────────────────────────────────────────────────
BASE_DIR = _BASE_DIR

KNOWN_FACES_DIR      = BASE_DIR / "known_faces"
MODEL_DIR            = BASE_DIR / "models"
LOG_DIR              = BASE_DIR / "logs"
EXPORT_DIR           = BASE_DIR / "exports"
EMPLOYEE_PHOTOS_DIR  = BASE_DIR / "assets" / "employee_photos"

# Create folders if they don't exist.
for _dir in (KNOWN_FACES_DIR, MODEL_DIR, LOG_DIR, EXPORT_DIR, EMPLOYEE_PHOTOS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)