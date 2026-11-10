"""
test_tools.py  --  Tests for MCP tool functions + baseline security gap demo
-----------------------------------------------------------------------------
Run with:  python -m pytest tests/ -v

These tests call the tool functions directly (not over MCP transport),
so they are fast and do not require the server to be running.
"""

import sys
import os
import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import the tool functions directly from the server module
from server.mcp_server import get_student_profile, get_attendance, get_grades


# ===========================================================================
# Tool: get_student_profile
# ===========================================================================

def test_tool_get_student_profile_101():
    """get_student_profile(101) should return Rahul's profile."""
    result = get_student_profile(101)
    assert "error" not in result
    assert result["name"] == "Rahul"
    assert result["department"] == "CSE"
    assert result["student_id"] == 101


def test_tool_get_student_profile_not_found():
    """get_student_profile with an invalid ID should return an error dict."""
    result = get_student_profile(999)
    assert "error" in result
    assert "999" in result["error"]


def test_tool_get_student_profile_invalid_id():
    """get_student_profile(-1) should return an input validation error."""
    result = get_student_profile(-1)
    assert "error" in result


# ===========================================================================
# Tool: get_attendance
# ===========================================================================

def test_tool_get_attendance_101():
    """get_attendance(101) should return Rahul's attendance records."""
    result = get_attendance(101)
    assert "error" not in result
    assert result["student_id"] == 101
    assert result["student_name"] == "Rahul"
    assert len(result["attendance"]) >= 3

    subjects = {r["subject"] for r in result["attendance"]}
    assert "DBMS" in subjects
    assert "OS" in subjects


def test_tool_get_attendance_102():
    """get_attendance(102) should return Aman's attendance records."""
    result = get_attendance(102)
    assert "error" not in result
    assert result["student_name"] == "Aman"


def test_tool_get_attendance_not_found():
    """get_attendance for unknown student should return an error dict."""
    result = get_attendance(999)
    assert "error" in result


# ===========================================================================
# Tool: get_grades
# ===========================================================================

def test_tool_get_grades_101():
    """get_grades(101) should return Rahul's grades."""
    result = get_grades(101)
    assert "error" not in result
    assert result["student_id"] == 101
    assert result["student_name"] == "Rahul"
    assert len(result["grades"]) >= 3

    grade_map = {g["subject"]: g["grade"] for g in result["grades"]}
    assert grade_map["DBMS"] == "A"
    assert grade_map["OS"] == "A+"


def test_tool_get_grades_not_found():
    """get_grades for unknown student should return an error dict."""
    result = get_grades(999)
    assert "error" in result


# ===========================================================================
# MCP Server: Import and initialization
# ===========================================================================

def test_mcp_server_importable():
    """The MCP server module must import without errors."""
    from server import mcp_server
    assert mcp_server.server is not None


def test_mcp_server_name():
    """The server should be named 'college-erp-mcp'."""
    from server.mcp_server import server
    assert server.name == "college-erp-mcp"


# ===========================================================================
# BASELINE SECURITY GAP DEMONSTRATION
# ===========================================================================
#
# This test documents the E2 security gap.
#
# Scenario:
#   Authenticated identity: student_101 (Rahul)
#   Request:                student_102's grades
#
# Expected (E2 baseline):
#   The tool RETURNS student_102's data without any authorization check.
#
# This is INTENTIONAL in the E2 baseline.
# It demonstrates that the server does not yet enforce identity-aware
# authorization. A proper policy layer is planned for the next phase.
#
# Do NOT rename this test to include the word "secure" --
# the baseline is deliberately insecure.
# ===========================================================================

def test_baseline_cross_student_access_gap():
    """
    SECURITY GAP DEMONSTRATION (E2 Baseline)
    -----------------------------------------
    Simulated identity:  student_101 (Rahul)
    Requested resource:  student_102 (Aman)'s grades

    The baseline MCP server does NOT enforce identity-aware authorization.
    Any caller that knows a student_id can retrieve that student's grades.

    This test PASSES, which means the data IS returned -- demonstrating the gap.
    The assertion verifies that the gap exists (data is returned without error).

    What this means:
      In a real system, student_101 should ONLY be able to see their own data.
      The next development phase will add an authorization policy layer that
      independently validates: who is asking + what they are asking for + for whom.
    """
    # Simulated context: the currently authenticated user is student_101
    simulated_authenticated_user = 101  # Rahul

    # The request -- intentionally asking for a DIFFERENT student's data
    requested_student_id = 102  # Aman

    # E2 BASELINE: The server does not check whether simulated_authenticated_user
    # is allowed to access requested_student_id's data.
    result = get_grades(requested_student_id)

    # The data IS returned (no authorization error)
    # This assertion PASSES -- which is the demonstration of the security gap.
    assert "error" not in result, (
        "The baseline server returned an error, but we expected it to return data "
        "(demonstrating the security gap)."
    )
    assert result["student_id"] == 102
    assert result["student_name"] == "Aman"
    assert len(result["grades"]) > 0

    # Print a clear message for demo purposes
    print()
    print("=" * 60)
    print("  SECURITY GAP DEMONSTRATION")
    print("=" * 60)
    print(f"  Authenticated user (simulated): student_{simulated_authenticated_user}")
    print(f"  Requested resource:             student_{requested_student_id}")
    print(f"  Data returned:                  YES (grades for {result['student_name']})")
    print()
    print("  CONCLUSION: The E2 baseline does NOT enforce cross-student")
    print("  authorization. Student 101 can read student 102's grades.")
    print()
    print("  This is the gap the next phase will address.")
    print("=" * 60)
