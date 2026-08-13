from database import Database
import time

class AttendanceService:

    def __init__(self):
        self.db = Database()
        self.last_mark = {}
        self.cooldown = 5

    def mark(self, emp_id):

        now = time.time()
        last = self.last_mark.get(emp_id, 0)

        if now - last > self.cooldown:
            self.db.mark_check_in(emp_id)
            self.last_mark[emp_id] = now
            print(f"🟢 Marked present: {emp_id}")

    def close(self):
        self.db.close()