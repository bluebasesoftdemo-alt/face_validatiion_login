"""
services/report_service.py
==========================
Handles generation of reports and statistics for the GUI dashboard.
"""

from typing import Dict, Any, List
from core.database import Database
from core.logger import get_logger

logger = get_logger(__name__)

class ReportService:
    def __init__(self, db: Database):
        self.db = db

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """
        Aggregates today's statistics for the main dashboard.
        Returns total employees, present, absent, and late.
        """
        try:
            return self.db.get_today_stats()
        except Exception as e:
            logger.error(f"Failed to fetch dashboard stats: {e}")
            return {"total": 0, "present": 0, "absent": 0, "late": 0}

    def get_monthly_raw_data(self, year: int = None, month: int = None, department: str = "All") -> List[Dict[str, Any]]:
        """
        Fetches raw attendance data for the data table and Excel export.
        Allows year and month to be None to ignore those filters.
        """
        sql = """
            SELECT a.attendance_date as Date,
                   e.employee_id as `Employee ID`,
                   e.employee_name as Name,
                   a.check_in as `Check-In`,
                   a.check_out as `Check-Out`,
                   a.status as Status,
                   a.is_late
            FROM attendance a
            JOIN employees e ON a.employee_id = e.employee_id
            WHERE 1=1
        """
        params = []
        
        if year is not None:
            sql += " AND YEAR(a.attendance_date) = %s"
            params.append(year)
            
        if month is not None:
            sql += " AND MONTH(a.attendance_date) = %s"
            params.append(month)
        
        if department and department != "All":
            sql += " AND e.department = %s"
            params.append(department)
            
        sql += " ORDER BY a.attendance_date DESC, e.employee_name ASC"
        
        try:
            return self.db._execute(sql, tuple(params), fetch="all", dictionary=True)
        except Exception as e:
            logger.error(f"Failed to generate monthly raw data: {e}")
            return []

    def get_monthly_analytics(self, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculates analytics cards from the raw data.
        Returns formatted strings for the UI cards.
        """
        if not raw_data:
            return {
                "total_days": "0 Days",
                "ontime_rate": "0.0%", 
                "total_late": "0 Incidents"
            }
            
        total_records = len(raw_data)
        total_late = sum(1 for row in raw_data if row.get("is_late"))
        
        # Format strings safely
        days_str = "1 Day" if total_records == 1 else f"{total_records} Days"
        incidents_str = "1 Incident" if total_late == 1 else f"{total_late} Incidents"
        
        ontime_rate = 100.0 - ((total_late / total_records) * 100.0) if total_records > 0 else 0.0
        
        return {
            "total_days": days_str,
            "ontime_rate": f"{ontime_rate:.1f}%",
            "total_late": incidents_str
        }
