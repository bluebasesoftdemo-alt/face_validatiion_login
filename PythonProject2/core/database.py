"""
core/database.py
================
Thread-safe database access layer for the Attendance Management System.

Design decisions
----------------
- **Connection pooling**: A ``MySQLConnectionPool`` is created once at startup.
  Every public method acquires a connection, uses it, and releases it back to
  the pool — making all methods safe to call from multiple threads concurrently
  (GUI thread, camera thread, report thread, etc.).

- **Schema migration**: ``_migrate_schema()`` runs at startup and idempotently
  adds new columns / indexes to existing tables.  Existing data is never
  modified.  Migration errors for already-existing columns (errno 1060) or
  keys (errno 1061) are silently skipped.

- **Backward compatibility**: The original public interface is preserved:
  - ``get_all_employees()``  → list of {"id", "name", "embedding"} dicts
  - ``mark_check_in(emp_id)``
  - ``mark_check_out(emp_id)``
  - ``attendance_exists(emp_id)``
  - ``get_attendance()``
  - ``add_employee(emp_id, name, embedding)``
  - ``close()``              → no-op (pool manages connections)

- **InsightFace embeddings**: Stored and retrieved as raw float32 bytes, exactly
  as in the original code.  ``get_all_employees()`` returns numpy arrays.
"""

from __future__ import annotations

import numpy as np
import mysql.connector
from mysql.connector import pooling
from datetime import date, datetime
from typing import Any, Dict, List, Optional
import json
import config
from core.logger import get_logger
from core.exceptions import (
    DatabaseError,
    DuplicateEmployeeError,
    EmployeeNotFoundError,
)

logger = get_logger(__name__)

# ── MySQL error codes used in migration guards ────────────────────────────────
_ERR_DUP_COLUMN = 1060  # ER_DUP_FIELDNAME   — column already exists
_ERR_DUP_KEY = 1061  # ER_DUP_KEYNAME     — index/key already exists
_ERR_DUP_ENTRY = 1062  # ER_DUP_ENTRY       — UNIQUE constraint data conflict
_IGNORABLE_MIGRATION = {_ERR_DUP_COLUMN, _ERR_DUP_KEY}


