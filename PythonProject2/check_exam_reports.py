"""
check_exam_reports.py

Quick standalone check: prints every row currently in the exam_reports
table, so you can verify saving is actually working without needing
to open MySQL Workbench or type any SQL yourself.
"""

from core.database import Database

db = Database()
rows = db._execute("SELECT * FROM exam_reports ORDER BY id DESC", fetch="all", dictionary=True)

if not rows:
    print("No rows found. Either the table is empty, or save_exam_report was never called successfully.")
else:
    print(f"Found {len(rows)} report(s):\n")
    for r in rows:
        print(r)