"""
services/break_service.py
=========================
Isolated module to track general employee breaks and calculate remaining hours.
"""

import time
from typing import Optional
from datetime import date, datetime
from core.database import Database
from core.logger import get_logger

logger = get_logger(__name__)

class BreakService:
    def __init__(self, db: Database):
        self.db = db
        self._debounce_cache = {}
        self.debounce_seconds = 60.0

    def toggle_generic_break(self, emp_id: str) -> None:
        """
        Toggles a generic break OUT and IN during standard cooldown windows.
        Includes a 60-second debounce to prevent bouncing.
        """
        now = time.time()
        
        if emp_id in self._debounce_cache:
            if (now - self._debounce_cache[emp_id]) < self.debounce_seconds:
                return
                
        self._debounce_cache[emp_id] = now
        
        try:
            # Check for today's latest row for this employee in employee_breaks
            row = self.db._execute(
                """
                SELECT id, break_out, break_in 
                FROM employee_breaks 
                WHERE employee_id = %s AND break_date = %s
                ORDER BY id DESC LIMIT 1
                """,
                (emp_id, date.today()),
                fetch="one",
                dictionary=True
            )
            
            current_dt = datetime.now()
            
            if row and row["break_in"] is None:
                # Update that row's break_in = NOW()
                self.db._execute(
                    "UPDATE employee_breaks SET break_in = %s WHERE id = %s",
                    (current_dt, row["id"])
                )
                logger.info(f"General Break IN recorded for {emp_id}")
            else:
                # Insert a brand new row with break_out = NOW()
                self.db._execute(
                    """
                    INSERT INTO employee_breaks (employee_id, break_date, break_out)
                    VALUES (%s, %s, %s)
                    """,
                    (emp_id, date.today(), current_dt)
                )
                logger.info(f"General Break OUT recorded for {emp_id}")
                
        except Exception as e:
            logger.error(f"Failed to toggle generic break for {emp_id}: {e}")

    def get_remaining_hours(self, emp_id: str) -> str:
        """
        Calculates the precise hours and minutes remaining for an 8-hour shift,
        factoring in all completed break durations.
        """
        try:
            # Fetch today's initial morning check_in
            att_record = self.db.get_today_attendance_record(emp_id)
            if not att_record or not att_record.get("check_in"):
                return "8h 0m remaining"
                
            check_in_dt = att_record["check_in"]
            current_dt = datetime.now()
            
            # Calculate total elapsed time
            elapsed_seconds = (current_dt - check_in_dt).total_seconds()
            
            # Sum up total durations of all break rows, including active ones
            breaks = self.db._execute(
                """
                SELECT break_out, break_in 
                FROM employee_breaks 
                WHERE employee_id = %s AND break_date = %s
                """,
                (emp_id, date.today()),
                fetch="all",
                dictionary=True
            )
            
            total_break_seconds = 0
            for b in (breaks or []):
                end_time = b["break_in"] if b["break_in"] else current_dt
                duration = (end_time - b["break_out"]).total_seconds()
                total_break_seconds += duration

            def parse_time(t_str):
                return datetime.strptime(t_str, "%H:%M:%S").time()

            # Calculate Lunch Penalty (including active lunch)
            lunch_out = att_record.get("lunch_out")
            lunch_in = att_record.get("lunch_in")
            excess_lunch_seconds = 0
            
            if lunch_out:
                l_in = lunch_in if lunch_in else current_dt
                actual_lunch_seconds = (l_in - lunch_out).total_seconds()
                
                lunch_start_str = self.db.get_setting("LUNCH_START", "13:00:00")
                lunch_end_str = self.db.get_setting("LUNCH_END", "13:45:00")
                
                l_start = parse_time(lunch_start_str)
                l_end = parse_time(lunch_end_str)
                
                today = date.today()
                l_start_dt = datetime.combine(today, l_start)
                l_end_dt = datetime.combine(today, l_end)
                if l_end_dt <= l_start_dt:
                    from datetime import timedelta
                    l_end_dt += timedelta(days=1)
                
                allowed_lunch_seconds = (l_end_dt - l_start_dt).total_seconds()
                
                if actual_lunch_seconds > allowed_lunch_seconds:
                    excess_lunch_seconds = actual_lunch_seconds - allowed_lunch_seconds
                
            # Net Working Time
            net_working_seconds = max(0, elapsed_seconds - total_break_seconds - excess_lunch_seconds)
            
            # Fetch dynamic Shift Times
            shift_start_str = self.db.get_setting("SHIFT_START", "10:00:00")
            shift_end_str = self.db.get_setting("SHIFT_END", "15:00:00")
                
            shift_start = parse_time(shift_start_str)
            shift_end = parse_time(shift_end_str)
            
            # If current time is past Shift End, gracefully return
            if current_dt.time() >= shift_end:
                return "Shift Finished"
                
            # Calculate target duration from start to end
            today = date.today()
            start_dt = datetime.combine(today, shift_start)
            end_dt = datetime.combine(today, shift_end)
            
            # Handle overnight shifts (end < start)
            if end_dt <= start_dt:
                from datetime import timedelta
                end_dt += timedelta(days=1)
                
            target_seconds = (end_dt - start_dt).total_seconds()
            
            remaining_seconds = max(0, target_seconds - net_working_seconds)
            
            hours = int(remaining_seconds // 3600)
            minutes = int((remaining_seconds % 3600) // 60)
            
            if hours <= 0 and minutes <= 0:
                return "Shift Finished"
                
            return f"{hours}h {minutes}m remaining"
            
        except Exception as e:
            logger.error(f"Error calculating remaining hours for {emp_id}: {e}")
            return "Error calculating"