class Database:
    """
    All-in-one database access object.

    Instantiate once and share across threads — all methods are thread-safe.

    Example::

        db = Database()
        employees = db.get_all_employees()   # for face recognition loop
        db.mark_check_in("EMP001")
    """

    def __init__(self) -> None:
        self._pool: Optional[pooling.MySQLConnectionPool] = None
        self._init_pool()
        self._setup_schema()
        logger.info("Database ready (pool_size=%d).", config.DB_POOL_SIZE)

    # ── Private: Pool ─────────────────────────────────────────────────────────

    def _init_pool(self) -> None:
        """Create the MySQL connection pool."""
        try:
            self._pool = pooling.MySQLConnectionPool(
                pool_name="att_pool",
                pool_size=config.DB_POOL_SIZE,
                pool_reset_session=True,
                host=config.DB_HOST,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                database=config.DB_NAME,
                autocommit=False,
            )
            logger.debug("Connection pool created.")
        except mysql.connector.Error as exc:
            logger.critical("Cannot connect to MySQL: %s", exc)
            raise DatabaseError(f"Cannot connect to database: {exc}") from exc

    def _get_conn(self) -> mysql.connector.MySQLConnection:
        """Borrow a connection from the pool."""
        try:
            return self._pool.get_connection()
        except mysql.connector.Error as exc:
            logger.error("Pool unavailable: %s", exc)
            raise DatabaseError(f"Database connection unavailable: {exc}") from exc

    def _execute(
            self,
            sql: str,
            params: tuple = (),
            fetch: str = "none",
            dictionary: bool = False,
    ) -> Any:
        """
        Unified SQL executor.

        Args:
            sql:        The SQL query string (use ``%s`` placeholders).
            params:     Bound parameters tuple.
            fetch:      ``"none"``  — write operation; commits and returns lastrowid.
                        ``"one"``   — returns one row (dict or tuple).
                        ``"all"``   — returns all rows (list of dicts or tuples).
            dictionary: If True, rows are returned as dicts keyed by column name.

        Returns:
            Depends on ``fetch``:
            - ``"none"``  → int (lastrowid)
            - ``"one"``   → dict / tuple / None
            - ``"all"``   → list of dicts / tuples

        Raises:
            DatabaseError: On any MySQL error.
        """
        conn = self._get_conn()
        cursor = None
        try:
            cursor = conn.cursor(dictionary=dictionary)
            cursor.execute(sql, params)

            if fetch == "one":
                return cursor.fetchone()
            if fetch == "all":
                return cursor.fetchall()

            # Write path
            conn.commit()
            return cursor.lastrowid

        except mysql.connector.Error as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.error(
                "SQL error [errno=%s]: %s | query=%.200s",
                exc.errno, exc.msg, sql.strip(),
            )
            raise DatabaseError(f"Database error ({exc.errno}): {exc.msg}") from exc
        finally:
            if cursor is not None:
                cursor.close()
            conn.close()

    # ── Private: Schema ───────────────────────────────────────────────────────

    def _setup_schema(self) -> None:
        """Create tables and apply migrations idempotently."""
        self._create_tables()
        self._migrate_schema()

    def _create_tables(self) -> None:
        """
        Create the two core tables if they don't exist yet.

        This is identical to the original ``create_tables()`` plus a
        CASCADE delete rule on the attendance foreign key so that
        deleting an employee cleans up their attendance records.
        """
        conn = self._get_conn()
        cursor = None
        try:
            cursor = conn.cursor()

            # employees — unchanged original schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS employees (
                    employee_id   VARCHAR(20)  PRIMARY KEY,
                    employee_name VARCHAR(100) NOT NULL,
                    embedding     LONGBLOB     NOT NULL,
                    created_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # attendance — original schema + ON DELETE CASCADE
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS attendance (
                    id              INT AUTO_INCREMENT PRIMARY KEY,
                    employee_id     VARCHAR(20),
                    attendance_date DATE,
                    check_in        DATETIME,
                    check_out       DATETIME,
                    status          VARCHAR(20),
                    FOREIGN KEY (employee_id)
                        REFERENCES employees(employee_id)
                        ON DELETE CASCADE
                )
            """)

            # employee_faces — new table for multiple faces
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS employee_faces (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    employee_id VARCHAR(20),
                    embedding LONGBLOB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (employee_id)
                        REFERENCES employees(employee_id)
                        ON DELETE CASCADE
                )
            """)

            # employee_breaks — isolated general break tracker
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS employee_breaks (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    employee_id VARCHAR(20),
                    break_date DATE NOT NULL,
                    break_out DATETIME NOT NULL,
                    break_in DATETIME NULL,
                    FOREIGN KEY (employee_id)
                        REFERENCES employees(employee_id)
                        ON DELETE CASCADE
                )
            """)

            # system_settings — table for dynamic configuration
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_settings (
                    setting_key VARCHAR(100) PRIMARY KEY,
                    setting_value VARCHAR(255) NOT NULL
                )
            """)

            # Initialize Default Shift End
            cursor.execute("""
                INSERT IGNORE INTO system_settings (setting_key, setting_value)
                VALUES ('SHIFT_END', '15:00:00')
            """)

            # exam_reports — stores the outcome of each proctored test session
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS exam_reports (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    candidate_id VARCHAR(20),
                    session_start DATETIME,
                    session_end DATETIME,
                    status VARCHAR(20),
                    violation_count INT,
                    violation_log TEXT
                )
            """)

            # candidates — stores each candidate's enrolled face for identity verification
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS candidates (
                    candidate_id VARCHAR(20) PRIMARY KEY,
                    candidate_name VARCHAR(100) NOT NULL,
                    embedding BLOB NOT NULL,
                    registered_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()
            logger.debug("Core tables verified.")

        except mysql.connector.Error as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            raise DatabaseError(f"Table creation failed: {exc}") from exc
        finally:
            if cursor:
                cursor.close()
            conn.close()

    def _migrate_schema(self) -> None:
        """
        Add new columns, indexes, and constraints to existing tables.

        Each statement is attempted independently.  If a column or key already
        exists the error is silently ignored so re-running the application on an
        already-migrated database is safe.

        If the UNIQUE constraint cannot be added because duplicate attendance
        records already exist, a warning is logged instead of raising.
        """
        migrations: List[str] = [
            # ── Employee profile columns ──────────────────────────────────
            "ALTER TABLE employees ADD COLUMN department     VARCHAR(100)  NULL",
            "ALTER TABLE employees ADD COLUMN position_title VARCHAR(100)  NULL",
            "ALTER TABLE employees ADD COLUMN email          VARCHAR(150)  NULL",
            "ALTER TABLE employees ADD COLUMN phone          VARCHAR(20)   NULL",
            "ALTER TABLE employees ADD COLUMN photo_path     VARCHAR(255)  NULL",
            "ALTER TABLE employees ADD COLUMN is_active      BOOLEAN       NOT NULL DEFAULT TRUE",
            "ALTER TABLE employees ADD COLUMN updated_at     TIMESTAMP     NULL DEFAULT NULL"
            "                                                ON UPDATE CURRENT_TIMESTAMP",
            # ── Attendance extended columns ───────────────────────────────
            "ALTER TABLE attendance ADD COLUMN working_hours DECIMAL(5,2)  NULL",
            "ALTER TABLE attendance ADD COLUMN is_late       BOOLEAN       NOT NULL DEFAULT FALSE",
            "ALTER TABLE attendance ADD COLUMN lunch_out     DATETIME      NULL",
            "ALTER TABLE attendance ADD COLUMN lunch_in      DATETIME      NULL",
            "ALTER TABLE attendance ADD COLUMN manual_checkout BOOLEAN     NOT NULL DEFAULT FALSE",
            # ── UNIQUE constraint: one record per employee per day ────────
            "ALTER TABLE attendance ADD UNIQUE KEY uq_emp_date (employee_id, attendance_date)",
            # ── Performance indexes ───────────────────────────────────────
            "CREATE INDEX idx_att_date   ON attendance(attendance_date)",
            "CREATE INDEX idx_att_emp_id ON attendance(employee_id)",
        ]

        conn = self._get_conn()
        cursor = None
        try:
            cursor = conn.cursor()
            for sql in migrations:
                try:
                    cursor.execute(sql)
                    conn.commit()
                    logger.debug("Migration applied: %.90s ...", sql[:90])
                except mysql.connector.Error as exc:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    if exc.errno in _IGNORABLE_MIGRATION:
                        logger.debug("Migration skipped (already applied): %.90s ...", sql[:90])
                    elif exc.errno == _ERR_DUP_ENTRY:
                        logger.warning(
                            "Cannot add UNIQUE constraint — duplicate attendance records "
                            "exist in the database. The constraint will not be enforced at "
                            "DB level, but the application-level guard remains active."
                        )
                    else:
                        logger.warning(
                            "Unexpected migration error [errno=%d]: %s | sql=%.90s",
                            exc.errno, exc.msg, sql[:90],
                        )

            # Migrate existing embeddings to employee_faces safely
            try:
                cursor.execute("SELECT employee_id, embedding FROM employees")
                existing_emps = cursor.fetchall()
                for emp_id, emb_blob in existing_emps:
                    cursor.execute("SELECT id FROM employee_faces WHERE employee_id = %s LIMIT 1", (emp_id,))
                    if not cursor.fetchone():
                        cursor.execute("INSERT INTO employee_faces (employee_id, embedding) VALUES (%s, %s)",
                                       (emp_id, emb_blob))
                conn.commit()
            except mysql.connector.Error as exc:
                try:
                    conn.rollback()
                except Exception:
                    pass
                logger.warning("Failed to migrate existing embeddings: %s", exc)

        finally:
            if cursor:
                cursor.close()
            conn.close()

    # ── System Settings ───────────────────────────────────────────────────────

    def get_setting(self, key: str, default: str = "") -> str:
        """
        Fetch a configuration value from the system_settings table.
        """
        row = self._execute(
            "SELECT setting_value FROM system_settings WHERE setting_key = %s",
            (key,),
            fetch="one",
            dictionary=True
        )
        if row and "setting_value" in row:
            return row["setting_value"]
        return default

    def set_setting(self, key: str, value: str) -> None:
        """
        Set or update a configuration value in the system_settings table.
        """
        self._execute(
            """
            INSERT INTO system_settings (setting_key, setting_value)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)
            """,
            (key, value)
        )
        logger.info("Setting updated: %s = %s", key, value)

    # ── Employee CRUD ─────────────────────────────────────────────────────────

    def add_employee(
            self,
            emp_id: str,
            name: str,
            embedding: np.ndarray,
            department: str = "",
            position_title: str = "",
            email: str = "",
            phone: str = "",
            photo_path: str = "",
    ) -> None:
        """
        Register a new employee with their face embedding.

        This method signature is backward-compatible with the original:
        ``db.add_employee(emp_id, name, embedding)`` still works.
        The extra keyword arguments are optional.

        Args:
            emp_id:         Unique employee identifier (e.g. "EMP001").
            name:           Full display name.
            embedding:      InsightFace 512-d float32 embedding array.
            department:     Department name (optional).
            position_title: Job title (optional).
            email:          Work email (optional).
            phone:          Contact number (optional).
            photo_path:     Relative path to saved profile photo (optional).

        Raises:
            DuplicateEmployeeError: If emp_id already exists.
            DatabaseError:          On any other database failure.
        """
        emb_bytes = embedding.astype(np.float32).tobytes()

        if not self.employee_exists(emp_id):
            self._execute(
                """
                INSERT INTO employees
                    (employee_id, employee_name, embedding,
                     department, position_title, email, phone, photo_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    emp_id, name, emb_bytes,
                    department or None,
                    position_title or None,
                    email or None,
                    phone or None,
                    photo_path or None,
                ),
            )
            logger.info("Employee registered: %s — %s", emp_id, name)

        self._execute(
            "INSERT INTO employee_faces (employee_id, embedding) VALUES (%s, %s)",
            (emp_id, emb_bytes)
        )
        logger.info("Face embedding added to employee_faces: %s", emp_id)

    def get_all_employees(self) -> List[Dict[str, Any]]:
        """
        Return all *active* employees with their face embeddings.

        The returned format is identical to the original and is what
        ``FaceRecognizer.recognize()`` expects::

            [
                {"id": "EMP001", "name": "Alice", "embedding": np.ndarray},
                ...
            ]

        Employees with ``is_active = FALSE`` are excluded so that deactivated
        staff are not recognised by the camera.
        """
        rows = self._execute(
            """
            SELECT e.employee_id, e.employee_name, f.embedding
            FROM   employees e
            JOIN   employee_faces f ON e.employee_id = f.employee_id
            WHERE  e.is_active = TRUE
            """,
            fetch="all",
            dictionary=False,
        ) or []

        result: List[Dict[str, Any]] = []
        for emp_id, emp_name, emb_blob in rows:
            try:
                emb = np.frombuffer(emb_blob, dtype=np.float32).copy()
                result.append({"id": emp_id, "name": emp_name, "embedding": emb})
            except Exception as exc:
                logger.error(
                    "Skipping employee %s — embedding deserialization failed: %s",
                    emp_id, exc,
                )
        return result

    def get_all_employees_info(self) -> List[Dict[str, Any]]:
        """
        Return all employees as display records (without the embedding blob).

        Safe for GUI tables, search results, and reports.
        Includes both active and inactive employees.
        """
        return self._execute(
            """
            SELECT employee_id, employee_name, department, position_title,
                   email, phone, photo_path, is_active, created_at
            FROM   employees
            ORDER  BY employee_name
            """,
            fetch="all",
            dictionary=True,
        ) or []

    def get_employee_by_id(self, emp_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a single employee record by ID (no embedding).

        Returns:
            A dict with employee fields, or ``None`` if not found.
        """
        return self._execute(
            """
            SELECT employee_id, employee_name, department, position_title,
                   email, phone, photo_path, is_active, created_at
            FROM   employees
            WHERE  employee_id = %s
            """,
            (emp_id,),
            fetch="one",
            dictionary=True,
        )

    def update_employee(
            self,
            emp_id: str,
            name: Optional[str] = None,
            department: Optional[str] = None,
            position_title: Optional[str] = None,
            email: Optional[str] = None,
            phone: Optional[str] = None,
            photo_path: Optional[str] = None,
    ) -> None:
        """
        Update employee profile fields.

        Only keyword arguments that are not ``None`` are written to the database,
        so callers can update a single field without touching the others.

        Raises:
            EmployeeNotFoundError: If the employee ID does not exist.
        """
        if not self.employee_exists(emp_id):
            raise EmployeeNotFoundError(f"Employee '{emp_id}' not found.")

        fields, params = [], []
        for col, val in (
                ("employee_name", name),
                ("department", department),
                ("position_title", position_title),
                ("email", email),
                ("phone", phone),
                ("photo_path", photo_path),
        ):
            if val is not None:
                fields.append(f"{col} = %s")
                params.append(val)

        if not fields:
            return  # nothing to update

        params.append(emp_id)
        self._execute(
            f"UPDATE employees SET {', '.join(fields)} WHERE employee_id = %s",
            tuple(params),
        )
        logger.info("Employee updated: %s | fields=%s", emp_id, [f.split(" =")[0] for f in fields])

    def delete_employee(self, emp_id: str, hard_delete: bool = False) -> None:
        """
        Remove or deactivate an employee.

        Args:
            emp_id:      Employee to remove.
            hard_delete: If ``True``, permanently delete the row and all
                         their attendance records (CASCADE).
                         If ``False`` (default), set ``is_active = FALSE``
                         so historical attendance data is preserved.

        Raises:
            EmployeeNotFoundError: If the employee ID does not exist.
        """
        if not self.employee_exists(emp_id):
            raise EmployeeNotFoundError(f"Employee '{emp_id}' not found.")

        if hard_delete:
            self._execute(
                "DELETE FROM employees WHERE employee_id = %s", (emp_id,)
            )
            logger.warning("Employee permanently deleted: %s", emp_id)
        else:
            self._execute(
                "UPDATE employees SET is_active = FALSE WHERE employee_id = %s",
                (emp_id,),
            )
            logger.info("Employee deactivated (soft-delete): %s", emp_id)

    def employee_exists(self, emp_id: str) -> bool:
        """Return ``True`` if an employee with this ID exists (active or inactive)."""
        row = self._execute(
            "SELECT 1 FROM employees WHERE employee_id = %s",
            (emp_id,),
            fetch="one",
            dictionary=False,
        )
        return row is not None

    def search_employees(self, query: str) -> List[Dict[str, Any]]:
        """
        Partial, case-insensitive search across employee_id, name,
        department, and email.

        Args:
            query: The search string (e.g. "ali", "EMP0", "Engineering").

        Returns:
            List of matching employee records (no embeddings).
        """
        like = f"%{query}%"
        return self._execute(
            """
            SELECT employee_id, employee_name, department, position_title,
                   email, phone, photo_path, is_active, created_at
            FROM   employees
            WHERE  employee_id    LIKE %s
               OR  employee_name  LIKE %s
               OR  department     LIKE %s
               OR  email          LIKE %s
            ORDER  BY employee_name
            """,
            (like, like, like, like),
            fetch="all",
            dictionary=True,
        ) or []

    def update_embedding(self, emp_id: str, embedding: np.ndarray) -> None:
        """
        Replace the face embedding for an existing employee.

        Use this when re-registering an employee's face without changing
        other profile data.

        Raises:
            EmployeeNotFoundError: If the employee ID does not exist.
        """
        if not self.employee_exists(emp_id):
            raise EmployeeNotFoundError(f"Employee '{emp_id}' not found.")
        self._execute(
            "UPDATE employees SET embedding = %s WHERE employee_id = %s",
            (embedding.astype(np.float32).tobytes(), emp_id),
        )
        logger.info("Face embedding updated for employee: %s", emp_id)

    # ── Attendance Operations ─────────────────────────────────────────────────

    def attendance_exists(self, emp_id: str) -> bool:
        """Return ``True`` if the employee already has a record for today."""
        row = self._execute(
            "SELECT id FROM attendance WHERE employee_id = %s AND attendance_date = %s",
            (emp_id, date.today()),
            fetch="one",
            dictionary=False,
        )
        return row is not None

    def is_currently_checked_in(self, emp_id: str) -> bool:
        """Return ``True`` if the employee is currently checked in (status = 'Present')."""
        row = self._execute(
            "SELECT id FROM attendance WHERE employee_id = %s AND attendance_date = %s AND status = 'Present'",
            (emp_id, date.today()),
            fetch="one",
            dictionary=False,
        )
        return row is not None

    def has_checked_out_today(self, emp_id: str) -> bool:
        """Return ``True`` if the employee has checked out today (checkout_time is NOT NULL)."""
        row = self._execute(
            "SELECT id FROM attendance WHERE employee_id = %s AND attendance_date = %s AND check_out IS NOT NULL",
            (emp_id, date.today()),
            fetch="one",
            dictionary=False,
        )
        return row is not None

    # ── Candidate CRUD (for the online assessment / proctoring website) ───────

    def add_candidate(self, candidate_id: str, name: str, embedding: np.ndarray) -> None:
        """
        Registers a candidate's face for identity verification later.
        Mirrors add_employee() exactly, just for candidates instead of staff.
        """
        emb_bytes = embedding.astype(np.float32).tobytes()
        self._execute(
            """
            INSERT INTO candidates (candidate_id, candidate_name, embedding)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE candidate_name = %s, embedding = %s
            """,
            (candidate_id, name, emb_bytes, name, emb_bytes),
        )
        logger.info("Candidate registered: %s — %s", candidate_id, name)

    def get_all_candidates(self) -> List[Dict[str, Any]]:
        """
        Returns all candidates in the exact format FaceRecognizer.recognize()
        expects::

            [
                {"id": "TEST001", "name": "Alice", "embedding": np.ndarray},
                ...
            ]
        """
        rows = self._execute(
            "SELECT candidate_id, candidate_name, embedding FROM candidates",
            fetch="all",
            dictionary=False,
        ) or []

        result: List[Dict[str, Any]] = []
        for cand_id, cand_name, emb_blob in rows:
            try:
                emb = np.frombuffer(emb_blob, dtype=np.float32).copy()
                result.append({"id": cand_id, "name": cand_name, "embedding": emb})
            except Exception as exc:
                logger.error(
                    "Skipping candidate %s — embedding deserialization failed: %s",
                    cand_id, exc,
                )
        return result

    def save_exam_report(self, candidate_id, session_start, session_end, status, violation_count, violation_log):
        """
        Saves the outcome of one proctored exam session.
        violation_log: a list of dicts like [{"type": "no_face", "timestamp": "..."}]
        """
        self._execute(
            """
            INSERT INTO exam_reports
                (candidate_id, session_start, session_end, status, violation_count, violation_log)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (candidate_id, session_start, session_end, status, violation_count, json.dumps(violation_log)),
        )
        logger.info("Exam report saved: %s (%s, %d violations)", candidate_id, status, violation_count)

    def mark_check_in(self, emp_id: str) -> bool:
        """
        Record a check-in for today.

        Automatically detects late arrivals by comparing the current time
        against ``config.LATE_THRESHOLD_TIME``.

        Args:
            emp_id: The employee to mark present.

        Returns:
            ``True``  — check-in was recorded.
            ``False`` — employee already checked in today (no-op).
        """
        if self.attendance_exists(emp_id):
            logger.debug("Check-in skipped (duplicate): %s", emp_id)
            return False

        now = datetime.now()
        is_late = now.time() > config.LATE_THRESHOLD_TIME

        self._execute(
            """
            INSERT INTO attendance
                (employee_id, attendance_date, check_in, status, is_late)
            VALUES (%s, %s, %s, 'Present', %s)
            """,
            (emp_id, date.today(), now, is_late),
        )
        flag = "LATE" if is_late else "ON TIME"
        logger.info("Check-in [%s]: %s at %s", flag, emp_id, now.strftime("%H:%M:%S"))
        return True

    def mark_check_out(self, emp_id: str) -> bool:
        """
        Record a check-out for today and compute working hours.

        Working hours are stored as a ``DECIMAL(5,2)`` (e.g. 8.50 = 8 h 30 min).

        Returns:
            ``True``  — check-out recorded.
            ``False`` — no check-in found for today, or already checked out.
        """
        row = self._execute(
            """
            SELECT id, check_in, check_out
            FROM   attendance
            WHERE  employee_id     = %s
              AND  attendance_date = %s
            """,
            (emp_id, date.today()),
            fetch="one",
            dictionary=True,
        )

        if row is None:
            logger.debug("Check-out skipped (no check-in found): %s", emp_id)
            return False

        if row["check_out"] is not None:
            logger.debug("Check-out skipped (already finalized): %s", emp_id)
            return False

        now = datetime.now()
        check_in_dt = row["check_in"]
        working_hrs = None

        if isinstance(check_in_dt, datetime):
            delta = now - check_in_dt
            working_hrs = round(delta.total_seconds() / 3600, 2)

        self._execute(
            """
            UPDATE attendance
            SET    check_out = %s, working_hours = %s, status = 'Checked Out'
            WHERE  employee_id     = %s
              AND  attendance_date = %s
            """,
            (now, working_hrs, emp_id, date.today()),
        )
        logger.info(
            "Check-out: %s at %s (%.2f hrs worked)",
            emp_id, now.strftime("%H:%M:%S"), working_hrs or 0,
        )
        return True

    # ── Attendance Queries ────────────────────────────────────────────────────

    def get_today_attendance_record(self, emp_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the current day's raw attendance row for an employee."""
        return self._execute(
            """
            SELECT id, employee_id, attendance_date, check_in, lunch_out, lunch_in, check_out, status, working_hours, is_late, manual_checkout
            FROM attendance
            WHERE employee_id = %s AND attendance_date = %s
            """,
            (emp_id, date.today()),
            fetch="one",
            dictionary=True
        )

    def update_attendance_record(self, emp_id: str, updates: dict) -> None:
        """Dynamically update an employee's today record."""
        if not updates:
            return

        fields = []
        params = []
        for k, v in updates.items():
            fields.append(f"{k} = %s")
            params.append(v)

        params.append(emp_id)
        params.append(date.today())

        sql = f"UPDATE attendance SET {', '.join(fields)} WHERE employee_id = %s AND attendance_date = %s"
        self._execute(sql, tuple(params))
        logger.debug(f"Updated attendance record for {emp_id}: {list(updates.keys())}")

    def close_yesterday_shifts(self) -> None:
        """
        Flag previous day's shifts where lunch_out exists but lunch_in is missing,
        or where check_out is missing, as 'Incomplete Shift'.
        Calculates partial hours up to lunch_out if applicable.
        """
        # We find records before today where check_out is NULL
        sql_find = """
            SELECT id, check_in, lunch_out, lunch_in, check_out 
            FROM attendance 
            WHERE attendance_date < CURDATE() 
              AND (check_out IS NULL OR (lunch_out IS NOT NULL AND lunch_in IS NULL))
              AND status != 'Incomplete Shift'
        """
        open_shifts = self._execute(sql_find, (), fetch="all", dictionary=True)

        for row in (open_shifts or []):
            hours = None
            if row.get("lunch_out") and row.get("check_in"):
                delta = row["lunch_out"] - row["check_in"]
                hours = round(delta.total_seconds() / 3600, 2)

            self._execute(
                "UPDATE attendance SET status = 'Incomplete Shift', working_hours = %s WHERE id = %s",
                (hours, row["id"])
            )

        if open_shifts:
            logger.info(f"Closed {len(open_shifts)} incomplete shifts from previous days.")

    def get_attendance(self) -> List[tuple]:
        """
        Return all attendance records as tuples.

        **Preserved for backward compatibility** — original callers and the
        existing GUI (if any) that unpack as (emp_id, name, date, in, out, status)
        will continue to work unchanged.
        """
        return self._execute(
            """
            SELECT a.employee_id, e.employee_name,
                   a.attendance_date, a.check_in, a.check_out, a.status
            FROM   attendance a
            JOIN   employees  e ON a.employee_id = e.employee_id
            ORDER  BY a.attendance_date DESC, a.employee_id
            """,
            fetch="all",
            dictionary=False,
        ) or []

    def get_attendance_by_date(self, target_date: date) -> List[Dict[str, Any]]:
        """Return all attendance records for a specific date as dicts."""
        return self._execute(
            """
            SELECT a.id, a.employee_id, e.employee_name, e.department,
                   a.attendance_date, a.check_in, a.check_out,
                   a.status, a.working_hours, a.is_late
            FROM   attendance a
            JOIN   employees  e ON a.employee_id = e.employee_id
            WHERE  a.attendance_date = %s
            ORDER  BY a.check_in
            """,
            (target_date,),
            fetch="all",
            dictionary=True,
        ) or []

    def get_attendance_by_employee(
            self,
            emp_id: str,
            start_date: Optional[date] = None,
            end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return attendance history for one employee.

        Args:
            emp_id:      Employee ID to query.
            start_date:  Optional lower bound (inclusive).
            end_date:    Optional upper bound (inclusive).
        """
        params: List[Any] = [emp_id]
        sql = """
            SELECT a.id, a.employee_id, e.employee_name,
                   a.attendance_date, a.check_in, a.check_out,
                   a.status, a.working_hours, a.is_late
            FROM   attendance a
            JOIN   employees  e ON a.employee_id = e.employee_id
            WHERE  a.employee_id = %s
        """
        if start_date:
            sql += " AND a.attendance_date >= %s"
            params.append(start_date)
        if end_date:
            sql += " AND a.attendance_date <= %s"
            params.append(end_date)
        sql += " ORDER BY a.attendance_date DESC"

        return self._execute(sql, tuple(params), fetch="all", dictionary=True) or []

    def get_attendance_range(
            self, start_date: date, end_date: date
    ) -> List[Dict[str, Any]]:
        """Return all attendance records between two dates (inclusive)."""
        return self._execute(
            """
            SELECT a.id, a.employee_id, e.employee_name, e.department,
                   a.attendance_date, a.check_in, a.check_out,
                   a.status, a.working_hours, a.is_late
            FROM   attendance a
            JOIN   employees  e ON a.employee_id = e.employee_id
            WHERE  a.attendance_date BETWEEN %s AND %s
            ORDER  BY a.attendance_date DESC, e.employee_name
            """,
            (start_date, end_date),
            fetch="all",
            dictionary=True,
        ) or []

    def get_today_stats(self) -> Dict[str, int]:
        """
        Return today's attendance summary.

        Returns:
            ``{"total": int, "present": int, "absent": int, "late": int}``

        The ``absent`` count is ``total_active_employees - present_today``.
        """
        total_row = self._execute(
            "SELECT COUNT(*) FROM employees WHERE is_active = TRUE",
            fetch="one",
            dictionary=False,
        )
        total = total_row[0] if total_row else 0

        today = date.today()

        present_row = self._execute(
            "SELECT COUNT(*) FROM attendance WHERE attendance_date = %s AND status = 'Present'",
            (today,),
            fetch="one",
            dictionary=False,
        )
        present = present_row[0] if present_row else 0

        late_row = self._execute(
            "SELECT COUNT(*) FROM attendance WHERE attendance_date = %s AND is_late = TRUE",
            (today,),
            fetch="one",
            dictionary=False,
        )
        late = late_row[0] if late_row else 0

        return {
            "total": total,
            "present": present,
            "absent": total - present,
            "late": late,
        }

    def get_monthly_stats(self, year: int, month: int) -> Dict[str, Any]:
        """
        Return aggregate attendance statistics for a calendar month.

        Returns:
            Dict with: ``total_employees``, ``present_count``, ``late_count``,
            ``avg_working_hours``, ``total_records``.
        """
        row = self._execute(
            """
            SELECT
                COUNT(DISTINCT a.employee_id) AS present_count,
                COUNT(CASE WHEN a.is_late THEN 1 END) AS late_count,
                AVG(a.working_hours)  AS avg_working_hours,
                COUNT(*)              AS total_records
            FROM attendance a
            WHERE YEAR(a.attendance_date)  = %s
              AND MONTH(a.attendance_date) = %s
              AND a.status = 'Present'
            """,
            (year, month),
            fetch="one",
            dictionary=True,
        )

        total_emp_row = self._execute(
            "SELECT COUNT(*) FROM employees WHERE is_active = TRUE",
            fetch="one",
            dictionary=False,
        )
        total_employees = total_emp_row[0] if total_emp_row else 0

        if row:
            return {
                "total_employees": total_employees,
                "present_count": row.get("present_count") or 0,
                "late_count": row.get("late_count") or 0,
                "avg_working_hours": round(float(row.get("avg_working_hours") or 0.0), 2),
                "total_records": row.get("total_records") or 0,
            }
        return {
            "total_employees": total_employees,
            "present_count": 0,
            "late_count": 0,
            "avg_working_hours": 0.0,
            "total_records": 0,
        }

    def get_recent_activity(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Return the most recent ``limit`` check-in records.

        Used by the dashboard to display live activity.
        """
        return self._execute(
            """
            SELECT a.employee_id, e.employee_name,
                   a.attendance_date, a.check_in, a.check_out,
                   a.status, a.is_late
            FROM   attendance a
            JOIN   employees  e ON a.employee_id = e.employee_id
            ORDER  BY a.check_in DESC
            LIMIT  %s
            """,
            (limit,),
            fetch="all",
            dictionary=True,
        ) or []

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        """
        No-op kept for backward compatibility.

        With connection pooling, connections are returned to the pool
        automatically after every operation.  There is nothing to close.
        """
        logger.debug("Database.close() called — no action needed with pooled connections.")