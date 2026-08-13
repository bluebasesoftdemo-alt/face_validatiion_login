"""
core/exceptions.py
==================
Custom exception hierarchy for the Attendance Management System.

All application-level errors inherit from ``AttendanceSystemError``,
so callers can catch the base type for a blanket handler or catch
specific sub-types for fine-grained recovery.

Example::

    from core.exceptions import EmployeeNotFoundError, DatabaseError

    try:
        db.get_employee_by_id("EMP99")
    except EmployeeNotFoundError as e:
        show_dialog("Employee not found", str(e))
    except DatabaseError as e:
        show_dialog("Database error", str(e))
"""


# ── Base ──────────────────────────────────────────────────────────────────────

class AttendanceSystemError(Exception):
    """
    Base class for all application-level exceptions.

    Catching this type handles any error raised by the system.
    """


# ── Database Layer ────────────────────────────────────────────────────────────

class DatabaseError(AttendanceSystemError):
    """
    Raised when a database operation fails unexpectedly.

    Wraps ``mysql.connector.Error`` with a human-readable message.
    """


class EmployeeNotFoundError(AttendanceSystemError):
    """
    Raised when an operation targets an employee ID that does not exist
    in the database.
    """


class DuplicateEmployeeError(AttendanceSystemError):
    """
    Raised when attempting to register an employee whose ID already
    exists in the database.
    """


# ── Camera Layer ──────────────────────────────────────────────────────────────

class CameraError(AttendanceSystemError):
    """
    Raised when the camera cannot be opened, or a frame cannot be read.
    """


# ── Face Recognition Layer ────────────────────────────────────────────────────

class FaceNotFoundError(AttendanceSystemError):
    """
    Raised when no face is detected in a frame where one is required
    (e.g. during employee registration quality checks).
    """


class FaceRecognitionError(AttendanceSystemError):
    """
    Raised when the face recognition engine fails to produce a valid
    embedding (e.g. model not loaded, corrupt frame).
    """


class LivenessError(AttendanceSystemError):
    """
    Raised when liveness detection determines the face is not from a
    live person (e.g. photo or screen replay detected).
    """


# ── Configuration Layer ───────────────────────────────────────────────────────

class ConfigurationError(AttendanceSystemError):
    """
    Raised when a required configuration value is missing or invalid.
    """


# ── Report Layer ──────────────────────────────────────────────────────────────

class ReportError(AttendanceSystemError):
    """
    Raised when an Excel or PDF report cannot be generated or saved.
    """
