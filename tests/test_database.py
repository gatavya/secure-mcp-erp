"""
test_database.py  --  Unit tests for the database layer
---------------------------------------------------------
Run with:  python -m pytest tests/ -v
"""

import sys
import os
import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.database import fetch_student, fetch_attendance, fetch_grades


# ===========================================================================
# Student tests
# ===========================================================================

def test_student_101_exists():
    """Student Rahul with ID 101 must be in the database."""
    student = fetch_student(101)
    assert student is not None, "Student 101 should exist"
    assert student["name"] == "Rahul"
    assert student["department"] == "CSE"
    assert student["student_id"] == 101


def test_student_102_exists():
    """Student Aman with ID 102 must be in the database."""
    student = fetch_student(102)
    assert student is not None, "Student 102 should exist"
    assert student["name"] == "Aman"
    assert student["department"] == "CSE"


def test_student_103_exists():
    """Student Priya with ID 103 must be in the database."""
    student = fetch_student(103)
    assert student is not None, "Student 103 should exist"
    assert student["name"] == "Priya"
    assert student["department"] == "ECE"


def test_student_not_found():
    """A non-existent student ID should return None."""
    result = fetch_student(999)
    assert result is None


# ===========================================================================
# Attendance tests
# ===========================================================================

def test_attendance_student_101():
    """Student 101 should have attendance records for DBMS, OS, and Computer Networks."""
    records = fetch_attendance(101)
    assert len(records) >= 3, "Student 101 should have at least the original attendance records"

    subjects = {r["subject"] for r in records}
    assert "DBMS" in subjects
    assert "OS" in subjects
    assert "Computer Networks" in subjects


def test_attendance_student_101_dbms_value():
    """Rahul's DBMS attendance should be exactly 87/100 = 87.0%."""
    records = fetch_attendance(101)
    dbms = next(r for r in records if r["subject"] == "DBMS")
    assert dbms["classes_attended"] == 87
    assert dbms["total_classes"] == 100
    assert dbms["percentage"] == 87.0


def test_attendance_student_102():
    """Student 102 should have attendance records."""
    records = fetch_attendance(102)
    assert len(records) >= 3
    dbms = next(r for r in records if r["subject"] == "DBMS")
    assert dbms["classes_attended"] == 76


def test_attendance_empty_for_unknown_student():
    """A student that doesn't exist should return an empty attendance list."""
    records = fetch_attendance(999)
    assert records == []


# ===========================================================================
# Grades tests
# ===========================================================================

def test_grades_student_101():
    """Student 101 (Rahul) should have grades for DBMS, OS, Computer Networks."""
    grades = fetch_grades(101)
    assert len(grades) >= 3

    subjects = {g["subject"] for g in grades}
    assert "DBMS" in subjects
    assert "OS" in subjects
    assert "Computer Networks" in subjects


def test_grades_student_101_values():
    """Rahul's grades: DBMS=A, OS=A+, Computer Networks=B+"""
    grades = fetch_grades(101)
    grade_map = {g["subject"]: g["grade"] for g in grades}
    assert grade_map["DBMS"] == "A"
    assert grade_map["OS"] == "A+"
    assert grade_map["Computer Networks"] == "B+"


def test_grades_student_102():
    """Student 102 (Aman) should have grades."""
    grades = fetch_grades(102)
    assert len(grades) >= 3
    grade_map = {g["subject"]: g["grade"] for g in grades}
    assert grade_map["DBMS"] == "B"
    assert grade_map["OS"] == "A"


def test_grades_empty_for_unknown_student():
    """A non-existent student should return an empty grades list."""
    grades = fetch_grades(999)
    assert grades == []

# ==========================================================================
# Expanded ERP relational schema
# ==========================================================================

def test_expanded_erp_tables_have_seed_data():
    from database.database import fetch_departments, fetch_faculty, fetch_subjects
    assert len(fetch_departments()) >= 5
    assert len(fetch_faculty()) >= 5
    assert len(fetch_subjects()) >= 10


def test_new_synthetic_student_has_enrollment_and_timetable():
    from database.database import fetch_student, fetch_enrollments, fetch_timetable
    student = fetch_student(104)
    assert student is not None and student["department"] == "CSE"
    assert len(fetch_enrollments(104)) >= 3
    assert len(fetch_timetable(student_id=104)) >= 1


def test_department_subject_filter():
    from database.database import fetch_subjects
    cse_subjects = fetch_subjects("CSE")
    assert cse_subjects
    assert all(subject["department_code"] == "CSE" for subject in cse_subjects)
