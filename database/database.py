"""
database.py  --  College ERP database layer
--------------------------------------------
WHAT IT IS:
  A thin wrapper around the SQLite database.
  All SQL queries live here.

WHY WE NEED IT:
  The MCP server tools call these functions to get real data.
  Keeping SQL here (not in the server) makes it easy to read and test.

HOW IT CONNECTS:
  mcp_server.py  -->  database.py  -->  erp.db  (SQLite file)
"""

import sqlite3
from pathlib import Path

# The SQLite file lives next to this module
DB_PATH = Path(__file__).parent / "erp.db"


def get_connection() -> sqlite3.Connection:
    """Open (or create) the SQLite database file and return a connection."""
    conn = sqlite3.connect(DB_PATH)
    # Row factory lets us access columns by name: row["name"] instead of row[0]
    conn.row_factory = sqlite3.Row
    return conn


# -- Students ------------------------------------------------------------------

def fetch_student(student_id: int) -> dict | None:
    """Return student profile dict with calculated CGPA, or None if the student does not exist."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT s.student_id, s.name, s.department,
                   ROUND(COALESCE(AVG(CASE g.grade
                       WHEN 'A+' THEN 10.0
                       WHEN 'A'  THEN 9.0
                       WHEN 'B+' THEN 8.0
                       WHEN 'B'  THEN 7.0
                       WHEN 'C'  THEN 6.0
                       WHEN 'D'  THEN 5.0
                       ELSE 0.0
                   END), 0.0), 2) AS cgpa
            FROM students s
            LEFT JOIN grades g ON s.student_id = g.student_id
            WHERE s.student_id = ?
            GROUP BY s.student_id, s.name, s.department
            """,
            (student_id,),
        ).fetchone()
    return dict(row) if row else None


# -- Attendance ----------------------------------------------------------------

