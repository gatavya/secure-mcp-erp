"""Initialize the synthetic College ERP database without deleting existing data.

Run from the project root: python database/seed.py
For an existing database this is an additive, idempotent upgrade.
"""
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = Path(__file__).parent / "erp.db"

BASE_SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    student_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(student_id),
    subject TEXT NOT NULL,
    classes_attended INTEGER NOT NULL CHECK(classes_attended >= 0),
    total_classes INTEGER NOT NULL CHECK(total_classes > 0)
);
CREATE TABLE IF NOT EXISTS grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(student_id),
    subject TEXT NOT NULL,
    grade TEXT NOT NULL,
    semester TEXT NOT NULL
);
"""

BASE_STUDENTS = [(101, "Rahul", "CSE"), (102, "Aman", "CSE"), (103, "Priya", "ECE")]
BASE_ATTENDANCE = [
    (101, "DBMS", 87, 100), (101, "OS", 92, 100), (101, "Computer Networks", 78, 90),
    (102, "DBMS", 76, 100), (102, "OS", 81, 100), (102, "Computer Networks", 65, 90),
    (103, "Signals & Systems", 90, 100), (103, "Digital Electronics", 85, 95),
    (103, "Communication Theory", 70, 90),
]
BASE_GRADES = [
    (101, "DBMS", "A", "Sem 4"), (101, "OS", "A+", "Sem 4"), (101, "Computer Networks", "B+", "Sem 4"),
    (102, "DBMS", "B", "Sem 4"), (102, "OS", "A", "Sem 4"), (102, "Computer Networks", "B", "Sem 4"),
    (103, "Signals & Systems", "A+", "Sem 4"), (103, "Digital Electronics", "A", "Sem 4"),
    (103, "Communication Theory", "B+", "Sem 4"),
]


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(BASE_SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0:
            conn.executemany("INSERT INTO students VALUES (?, ?, ?)", BASE_STUDENTS)
            conn.executemany(
                "INSERT INTO attendance(student_id, subject, classes_attended, total_classes) VALUES (?, ?, ?, ?)",
                BASE_ATTENDANCE,
            )
            conn.executemany(
                "INSERT INTO grades(student_id, subject, grade, semester) VALUES (?, ?, ?, ?)",
                BASE_GRADES,
            )
    # Import after the base tables exist; this performs safe additive migration and seeding.
    from database.upgrade import upgrade
    upgrade()


if __name__ == "__main__":
    main()
