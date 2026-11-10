"""Idempotently expand the demo database into a production-oriented synthetic ERP.

This is a local research prototype, not a production deployment. It preserves
existing student/attendance/grade/audit records and adds deterministic synthetic
records until the database reaches the target size.

Run from project root: python database/seed.py
"""
from __future__ import annotations
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "erp.db"
TARGET_STUDENTS = 500
TARGET_FACULTY = 50

DEPARTMENTS = [
    ("CSE", "Computer Science and Engineering"),
    ("ECE", "Electronics and Communication Engineering"),
    ("EE", "Electrical Engineering"),
    ("ME", "Mechanical Engineering"),
    ("DS", "Data Science"),
]

SUBJECTS = [
    ("CS301", "DBMS", "CSE", 4),
    ("CS302", "Operating Systems", "CSE", 4),
    ("CS303", "Computer Networks", "CSE", 4),
    ("CS304", "Data Structures", "CSE", 3),
    ("CS305", "Software Engineering", "CSE", 5),
    ("EC301", "Signals & Systems", "ECE", 4),
    ("EC302", "Digital Electronics", "ECE", 4),
    ("EC303", "Communication Theory", "ECE", 4),
    ("EC304", "Microprocessors", "ECE", 3),
    ("EC305", "Digital Signal Processing", "ECE", 5),
    ("EE301", "Circuit Analysis", "EE", 4),
    ("EE302", "Power Systems", "EE", 4),
    ("EE303", "Electrical Machines", "EE", 3),
    ("EE304", "Control Systems", "EE", 5),
    ("EE305", "Power Electronics", "EE", 6),
    ("ME301", "Thermodynamics", "ME", 4),
    ("ME302", "Fluid Mechanics", "ME", 4),
    ("ME303", "Manufacturing Processes", "ME", 3),
    ("ME304", "Machine Design", "ME", 5),
    ("ME305", "Heat Transfer", "ME", 6),
    ("DS301", "Probability and Statistics", "DS", 4),
    ("DS302", "Machine Learning", "DS", 4),
    ("DS303", "Data Visualization", "DS", 3),
    ("DS304", "Database Analytics", "DS", 5),
    ("DS305", "Big Data Systems", "DS", 6),
]

BASE_FACULTY = [
    (201, "Prof. Sharma", "CSE", "teacher"),
    (202, "Prof. Verma", "ECE", "teacher"),
    (203, "Prof. Iyer", "EE", "teacher"),
    (204, "Prof. Khan", "ME", "teacher"),
    (205, "Dr. Mehta", "DS", "teacher"),
    (206, "Prof. Rao", "CSE", "teacher"),
]

FIRST_NAMES = [
    "Aarav", "Aditi", "Ananya", "Arjun", "Diya", "Ishaan", "Ishita", "Kabir",
    "Kavya", "Karan", "Meera", "Neha", "Nikhil", "Priya", "Rahul", "Riya",
    "Rohan", "Sana", "Sarthak", "Tanvi", "Vikram", "Yash", "Zoya", "Advik",
    "Avni", "Dev", "Ira", "Manav", "Naina", "Reyansh",
]
LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Iyer", "Khan", "Rao", "Gupta", "Mehta",
    "Joshi", "Nair", "Das", "Singh", "Kapoor", "Mishra", "Bose", "Kulkarni",
    "Malhotra", "Chopra", "Reddy", "Saxena",
]

