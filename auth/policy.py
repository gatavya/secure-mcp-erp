"""
policy.py  --  Authorization Policy Layer (E3)
-----------------------------------------------
WHAT IT IS:
  The single source of truth for access control decisions.
  Every MCP tool call passes through this before hitting the database.

WHY A SEPARATE MODULE:
  Keeping policy logic here (not scattered in route handlers or DB functions)
  makes it easy to audit, test, and upgrade in E4 (e.g. RBAC rules engine).

POLICY RULES (E3):
  Role: student
    - Can call get_student_profile / get_attendance / get_grades
      ONLY for their own student_id (caller.student_id == requested_student_id)
    - Any attempt to access another student's data is DENIED

  Role: admin or teacher
    - Can call any tool for any student_id -- ALLOWED

RETURN VALUE:
  allow_request() returns a PolicyResult namedtuple:
    .allowed  bool    -- True = proceed, False = reject
    .reason   str     -- Human-readable explanation (shown in audit log & UI)
"""

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class PolicyResult:
    allowed: bool
    reason:  str


# ---------------------------------------------------------------------------
# Allowed tools (whitelist)
# ---------------------------------------------------------------------------

ALLOWED_TOOLS = {
    "get_student_profile",
    "get_attendance",
    "get_grades",
    "get_student_timetable",
    "get_top_students_by_cgpa",
}


# ---------------------------------------------------------------------------
# Core policy function
# ---------------------------------------------------------------------------

def allow_request(
    caller: dict,
    tool_name: str,
    requested_student_id: int | None = None,
) -> PolicyResult:
    """
    Evaluate whether the caller is allowed to invoke tool_name
    for the given requested_student_id.

    Args:
        caller: JWT payload dict — must have keys: role, student_id, name, sub
        tool_name: Name of the MCP tool being called
        requested_student_id: The student_id argument passed to the tool, or None for aggregate tools

    Returns:
        PolicyResult(allowed=True/False, reason=<explanation>)
    """

    # 1. Tool must be in the allowed list
    if tool_name not in ALLOWED_TOOLS:
        return PolicyResult(
            allowed=False,
            reason=f"Tool '{tool_name}' is not a recognized tool.",
        )

    role = caller.get("role")
    caller_student_id = caller.get("student_id")
    caller_name = caller.get("name", caller.get("sub", "unknown"))

    # Academic Leaderboard / Top CGPA: restricted to faculty and admin only
    if tool_name == "get_top_students_by_cgpa":
        if role in ["admin", "teacher"]:
            return PolicyResult(
                allowed=True,
                reason=f"ALLOWED: {role.capitalize()} '{caller_name}' accessed academic rankings (top students by CGPA).",
            )
        else:
            return PolicyResult(
                allowed=False,
                reason=f"DENIED: Student '{caller_name}' is not authorized to view peer academic rankings or top students list.",
            )

    # 2. Admin & Teacher: access to all students
    if role in ["admin", "teacher"]:
        return PolicyResult(
            allowed=True,
            reason=(
                f"ALLOWED: {role.capitalize()} '{caller_name}' has access "
                f"to {tool_name}(student_id={requested_student_id})."
            ),
        )

    # 3. Student: can only access their own data
    if role == "student":
        if caller_student_id == requested_student_id:
            return PolicyResult(
                allowed=True,
                reason=(
                    f"ALLOWED: Student '{caller_name}' (ID {caller_student_id}) "
                    f"accessed their own data via {tool_name}."
                ),
            )
        else:
            return PolicyResult(
                allowed=False,
                reason=(
                    f"DENIED: Student '{caller_name}' (ID {caller_student_id}) "
                    f"attempted to access student {requested_student_id}'s data "
                    f"via {tool_name}. Cross-student access is not permitted."
                ),
            )

    # 4. Unknown role
    return PolicyResult(
        allowed=False,
        reason=f"DENIED: Unknown role '{role}' for caller '{caller_name}'.",
    )
