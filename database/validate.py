"""Run integrity and dataset-size checks for the synthetic College ERP.

Usage from project root: python database/validate.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "erp.db"
EXPECTED_MINIMUMS = {
    "departments": 5,
    "students": 500,
    "faculty": 50,
    "subjects": 25,
    "enrollments": 2500,
    "attendance": 2500,
    "grades": 2500,
    "timetable": 50,
}


def main() -> int:
    if not DB_PATH.exists():
        print(f"FAIL: database not found: {DB_PATH}")
        return 1
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        print(f"SQLite integrity_check: {integrity}")
        print(f"Foreign-key violations: {len(fk_errors)}")
        failed = integrity != "ok" or bool(fk_errors)
        for table, minimum in EXPECTED_MINIMUMS.items():
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            ok = count >= minimum
            print(f"{'PASS' if ok else 'FAIL'} {table:18} {count:>7} rows (minimum {minimum})")
            failed |= not ok
        # Every student should have academic data in the prototype.
        students_without_attendance = conn.execute(
            "SELECT COUNT(*) FROM students s WHERE NOT EXISTS "
            "(SELECT 1 FROM attendance a WHERE a.student_id = s.student_id)"
        ).fetchone()[0]
        students_without_grades = conn.execute(
            "SELECT COUNT(*) FROM students s WHERE NOT EXISTS "
            "(SELECT 1 FROM grades g WHERE g.student_id = s.student_id)"
        ).fetchone()[0]
        print(f"Students without attendance: {students_without_attendance}")
        print(f"Students without grades: {students_without_grades}")
        failed |= students_without_attendance > 0 or students_without_grades > 0
        print("\nRESULT:", "FAIL" if failed else "PASS — database checks completed")
        return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
