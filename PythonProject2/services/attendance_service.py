"""
services/attendance_service.py
==============================
Handles business logic for attendance marking, check-in/out logic, and cooldowns.
"""

import threading
import time
from typing import Dict, Any, List, Optional
from datetime import date, datetime, timedelta
from core.database import Database
from core.logger import get_logger
from services.break_service import BreakService
import config

logger = get_logger(__name__)

class AttendanceService:
    def __init__(self, db: Database):
        self.db = db
        self.break_service = BreakService(db)
        
        # We still keep locks for thread safety per employee
        self._global_lock = threading.Lock()
        self._employee_locks: Dict[str, threading.Lock] = {}
        
        # Debounce cache to prevent blasting the DB with queries every frame
        # emp_id -> timestamp of last process
        self._debounce_cache: Dict[str, float] = {}
        self.debounce_seconds = 2.0 

    def _get_emp_lock(self, emp_id: str) -> threading.Lock:
        with self._global_lock:
            if emp_id not in self._employee_locks:
                self._employee_locks[emp_id] = threading.Lock()
            return self._employee_locks[emp_id]
            
    def _parse_time(self, time_str: str, default: str) -> datetime.time:
        try:
            return datetime.strptime(time_str, "%H:%M:%S").time()
        except ValueError:
            return datetime.strptime(default, "%H:%M:%S").time()

    def _calculate_net_working_hours(self, emp_id: str, check_in_dt: datetime, current_dt: datetime, lunch_in_dt: Optional[datetime]) -> float:
        base_seconds = (current_dt - check_in_dt).total_seconds()
        
        breaks = self.db._execute(
            "SELECT break_out, break_in FROM employee_breaks WHERE employee_id = %s AND break_date = %s",
            (emp_id, date.today()), fetch="all", dictionary=True
        )
        total_break_seconds = 0
        if breaks:
            for b in breaks:
                if b["break_in"] and b["break_out"]:
                    total_break_seconds += (b["break_in"] - b["break_out"]).total_seconds()
                    
        late_lunch_seconds = 0
        if lunch_in_dt:
            lunch_end_str = self.db.get_setting("LUNCH_END", "13:45:00")
            lunch_end = self._parse_time(lunch_end_str, "13:45:00")
            lunch_end_dt = datetime.combine(lunch_in_dt.date(), lunch_end)
            if lunch_in_dt > lunch_end_dt:
                late_lunch_seconds = (lunch_in_dt - lunch_end_dt).total_seconds()
                
        net_seconds = base_seconds - total_break_seconds - late_lunch_seconds
        return round(max(0, net_seconds) / 3600.0, 2)

    def mark_attendance(self, emp_id: str) -> bool:
        """
        State-driven attendance marking logic using dynamic timeline windows.
        """
        now = time.time()
        
        # Fast debounce to avoid hitting the DB 30 times a second per face
        if emp_id in self._debounce_cache and (now - self._debounce_cache[emp_id]) < self.debounce_seconds:
            return False
            
        self._debounce_cache[emp_id] = now
        emp_lock = self._get_emp_lock(emp_id)
        
        with emp_lock:
            try:
                # 1. Fetch Dynamic Settings
                shift_start_str = self.db.get_setting("SHIFT_START", "10:00:00")
                late_buffer_str = self.db.get_setting("LATE_BUFFER", "5")
                lunch_start_str = self.db.get_setting("LUNCH_START", "13:00:00")
                lunch_end_str = self.db.get_setting("LUNCH_END", "13:45:00")
                checkout_unlock_str = self.db.get_setting("CHECKOUT_UNLOCK", "16:45:00")
                
                shift_start = self._parse_time(shift_start_str, "10:00:00")
                lunch_start = self._parse_time(lunch_start_str, "13:00:00")
                lunch_end = self._parse_time(lunch_end_str, "13:45:00")
                checkout_unlock = self._parse_time(checkout_unlock_str, "16:45:00")
                
                try:
                    late_buffer_mins = int(late_buffer_str)
                except ValueError:
                    late_buffer_mins = 5
                    
                current_dt = datetime.now()
                current_t = current_dt.time()
                
                # Calculate the exact late threshold datetime for today
                shift_start_dt = datetime.combine(date.today(), shift_start)
                late_threshold_dt = shift_start_dt + timedelta(minutes=late_buffer_mins)
                
                # 2. Fetch Employee Record
                record = self.db.get_today_attendance_record(emp_id)
                
                # STATE 0: No Record -> Check-In
                if not record:
                    is_late = current_dt > late_threshold_dt
                    status = "Late" if is_late else "Present"
                    
                    self.db._execute(
                        """
                        INSERT INTO attendance (employee_id, attendance_date, check_in, status, is_late)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (emp_id, date.today(), current_dt, status, is_late)
                    )
                    logger.info(f"Check-IN recorded for {emp_id}. Status: {status}")
                    self.break_service._debounce_cache[emp_id] = time.time()
                    return True
                    
                # If they already checked out manually, don't auto-update anything else
                if record.get("manual_checkout"):
                    return False
                
                # Early Lunch Split Rectification
                t_1330 = datetime.strptime("13:30:00", "%H:%M:%S").time()
                if current_t > t_1330:
                    open_b = self.db._execute(
                        "SELECT id, break_out FROM employee_breaks WHERE employee_id = %s AND break_date = %s AND break_in IS NULL ORDER BY id DESC LIMIT 1",
                        (emp_id, date.today()), fetch="one", dictionary=True
                    )
                    if open_b:
                        b_out = open_b["break_out"]
                        t_1245 = datetime.combine(date.today(), datetime.strptime("12:45:00", "%H:%M:%S").time())
                        t_1300 = datetime.combine(date.today(), datetime.strptime("13:00:00", "%H:%M:%S").time())
                        
                        if t_1245 <= b_out <= t_1300:
                            # 1. Close open break tracking row
                            self.db._execute(
                                "UPDATE employee_breaks SET break_in = %s WHERE id = %s",
                                (t_1300, open_b["id"])
                            )
                            # 2. Write to main attendance row
                            new_status = "Late" if record.get("is_late") else "Present"
                            self.db.update_attendance_record(emp_id, {
                                "lunch_out": t_1300,
                                "lunch_in": current_dt,
                                "status": new_status
                            })
                            logger.info(f"Early Lunch Split rectified for {emp_id}")
                            return True
                
                # STATE 1: Morning Cooldown
                if current_t < lunch_start:
                    self.break_service.toggle_generic_break(emp_id)
                    return False
                    
                # STATE 2: Lunch Window
                if lunch_start <= current_t <= lunch_end:
                    if not record.get("lunch_out"):
                        self.db.update_attendance_record(emp_id, {"lunch_out": current_dt, "status": "Lunch Out"})
                        logger.info(f"Lunch OUT recorded for {emp_id}")
                        return True
                    elif record.get("lunch_out") and not record.get("lunch_in"):
                        # Use a 60-second debounce to prevent bouncing right at the door
                        time_since_lunch_out = (current_dt - record["lunch_out"]).total_seconds()
                        if time_since_lunch_out > 60:
                            status = "Late" if record.get("is_late") else "Present"
                            self.db.update_attendance_record(emp_id, {"lunch_in": current_dt, "status": status})
                            logger.info(f"Lunch IN recorded for {emp_id}")
                            return True
                    return False
                    
                # STATE 3: Afternoon Cooldown
                if current_t > lunch_end and current_t < checkout_unlock:
                    self.break_service.toggle_generic_break(emp_id)
                    return False
                    
                # STATE 4: Evening Window (Check-Out updates)
                if current_t >= checkout_unlock:
                    if record.get("lunch_out") and not record.get("lunch_in"):
                        time_since_lunch_out = (current_dt - record["lunch_out"]).total_seconds()
                        if time_since_lunch_out > 60:
                            status = "Late" if record.get("is_late") else "Present"
                            self.db.update_attendance_record(emp_id, {"lunch_in": current_dt, "status": status})
                            logger.info(f"Lunch IN recorded for {emp_id} (Late Return)")
                            return True
                        return False

                    open_break = self.db._execute(
                        "SELECT id FROM employee_breaks WHERE employee_id = %s AND break_date = %s AND break_in IS NULL",
                        (emp_id, date.today()), fetch="one"
                    )
                    if open_break:
                        self.break_service.toggle_generic_break(emp_id)
                        return False

                    check_in_dt = record["check_in"]
                    lunch_out_dt = record.get("lunch_out")
                    lunch_in_dt = record.get("lunch_in")
                    
                    net_hours = self._calculate_net_working_hours(emp_id, check_in_dt, current_dt, lunch_in_dt)
                    
                    self.db.update_attendance_record(emp_id, {
                        "check_out": current_dt, 
                        "status": "Checked Out",
                        "working_hours": net_hours
                    })
                    logger.info(f"Check-OUT updated for {emp_id} at {current_dt.strftime('%H:%M:%S')}")
                    return True
                    
                return False
                
            except Exception as e:
                logger.error(f"Failed to process attendance for {emp_id}: {e}")
                return False

    def force_checkout(self, emp_id: str) -> bool:
        """
        Manually override the time-lock window and check out an employee immediately.
        """
        emp_lock = self._get_emp_lock(emp_id)
        with emp_lock:
            try:
                record = self.db.get_today_attendance_record(emp_id)
                if not record or record.get("check_out"):
                    return False
                    
                current_dt = datetime.now()
                check_in_dt = record["check_in"]
                lunch_out_dt = record.get("lunch_out")
                lunch_in_dt = record.get("lunch_in")
                
                open_break = self.db._execute(
                    """
                    SELECT id, break_out 
                    FROM employee_breaks 
                    WHERE employee_id = %s AND break_date = %s AND break_in IS NULL
                    ORDER BY id DESC LIMIT 1
                    """,
                    (emp_id, date.today()),
                    fetch="one",
                    dictionary=True
                )
                
                real_now = datetime.now()
                shift_end_str = self.db.get_setting("SHIFT_END", "17:00:00")
                shift_end = self._parse_time(shift_end_str, "17:00:00")
                shift_end_dt = datetime.combine(date.today(), shift_end)
                lunch_start_str = self.db.get_setting("LUNCH_START", "13:00:00")
                lunch_start = self._parse_time(lunch_start_str, "13:00:00")
                
                is_pre_lunch_runner = False
                
                if open_break:
                    b_out = open_break["break_out"]
                    self.db._execute(
                        "UPDATE employee_breaks SET break_in = %s WHERE id = %s",
                        (b_out, open_break["id"])
                    )
                    if b_out.time() <= lunch_start:
                        is_pre_lunch_runner = True
                
                if lunch_out_dt and not lunch_in_dt:
                    self.db.update_attendance_record(emp_id, {"lunch_in": lunch_out_dt})
                    lunch_in_dt = lunch_out_dt

                if is_pre_lunch_runner:
                    current_dt = b_out
                elif real_now.time() < shift_end:
                    current_dt = real_now
                else:
                    if open_break:
                        current_dt = b_out
                    elif lunch_out_dt and not lunch_in_dt:
                        current_dt = lunch_out_dt
                    else:
                        current_dt = shift_end_dt

                net_hours = self._calculate_net_working_hours(emp_id, check_in_dt, current_dt, lunch_in_dt)
                
                self.db.update_attendance_record(emp_id, {
                    "check_out": current_dt,
                    "status": "Forced Out",
                    "manual_checkout": True,
                    "working_hours": net_hours
                })
                logger.info(f"Manual Force-OUT executed for {emp_id}")
                return True
            except Exception as e:
                logger.error(f"Error in force_checkout for {emp_id}: {e}")
                return False

    def get_today_attendance(self) -> List[Dict[str, Any]]:
        sql = """
            SELECT a.id, a.employee_id, e.employee_name, a.check_in, a.lunch_out, a.lunch_in, a.check_out, a.status 
            FROM attendance a
            JOIN employees e ON a.employee_id = e.employee_id
            WHERE a.attendance_date = CURDATE()
            ORDER BY a.check_in DESC
        """
        return self.db._execute(sql, (), fetch="all", dictionary=True)

    def get_attendance_for_date(self, target_date: date) -> List[Dict[str, Any]]:
        sql = """
            SELECT a.id, a.employee_id, e.employee_name, a.check_in, a.lunch_out, a.lunch_in, a.check_out, a.status 
            FROM attendance a
            JOIN employees e ON a.employee_id = e.employee_id
            WHERE a.attendance_date = %s
            ORDER BY a.check_in DESC
        """
        return self.db._execute(sql, (target_date,), fetch="all", dictionary=True)
