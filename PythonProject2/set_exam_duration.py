"""
set_exam_duration.py

Run this any time your team decides the exam duration -- no code
changes needed anywhere else after this.
"""

from core.database import Database

db = Database()
db._execute(
    """
    INSERT INTO system_settings (setting_key, setting_value)
    VALUES ('EXAM_DURATION_MINUTES', %s)
    ON DUPLICATE KEY UPDATE setting_value = %s
    """,
    ("2", "2"),  # <-- set to 2 for now so you can actually test it ending; change to real duration later
)
print("Exam duration set.")