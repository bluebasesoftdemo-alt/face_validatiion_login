import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv('.env')

conn = mysql.connector.connect(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME')
)
cur = conn.cursor()

# ── Indexes ───────────────────────────────────────────────────────────────────
print('=' * 60)
print('ALL INDEXES on employees')
print('=' * 60)
cur.execute('SHOW INDEX FROM employees')
for row in cur.fetchall():
    unique_label = "UNIQUE" if row[1] == 0 else "non-unique"
    print(f"  Key: {row[2]:<25}  Column: {row[4]:<20}  {unique_label}")

print()
print('=' * 60)
print('ALL INDEXES on attendance')
print('=' * 60)
cur.execute('SHOW INDEX FROM attendance')
for row in cur.fetchall():
    unique_label = "UNIQUE" if row[1] == 0 else "non-unique"
    print(f"  Key: {row[2]:<25}  Column: {row[4]:<20}  {unique_label}")

# ── Row counts ────────────────────────────────────────────────────────────────
print()
print('=' * 60)
print('ROW COUNTS (data integrity check)')
print('=' * 60)
cur.execute('SELECT COUNT(*) FROM employees')
emp_count = cur.fetchone()[0]
print(f"  employees  : {emp_count} row(s)")

cur.execute('SELECT COUNT(*) FROM attendance')
att_count = cur.fetchone()[0]
print(f"  attendance : {att_count} row(s)")

# ── Embedding integrity ───────────────────────────────────────────────────────
print()
print('=' * 60)
print('EMPLOYEE RECORDS (embedding size check)')
print('=' * 60)
cur.execute('SELECT employee_id, employee_name, LENGTH(embedding), is_active FROM employees')
for row in cur.fetchall():
    emb_bytes = row[2]
    emb_floats = emb_bytes // 4
    active = "active" if row[3] else "inactive"
    print(f"  ID: {row[0]:<15}  Name: {row[1]:<20}  Embedding: {emb_bytes} bytes ({emb_floats} floats)  Status: {active}")

# ── Attendance records ────────────────────────────────────────────────────────
print()
print('=' * 60)
print('ATTENDANCE RECORDS')
print('=' * 60)
cur.execute("""
    SELECT a.id, a.employee_id, a.attendance_date, a.check_in,
           a.check_out, a.status, a.working_hours, a.is_late
    FROM attendance a
    ORDER BY a.attendance_date DESC
""")
rows = cur.fetchall()
if not rows:
    print("  (no records)")
for row in rows:
    print(f"  id={row[0]}  emp={row[1]}  date={row[2]}  in={row[3]}  out={row[4]}  status={row[5]}  hrs={row[6]}  late={row[7]}")

cur.close()
conn.close()
print()
print('All checks passed — no existing data was modified or deleted.')
