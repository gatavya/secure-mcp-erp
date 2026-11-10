"""
mcp_server_e4.py  --  College ERP MCP Server (E4 Final)
----------------------------------------------------------
WHAT IS DIFFERENT FROM E3:
  - Supports Teacher role
  - Identical security architecture

HOW TO RUN (standalone, for testing):
  python server/mcp_server_e4.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp.server.mcpserver import MCPServer
from database.database import fetch_student, fetch_attendance, fetch_grades, fetch_timetable, fetch_top_students_by_cgpa
from auth.jwt_utils import verify_token
from auth.policy import allow_request
from auth.audit import log_access, ensure_audit_table

import jwt as pyjwt

# ---------------------------------------------------------------------------
# Server Definition
# ---------------------------------------------------------------------------

server = MCPServer(
    name="college-erp-mcp-e4",
    description=(
        "SECURED MCP Server for Controlled Access to College ERP (E4). "
        "All tools require a valid JWT caller_token. "
        "Authorization policy enforces role-based access. "
        "All access attempts are audit-logged."
    ),
)

# Ensure audit table exists at startup
ensure_audit_table()


# ---------------------------------------------------------------------------
# Shared: decode + authorize helper
# ---------------------------------------------------------------------------

def _authorize(caller_token: str, tool_name: str, student_id: int | None = None) -> tuple[bool, dict | None, str]:
    """
    Verify JWT and run authorization policy.

    Returns:
        (allowed: bool, caller: dict | None, reason: str)
    """
    # 1. Verify token
    try:
        caller = verify_token(caller_token)
    except pyjwt.ExpiredSignatureError:
        return False, None, "DENIED: JWT token has expired. Please log in again."
    except pyjwt.InvalidTokenError as e:
        return False, None, f"DENIED: Invalid JWT token -- {e}"

    # 2. Run policy
    result = allow_request(caller, tool_name, student_id)

    # 3. Audit log
    log_access(
        caller=caller,
        tool_name=tool_name,
        requested_student_id=student_id,
        allowed=result.allowed,
        reason=result.reason,
    )

    return result.allowed, caller, result.reason


# ---------------------------------------------------------------------------
# Tool 1: get_student_profile (secured)
# ---------------------------------------------------------------------------

@server.tool(
    name="get_student_profile",
    description=(
        "Retrieve the profile of a student by their student ID. "
        "Requires a valid JWT caller_token. "
        "Students may only access their own profile. Admins can access any."
    ),
)
def get_student_profile(student_id: int, caller_token: str) -> dict:
    """
    Args:
        student_id: The numeric student ID (e.g. 101, 102, 103)
        caller_token: JWT token issued at login

    Returns:
        Student profile dict, or error dict if denied / not found.

    E3 NOTE: Access is authorized before any DB query.
    """
    allowed, caller, reason = _authorize(caller_token, "get_student_profile", student_id)
    if not allowed:
        return {"error": reason, "authorized": False}

    profile = fetch_student(student_id)
    if profile is None:
        return {"error": f"Student with ID {student_id} not found.", "authorized": True}
    return {**profile, "authorized": True}


# ---------------------------------------------------------------------------
# Tool 2: get_attendance (secured)
# ---------------------------------------------------------------------------

@server.tool(
    name="get_attendance",
    description=(
        "Retrieve attendance records for a student by their student ID. "
        "Requires a valid JWT caller_token. "
        "Students may only access their own attendance. Admins can access any."
    ),
)
def get_attendance(student_id: int, caller_token: str) -> dict:
    """
    Args:
        student_id: The numeric student ID
        caller_token: JWT token issued at login

    Returns:
        Attendance dict, or error dict if denied / not found.
    """
    allowed, caller, reason = _authorize(caller_token, "get_attendance", student_id)
    if not allowed:
        return {"error": reason, "authorized": False}

    profile = fetch_student(student_id)
    if profile is None:
        return {"error": f"Student with ID {student_id} not found.", "authorized": True}

    records = fetch_attendance(student_id)
    return {
        "student_id":   student_id,
        "student_name": profile["name"],
        "attendance":   records,
        "authorized":   True,
    }


# ---------------------------------------------------------------------------
# Tool 3: get_grades (secured)
# ---------------------------------------------------------------------------

@server.tool(
    name="get_grades",
    description=(
        "Retrieve grades for a student by their student ID. "
        "Requires a valid JWT caller_token. "
        "Students may only access their own grades. Admins can access any."
    ),
)
def get_grades(student_id: int, caller_token: str) -> dict:
    """
    Args:
        student_id: The numeric student ID
        caller_token: JWT token issued at login

    Returns:
        Grades dict, or error dict if denied / not found.
    """
    allowed, caller, reason = _authorize(caller_token, "get_grades", student_id)
    if not allowed:
        return {"error": reason, "authorized": False}

    profile = fetch_student(student_id)
    if profile is None:
        return {"error": f"Student with ID {student_id} not found.", "authorized": True}

    records = fetch_grades(student_id)
    return {
        "student_id":   student_id,
        "student_name": profile["name"],
        "grades":       records,
        "authorized":   True,
    }


@server.tool(
    name="get_student_timetable",
    description=(
        "Retrieve the weekly timetable for a student by student ID. "
        "Requires a valid JWT caller_token. Students may only access their own timetable; "
        "teacher/admin permissions are evaluated by the authorization policy."
    ),
)
def get_student_timetable(student_id: int, caller_token: str) -> dict:
    """Return timetable only after identity and access policy checks."""
    allowed, caller, reason = _authorize(caller_token, "get_student_timetable", student_id)
    if not allowed:
        return {"error": reason, "authorized": False}
    profile = fetch_student(student_id)
    if profile is None:
        return {"error": f"Student with ID {student_id} not found.", "authorized": True}
    return {
        "student_id": student_id,
        "student_name": profile["name"],
        "timetable": fetch_timetable(student_id=student_id),
        "authorized": True,
    }


# ---------------------------------------------------------------------------
# Tool 5: get_top_students_by_cgpa (secured)
# ---------------------------------------------------------------------------

@server.tool(
    name="get_top_students_by_cgpa",
    description=(
        "Retrieve the top students ranked by Cumulative Grade Point Average (CGPA). "
        "Use this when the user asks for top students, rankers, highest CGPA, academic leaderboard, or honor roll. "
        "Returns a list of students with student_id, name, department, and cgpa. "
        "Requires a valid JWT caller_token. "
        "Parameters: limit (integer, number of students to return, default 10), "
        "department (optional string filter like 'CSE', 'ECE', 'EE', 'ME', 'DS')."
    ),
)
def get_top_students_by_cgpa(
    caller_token: str,
    limit: int = 10,
    department: str | None = None,
) -> dict:
    """Return top students ranked by CGPA after policy evaluation."""
    allowed, caller, reason = _authorize(caller_token, "get_top_students_by_cgpa", None)
    if not allowed:
        return {"error": reason, "authorized": False}

    top_students = fetch_top_students_by_cgpa(limit=limit, department=department)
    return {
        "top_students": top_students,
        "count": len(top_students),
        "department": department or "ALL",
        "authorized": True,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio
    asyncio.run(server.run_stdio_async())

