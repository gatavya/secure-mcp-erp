"""
mcp_server.py  --  College ERP MCP Server (E2 Baseline)
---------------------------------------------------------
WHAT IT IS:
  An MCP server that exposes 3 tools so an LLM can query
  the College ERP database using structured function calls.

WHY WE NEED IT:
  The LLM cannot directly speak SQL. MCP gives it named tools
  with clear descriptions so it knows what to call and when.

HOW IT CONNECTS:
  LLM  -->  MCP Client  -->  [stdio]  -->  mcp_server.py  -->  database.py  -->  erp.db

SECURITY NOTE (E2 Baseline):
  This server does NOT enforce identity-aware authorization.
  Any caller can request any student's data by passing any student_id.
  This is the intentional security gap we demonstrate in E2.
  A proper authorization layer is planned for the next phase.

HOW TO RUN (standalone, for testing):
  python server/mcp_server.py
"""

import sys
import os

# Make sure the project root is on the path so we can import 'database'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp.server.mcpserver import MCPServer
from database.database import fetch_student, fetch_attendance, fetch_grades, fetch_timetable, fetch_top_students_by_cgpa

# ---------------------------------------------------------------------------
# Server Definition
# ---------------------------------------------------------------------------

# MCPServer is the main class from mcp 2.x (previously called FastMCP in v1)
server = MCPServer(
    name="college-erp-mcp",
    description=(
        "Secure MCP Server for Controlled Access to a simulated College ERP. "
        "Provides read-only access to student profiles, attendance, and grades."
    ),
)

# ---------------------------------------------------------------------------
# Tool 1: get_student_profile
# ---------------------------------------------------------------------------

@server.tool(
    name="get_student_profile",
    description=(
        "Retrieve the profile of a student by their student ID. "
        "Returns the student's name and department. "
        "Use this when the user asks 'who is student 101' or 'what department is Rahul in'."
    ),
)
def get_student_profile(student_id: int) -> dict:
    """
    Args:
        student_id: The numeric student ID (e.g. 101, 102, 103)

    Returns:
        A dict with keys: student_id, name, department
        OR an error dict if the student is not found.

    BASELINE NOTE: No authorization check is performed.
    Any caller can retrieve any student's profile.
    """
    if not isinstance(student_id, int) or student_id <= 0:
        return {"error": f"Invalid student_id: {student_id!r}. Must be a positive integer."}

    profile = fetch_student(student_id)
    if profile is None:
        return {"error": f"Student with ID {student_id} not found."}

    return profile


# ---------------------------------------------------------------------------
# Tool 2: get_attendance
# ---------------------------------------------------------------------------

@server.tool(
    name="get_attendance",
    description=(
        "Retrieve the attendance records for a student by their student ID. "
        "Returns subject-wise attendance: classes attended, total classes, and percentage. "
        "Use this when the user asks 'what is Rahul's attendance' or 'how many classes did student 102 attend'."
    ),
)
def get_attendance(student_id: int) -> dict:
    """
    Args:
        student_id: The numeric student ID (e.g. 101, 102, 103)

    Returns:
        A dict with 'student_id' and 'attendance' (list of subject records).

    BASELINE NOTE: No authorization check is performed.
    Any caller can retrieve any student's attendance.
    """
    if not isinstance(student_id, int) or student_id <= 0:
        return {"error": f"Invalid student_id: {student_id!r}. Must be a positive integer."}

    # Verify the student exists first
    profile = fetch_student(student_id)
    if profile is None:
        return {"error": f"Student with ID {student_id} not found."}

    records = fetch_attendance(student_id)
    return {
        "student_id": student_id,
        "student_name": profile["name"],
        "attendance": records,
    }


# ---------------------------------------------------------------------------
# Tool 3: get_grades
# ---------------------------------------------------------------------------

@server.tool(
    name="get_grades",
    description=(
        "Retrieve the grades (marks) for a student by their student ID. "
        "Returns subject-wise grades and semester information. "
        "Use this when the user asks 'what are Rahul's grades' or 'show me grades for student 102'."
    ),
)
def get_grades(student_id: int) -> dict:
    """
    Args:
        student_id: The numeric student ID (e.g. 101, 102, 103)

    Returns:
        A dict with 'student_id', 'student_name', and 'grades' (list of subject records).

    BASELINE NOTE: No authorization check is performed.
    Any caller can retrieve any student's grades.
    """
    if not isinstance(student_id, int) or student_id <= 0:
        return {"error": f"Invalid student_id: {student_id!r}. Must be a positive integer."}

    # Verify the student exists first
    profile = fetch_student(student_id)
    if profile is None:
        return {"error": f"Student with ID {student_id} not found."}

    records = fetch_grades(student_id)
    return {
        "student_id": student_id,
        "student_name": profile["name"],
        "grades": records,
    }


@server.tool(
    name="get_student_timetable",
    description=(
        "Retrieve the weekly timetable for a student by student ID. "
        "Returns subject, faculty, day, time, room, and section. "
        "Use this when asked for a student's class schedule."
    ),
)
def get_student_timetable(student_id: int) -> dict:
    """E2 baseline timetable lookup; deliberately has no authorization check."""
    if not isinstance(student_id, int) or student_id <= 0:
        return {"error": f"Invalid student_id: {student_id!r}. Must be a positive integer."}
    profile = fetch_student(student_id)
    if profile is None:
        return {"error": f"Student with ID {student_id} not found."}
    return {
        "student_id": student_id,
        "student_name": profile["name"],
        "timetable": fetch_timetable(student_id=student_id),
    }


@server.tool(
    name="get_top_students_by_cgpa",
    description=(
        "Retrieve the top students ranked by Cumulative Grade Point Average (CGPA). "
        "Use this when asked for top students, rankers, highest CGPA, academic leaderboard, or honor roll. "
        "Parameters: limit (integer, number of students to return, default 10), "
        "department (optional string filter like 'CSE', 'ECE', 'EE', 'ME', 'DS')."
    ),
)
def get_top_students_by_cgpa(limit: int = 10, department: str | None = None) -> dict:
    """E2 baseline ranking lookup without authorization checks."""
    top_students = fetch_top_students_by_cgpa(limit=limit, department=department)
    return {
        "top_students": top_students,
        "count": len(top_students),
        "department": department or "ALL",
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # run_stdio_async() listens on stdin/stdout (the standard MCP transport)
    # This is how the MCP client launches and communicates with the server
    import asyncio
    asyncio.run(server.run_stdio_async())

