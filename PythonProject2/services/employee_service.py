"""
services/employee_service.py
============================
Handles business logic for employee management.
"""

from typing import List, Dict, Any, Optional
import numpy as np
from core.database import Database
from core.exceptions import EmployeeNotFoundError
from core.logger import get_logger

logger = get_logger(__name__)

class EmployeeService:
    def __init__(self, db: Database):
        self.db = db

    def get_all_active_employees(self) -> List[Dict[str, Any]]:
        """
        Fetches all employees from the database.
        (In a future update, we can filter by `is_active=1` if soft-deletes are used).
        """
        logger.debug("Fetching all active employees via EmployeeService.")
        return self.db.get_all_employees()

    def get_employee_by_id(self, emp_id: str) -> Optional[Dict[str, Any]]:
        """Fetches a specific employee by ID."""
        sql = "SELECT * FROM employees WHERE employee_id = %s"
        return self.db._execute(sql, (emp_id,), fetch="one", dictionary=True)

    def register_employee(
        self, 
        emp_id: str, 
        name: str, 
        embedding: bytes, 
        department: str = None,
        position: str = None,
        photo_path: str = None
    ) -> bool:
        """
        Registers a new employee into the database.
        Ensures the employee doesn't already exist.
        """
        existing = self.get_employee_by_id(emp_id)
        if existing:
            logger.warning(f"Registration failed: Employee {emp_id} already exists.")
            return False
            
        try:
            self.db.add_employee(
                emp_id=emp_id,
                name=name,
                embedding=np.frombuffer(embedding, dtype=np.float32),
                department=department,
                position_title=position,
                photo_path=photo_path
            )
            logger.info(f"Successfully registered employee: {emp_id} ({name})")
            return True
        except Exception as e:
            logger.error(f"Failed to register employee {emp_id}: {e}")
            return False

    def update_employee_status(self, emp_id: str, is_active: bool) -> bool:
        """Soft-deletes or reactivates an employee."""
        sql = "UPDATE employees SET is_active = %s WHERE employee_id = %s"
        try:
            self.db._execute(sql, (is_active, emp_id), fetch="none")
            logger.info(f"Updated status for {emp_id} to active={is_active}")
            return True
        except Exception as e:
            logger.error(f"Failed to update status for {emp_id}: {e}")
            return False