def fetch_attendance(student_id: int) -> list[dict]:
    """Return a list of attendance records for the given student_id."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                a.subject,
                a.classes_attended,
                a.total_classes,
                ROUND(a.classes_attended * 100.0 / a.total_classes, 1) AS percentage
            FROM attendance a
            WHERE a.student_id = ?
            ORDER BY a.subject
            """,
            (student_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# -- Grades --------------------------------------------------------------------

def fetch_grades(student_id: int) -> list[dict]:
    """Return a list of grade records with grade_points for the given student_id."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT g.subject, g.grade, g.semester,
                   CASE g.grade
                       WHEN 'A+' THEN 10.0
                       WHEN 'A'  THEN 9.0
                       WHEN 'B+' THEN 8.0
                       WHEN 'B'  THEN 7.0
                       WHEN 'C'  THEN 6.0
                       WHEN 'D'  THEN 5.0
                       ELSE 0.0
                   END AS grade_points
            FROM grades g
            WHERE g.student_id = ?
            ORDER BY g.subject
            """,
            (student_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# -- Expanded ERP queries ------------------------------------------------------

def fetch_departments() -> list[dict]:
    """Return departments and their display names."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT department_code, department_name FROM departments ORDER BY department_code"
        ).fetchall()
    return [dict(r) for r in rows]


def fetch_faculty(faculty_id: int | None = None) -> list[dict] | dict | None:
    """Return all faculty, or one faculty member when faculty_id is supplied."""
    with get_connection() as conn:
        if faculty_id is None:
            rows = conn.execute(
                "SELECT f.faculty_id, f.name, f.department_code, d.department_name, f.role "
                "FROM faculty f JOIN departments d USING(department_code) ORDER BY f.faculty_id"
            ).fetchall()
            return [dict(r) for r in rows]
        row = conn.execute(
            "SELECT f.faculty_id, f.name, f.department_code, d.department_name, f.role "
            "FROM faculty f JOIN departments d USING(department_code) WHERE f.faculty_id = ?",
            (faculty_id,),
        ).fetchone()
    return dict(row) if row else None


def fetch_subjects(department_code: str | None = None) -> list[dict]:
    """Return subjects, optionally filtered by department."""
    query = (
        "SELECT s.subject_code, s.subject_name, s.department_code, d.department_name, s.semester "
        "FROM subjects s JOIN departments d USING(department_code)"
    )
    params: tuple = ()
    if department_code:
        query += " WHERE s.department_code = ?"
        params = (department_code.upper(),)
    query += " ORDER BY s.department_code, s.semester, s.subject_code"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def fetch_enrollments(student_id: int) -> list[dict]:
    """Return the subjects in which a student is enrolled."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT e.student_id, e.academic_year, s.subject_code, s.subject_name, "
            "s.department_code, s.semester FROM enrollments e "
            "JOIN subjects s USING(subject_code) WHERE e.student_id = ? "
            "ORDER BY s.semester, s.subject_code",
            (student_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def fetch_timetable(department_code: str | None = None, student_id: int | None = None) -> list[dict]:
    """Return timetable rows; optionally filter by department or a student's enrolled subjects."""
    query = (
        "SELECT t.timetable_id, t.day_of_week, t.start_time, t.end_time, t.room, t.section, "
        "s.subject_code, s.subject_name, s.department_code, f.faculty_id, f.name AS faculty_name "
        "FROM timetable t JOIN subjects s USING(subject_code) "
        "JOIN faculty f USING(faculty_id)"
    )
    clauses: list[str] = []
    params: list = []
    if department_code:
        clauses.append("s.department_code = ?")
        params.append(department_code.upper())
    if student_id is not None:
        clauses.append("s.subject_code IN (SELECT subject_code FROM enrollments WHERE student_id = ?)")
        params.append(student_id)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY CASE t.day_of_week WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 "              "WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 ELSE 6 END, t.start_time"
    with get_connection() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [dict(r) for r in rows]


def fetch_department_attendance(department_code: str) -> list[dict]:
    """Return subject-level attendance aggregates for a department."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT st.department AS department_code, st.student_id, st.name AS student_name, "
            "a.subject, a.classes_attended, a.total_classes, "
            "ROUND(a.classes_attended * 100.0 / NULLIF(a.total_classes, 0), 1) AS percentage "
            "FROM students st JOIN attendance a USING(student_id) "
            "WHERE st.department = ? ORDER BY st.student_id, a.subject",
            (department_code.upper(),),
        ).fetchall()
    return [dict(r) for r in rows]


def fetch_all_students() -> list[dict]:
    """Return the synthetic student directory with CGPA (for admin-only UI endpoints)."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT s.student_id, s.name, s.department,
                   ROUND(COALESCE(AVG(CASE g.grade
                       WHEN 'A+' THEN 10.0
                       WHEN 'A'  THEN 9.0
                       WHEN 'B+' THEN 8.0
                       WHEN 'B'  THEN 7.0
                       WHEN 'C'  THEN 6.0
                       WHEN 'D'  THEN 5.0
                       ELSE 0.0
                   END), 0.0), 2) AS cgpa
            FROM students s
            LEFT JOIN grades g ON s.student_id = g.student_id
            GROUP BY s.student_id, s.name, s.department
            ORDER BY s.student_id
            """
        ).fetchall()
    return [dict(r) for r in rows]


def fetch_top_students_by_cgpa(limit: int = 10, department: str | None = None) -> list[dict]:
    """Return top students ranked by CGPA, optionally filtered by department."""
    with get_connection() as conn:
        query = """
            SELECT s.student_id, s.name, s.department,
                   ROUND(COALESCE(AVG(CASE g.grade
                       WHEN 'A+' THEN 10.0
                       WHEN 'A'  THEN 9.0
                       WHEN 'B+' THEN 8.0
                       WHEN 'B'  THEN 7.0
                       WHEN 'C'  THEN 6.0
                       WHEN 'D'  THEN 5.0
                       ELSE 0.0
                   END), 0.0), 2) AS cgpa
            FROM students s
            LEFT JOIN grades g ON s.student_id = g.student_id
        """
        params = []
        if department:
            query += " WHERE s.department = ?"
            params.append(department.upper())
        query += """
            GROUP BY s.student_id, s.name, s.department
            ORDER BY cgpa DESC, s.student_id ASC
            LIMIT ?
        """
        params.append(limit)
        rows = conn.execute(query, tuple(params)).fetchall()
    return [dict(r) for r in rows]