LEGACY_LABELS = {"CS302": "OS"}
DEPT_SUBJECTS = {
    dept: [(code, LEGACY_LABELS.get(code, name)) for code, name, subject_dept, _ in SUBJECTS if subject_dept == dept]
    for dept, _ in DEPARTMENTS
}


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def synthetic_students(existing_count: int) -> list[tuple[int, str, str]]:
    """Return deterministic new student rows until TARGET_STUDENTS is reached."""
    to_add = max(0, TARGET_STUDENTS - existing_count)
    rows = []
    for i in range(to_add):
        dept = DEPARTMENTS[(i + existing_count) % len(DEPARTMENTS)][0]
        first = FIRST_NAMES[i % len(FIRST_NAMES)]
        last = LAST_NAMES[(i // len(FIRST_NAMES)) % len(LAST_NAMES)]
        # Add a stable suffix to keep names unique and avoid implying real identities.
        name = f"{first} {last} {i + 1:03d}"
        rows.append((1000 + i, name, dept))
    return rows


def synthetic_faculty(existing_count: int) -> list[tuple[int, str, str, str]]:
    to_add = max(0, TARGET_FACULTY - existing_count)
    rows = []
    for i in range(to_add):
        dept = DEPARTMENTS[i % len(DEPARTMENTS)][0]
        rows.append((207 + i, f"Faculty Member {i + 1:03d}", dept, "teacher"))
    return rows


def upgrade() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS departments (
            department_code TEXT PRIMARY KEY,
            department_name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS faculty (
            faculty_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            department_code TEXT NOT NULL REFERENCES departments(department_code),
            role TEXT NOT NULL DEFAULT 'teacher' CHECK(role IN ('teacher','admin'))
        );
        CREATE TABLE IF NOT EXISTS subjects (
            subject_code TEXT PRIMARY KEY,
            subject_name TEXT NOT NULL,
            department_code TEXT NOT NULL REFERENCES departments(department_code),
            semester INTEGER NOT NULL CHECK(semester BETWEEN 1 AND 8),
            UNIQUE(subject_name, department_code)
        );
        CREATE TABLE IF NOT EXISTS enrollments (
            enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES students(student_id),
            subject_code TEXT NOT NULL REFERENCES subjects(subject_code),
            academic_year TEXT NOT NULL DEFAULT '2026-27',
            UNIQUE(student_id, subject_code, academic_year)
        );
        CREATE TABLE IF NOT EXISTS faculty_subject_assignments (
            faculty_id INTEGER NOT NULL REFERENCES faculty(faculty_id),
            subject_code TEXT NOT NULL REFERENCES subjects(subject_code),
            PRIMARY KEY(faculty_id, subject_code)
        );
        CREATE TABLE IF NOT EXISTS timetable (
            timetable_id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_code TEXT NOT NULL REFERENCES subjects(subject_code),
            faculty_id INTEGER NOT NULL REFERENCES faculty(faculty_id),
            day_of_week TEXT NOT NULL CHECK(day_of_week IN ('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday')),
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            room TEXT NOT NULL,
            section TEXT NOT NULL DEFAULT 'A'
        );
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_students_department ON students(department);
        CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_id);
        CREATE INDEX IF NOT EXISTS idx_grades_student ON grades(student_id);
        CREATE INDEX IF NOT EXISTS idx_enrollments_student ON enrollments(student_id);
        CREATE INDEX IF NOT EXISTS idx_enrollments_subject ON enrollments(subject_code);
        CREATE INDEX IF NOT EXISTS idx_subject_department ON subjects(department_code);
        CREATE INDEX IF NOT EXISTS idx_faculty_department ON faculty(department_code);
        CREATE INDEX IF NOT EXISTS idx_timetable_subject ON timetable(subject_code);
        CREATE TRIGGER IF NOT EXISTS trg_students_department_insert
        BEFORE INSERT ON students
        WHEN NOT EXISTS (SELECT 1 FROM departments WHERE department_code = NEW.department)
        BEGIN
            SELECT RAISE(ABORT, 'Unknown department_code for student');
        END;
        CREATE TRIGGER IF NOT EXISTS trg_students_department_update
        BEFORE UPDATE OF department ON students
        WHEN NOT EXISTS (SELECT 1 FROM departments WHERE department_code = NEW.department)
        BEGIN
            SELECT RAISE(ABORT, 'Unknown department_code for student');
        END;
        """)

        # Keep the original E2/E3 schema compatible while adding normalized references.
        if "subject_code" not in table_columns(conn, "attendance"):
            conn.execute("ALTER TABLE attendance ADD COLUMN subject_code TEXT REFERENCES subjects(subject_code)")
        if "subject_code" not in table_columns(conn, "grades"):
            conn.execute("ALTER TABLE grades ADD COLUMN subject_code TEXT REFERENCES subjects(subject_code)")

        conn.executemany("INSERT OR IGNORE INTO departments VALUES (?, ?)", DEPARTMENTS)
        conn.executemany(
            "INSERT OR IGNORE INTO subjects(subject_code, subject_name, department_code, semester) VALUES (?, ?, ?, ?)",
            SUBJECTS,
        )
        conn.executemany(
            "INSERT OR IGNORE INTO faculty(faculty_id, name, department_code, role) VALUES (?, ?, ?, ?)",
            BASE_FACULTY,
        )

        # Expand to 500 total students, preserving all existing student IDs and records.
        student_count = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        conn.executemany(
            "INSERT OR IGNORE INTO students(student_id, name, department) VALUES (?, ?, ?)",
            synthetic_students(student_count),
        )

        # Expand to 50 faculty members while retaining original faculty rows.
        faculty_count = conn.execute("SELECT COUNT(*) FROM faculty").fetchone()[0]
        conn.executemany(
            "INSERT OR IGNORE INTO faculty(faculty_id, name, department_code, role) VALUES (?, ?, ?, ?)",
            synthetic_faculty(faculty_count),
        )

        # Link the legacy subject labels to normalized subject codes.
        aliases = {
            "DBMS": "CS301", "OS": "CS302", "Computer Networks": "CS303",
            "Data Structures": "CS304", "Software Engineering": "CS305",
            "Signals & Systems": "EC301", "Digital Electronics": "EC302",
            "Communication Theory": "EC303", "Microprocessors": "EC304",
            "Digital Signal Processing": "EC305", "Circuit Analysis": "EE301",
            "Power Systems": "EE302", "Electrical Machines": "EE303",
            "Control Systems": "EE304", "Power Electronics": "EE305",
            "Thermodynamics": "ME301", "Fluid Mechanics": "ME302",
            "Manufacturing Processes": "ME303", "Machine Design": "ME304",
            "Heat Transfer": "ME305", "Probability and Statistics": "DS301",
            "Machine Learning": "DS302", "Data Visualization": "DS303",
            "Database Analytics": "DS304", "Big Data Systems": "DS305",
        }
        for table in ("attendance", "grades"):
            rows = conn.execute(f"SELECT id, subject FROM {table} WHERE subject_code IS NULL").fetchall()
            for row in rows:
                code = aliases.get(row["subject"])
                if code:
                    conn.execute(f"UPDATE {table} SET subject_code = ? WHERE id = ?", (code, row["id"]))

        # Ensure every student is enrolled in their department's subjects. All records are synthetic.
        students = conn.execute("SELECT student_id, department FROM students ORDER BY student_id").fetchall()
        faculty_by_dept: dict[str, list[int]] = {}
        for row in conn.execute("SELECT faculty_id, department_code FROM faculty ORDER BY faculty_id"):
            faculty_by_dept.setdefault(row["department_code"], []).append(row["faculty_id"])

        grades = ["A+", "A", "B+", "B", "C", "A", "B+"]
        for student in students:
            sid, dept = student["student_id"], student["department"]
            subjects = DEPT_SUBJECTS.get(dept, DEPT_SUBJECTS["CSE"])
            for idx, (code, label) in enumerate(subjects):
                attended = 55 + ((sid * 7 + idx * 11) % 46)  # 55-100 inclusive
                total = 100
                grade = grades[(sid + idx) % len(grades)]
                conn.execute(
                    "INSERT OR IGNORE INTO enrollments(student_id, subject_code, academic_year) VALUES (?, ?, '2026-27')",
                    (sid, code),
                )
                conn.execute(
                    "INSERT INTO attendance(student_id, subject, classes_attended, total_classes, subject_code) "
                    "SELECT ?, ?, ?, ?, ? WHERE NOT EXISTS "
                    "(SELECT 1 FROM attendance WHERE student_id = ? AND subject = ?)",
                    (sid, label, attended, total, code, sid, label),
                )
                conn.execute(
                    "INSERT INTO grades(student_id, subject, grade, semester, subject_code) "
                    "SELECT ?, ?, ?, ?, ? WHERE NOT EXISTS "
                    "(SELECT 1 FROM grades WHERE student_id = ? AND subject = ? AND semester = 'Sem 4')",
                    (sid, label, grade, "Sem 4", code, sid, label),
                )

        # Assign every subject to a faculty member from the same department.
        for code, _, dept, _ in SUBJECTS:
            candidates = faculty_by_dept.get(dept, [])
            if candidates:
                faculty_id = candidates[sum(ord(ch) for ch in code) % len(candidates)]
                conn.execute(
                    "INSERT OR IGNORE INTO faculty_subject_assignments(faculty_id, subject_code) VALUES (?, ?)",
                    (faculty_id, code),
                )

        # Create two sections per subject, with deterministic schedules and no duplicate reruns.
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        slots = [("09:00", "10:00", "Room 101"), ("10:15", "11:15", "Room 202"),
                 ("11:30", "12:30", "Lab 1"), ("13:00", "14:00", "Room 303"),
                 ("14:15", "15:15", "Lab 2")]
        for i, (code, _, dept, _) in enumerate(SUBJECTS):
            candidates = faculty_by_dept.get(dept, [201])
            for section_idx, section in enumerate(("A", "B")):
                day = days[(i + section_idx) % len(days)]
                start, end, room = slots[(i + section_idx) % len(slots)]
                conn.execute(
                    "INSERT INTO timetable(subject_code, faculty_id, day_of_week, start_time, end_time, room, section) "
                    "SELECT ?, ?, ?, ?, ?, ?, ? WHERE NOT EXISTS "
                    "(SELECT 1 FROM timetable WHERE subject_code = ? AND section = ?)",
                    (code, candidates[(i + section_idx) % len(candidates)], day, start, end, room, section, code, section),
                )

        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, description) VALUES (2, 'Expanded synthetic ERP dataset and relational indexes')"
        )
        conn.commit()

    print(f"Upgraded database: {DB_PATH}")
    with sqlite3.connect(DB_PATH) as conn:
        for table in ("departments", "students", "faculty", "subjects", "enrollments", "attendance", "grades", "timetable", "audit_log"):
            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                print(f"  {table:28} {count:>7}")


if __name__ == "__main__":
    upgrade()
