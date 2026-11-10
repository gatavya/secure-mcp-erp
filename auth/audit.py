"""
audit.py  --  Audit Log Layer (E3)
------------------------------------
WHAT IT IS:
  Functions to write and read the audit_log table in erp.db.
  Every MCP tool access attempt is recorded here -- allowed or denied.

WHY IT MATTERS:
  Audit logging is a core security control. It answers:
    "Who accessed what data, when, and was it allowed?"
  This is what makes E3 a proper secure system vs the E2 baseline.

AUDIT LOG SCHEMA:
  id            INTEGER  -- auto-increment
  timestamp     TEXT     -- ISO-8601 UTC timestamp
  caller_sub    TEXT     -- JWT 'sub' claim (student_id or "admin")
  caller_name   TEXT     -- Human-readable name
  caller_role   TEXT     -- "student" | "admin"
  tool_name     TEXT     -- MCP tool called
  requested_id  INTEGER  -- student_id argument passed to the tool
  allowed       INTEGER  -- 1 = allowed, 0 = denied
  reason        TEXT     -- policy decision explanation
"""

import sqlite3
import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "database" / "erp.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_audit_table() -> None:
    """Create the audit_log table if it doesn't exist yet."""
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp     TEXT    NOT NULL,
                caller_sub    TEXT    NOT NULL,
                caller_name   TEXT    NOT NULL,
                caller_role   TEXT    NOT NULL,
                tool_name     TEXT    NOT NULL,
                requested_id  INTEGER NOT NULL,
                allowed       INTEGER NOT NULL,
                reason        TEXT    NOT NULL
            )
        """)


def log_access(
    caller: dict,
    tool_name: str,
    requested_student_id: int | None,
    allowed: bool,
    reason: str,
) -> None:
    """
    Write one audit record.

    Args:
        caller: JWT payload dict (role, student_id, name, sub)
        tool_name: MCP tool that was called
        requested_student_id: The student_id argument, or None/0 for aggregate queries
        allowed: True if the policy allowed the request
        reason: PolicyResult.reason string
    """
    ensure_audit_table()
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    req_id = requested_student_id if (requested_student_id is not None) else 0
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO audit_log
              (timestamp, caller_sub, caller_name, caller_role,
               tool_name, requested_id, allowed, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                str(caller.get("sub", "")),
                caller.get("name", ""),
                caller.get("role", ""),
                tool_name,
                req_id,
                1 if allowed else 0,
                reason,
            ),
        )


def fetch_audit_log(limit: int = 100) -> list[dict]:
    """
    Return the most recent audit log entries (newest first).

    Args:
        limit: Maximum number of records to return

    Returns:
        List of dicts with all audit_log columns
    """
    ensure_audit_table()
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
