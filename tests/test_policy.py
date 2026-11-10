"""
test_policy.py -- Comprehensive unit tests for zero-trust authorization policies
--------------------------------------------------------------------------------
Tests RBAC and least-privilege boundary enforcement across student, teacher, and admin roles.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from auth.policy import allow_request

# Mock callers
STUDENT_RAHUL = {
    "sub": "rahul",
    "role": "student",
    "student_id": 101,
    "name": "Rahul"
}

STUDENT_AMAN = {
    "sub": "aman",
    "role": "student",
    "student_id": 102,
    "name": "Aman"
}

TEACHER = {
    "sub": "teacher",
    "role": "teacher",
    "student_id": None,
    "name": "Prof. Sharma"
}

ADMIN = {
    "sub": "admin",
    "role": "admin",
    "student_id": None,
    "name": "System Admin"
}


# ---------------------------------------------------------------------------
# Tests: Top CGPA / Academic Leaderboard
# ---------------------------------------------------------------------------

def test_student_denied_top_cgpa():
    """Students MUST NOT be allowed to view top students / academic leaderboard."""
    result = allow_request(STUDENT_RAHUL, "get_top_students_by_cgpa", None)
    assert result.allowed is False
    assert "DENIED" in result.reason
    assert "not authorized" in result.reason.lower()


def test_teacher_allowed_top_cgpa():
    """Faculty / teachers MUST be allowed to view top students by CGPA."""
    result = allow_request(TEACHER, "get_top_students_by_cgpa", None)
    assert result.allowed is True
    assert "ALLOWED" in result.reason


def test_admin_allowed_top_cgpa():
    """Administrators MUST be allowed to view top students by CGPA."""
    result = allow_request(ADMIN, "get_top_students_by_cgpa", None)
    assert result.allowed is True
    assert "ALLOWED" in result.reason


# ---------------------------------------------------------------------------
# Tests: Student Self vs. Cross-Student Access
# ---------------------------------------------------------------------------

def test_student_allowed_own_records():
    """Students can access their own profile, grades, and attendance."""
    for tool in ["get_student_profile", "get_grades", "get_attendance", "get_student_timetable"]:
        res = allow_request(STUDENT_RAHUL, tool, requested_student_id=101)
        assert res.allowed is True
        assert "ALLOWED" in res.reason


def test_student_denied_other_student_records():
    """Students MUST NOT access another student's profile, grades, or attendance."""
    for tool in ["get_student_profile", "get_grades", "get_attendance", "get_student_timetable"]:
        res = allow_request(STUDENT_RAHUL, tool, requested_student_id=102)
        assert res.allowed is False
        assert "DENIED" in res.reason


# ---------------------------------------------------------------------------
# Tests: Faculty and Admin Broad Access
# ---------------------------------------------------------------------------

def test_teacher_allowed_any_student_record():
    """Faculty can access any student's records."""
    for tool in ["get_student_profile", "get_grades", "get_attendance", "get_student_timetable"]:
        res = allow_request(TEACHER, tool, requested_student_id=101)
        assert res.allowed is True


def test_admin_allowed_any_student_record():
    """Admins can access any student's records."""
    for tool in ["get_student_profile", "get_grades", "get_attendance", "get_student_timetable"]:
        res = allow_request(ADMIN, tool, requested_student_id=101)
        assert res.allowed is True
