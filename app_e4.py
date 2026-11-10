import asyncio
import json
import os
import sys
import functools

from flask import Flask, jsonify, request, render_template, Response
import jwt as pyjwt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

sys.path.insert(0, os.path.dirname(__file__))

from database.database import fetch_student, fetch_attendance, fetch_grades
from auth.jwt_utils import issue_token, verify_token, extract_token_from_header
from auth.users import authenticate
from auth.policy import allow_request
from auth.audit import log_access, fetch_audit_log, ensure_audit_table

app = Flask(__name__, template_folder="templates")

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[]
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SERVER_SCRIPT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "server",
        "mcp_server_e4.py"
    )
)

OLLAMA_MODEL = os.environ.get(
    "OLLAMA_MODEL",
    "qwen3:4b"
)
KNOWN_STUDENTS = None  # Student IDs are read from the ERP database at request time.

# Ensure audit table exists at startup
ensure_audit_table()


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

# ---------------------------------------------------------------------------
# Helper: JWT auth decorator
# ---------------------------------------------------------------------------

def require_auth(f):

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        token = extract_token_from_header(request.headers.get("Authorization"))
        if not token:
            return jsonify({"error": "Missing Authorization header. Please log in."}), 401
        try:
            caller = verify_token(token)
        except pyjwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired. Please log in again."}), 401
        except pyjwt.InvalidTokenError as e:
            app.logger.warning(
            "JWT verification failed: %s - %s",
            type(e).__name__,
            str(e)
            )
        return jsonify({
            "error": "Invalid or expired authentication token."
        }), 401
        return f(caller, *args, **kwargs)
    return wrapper

# ---------------------------------------------------------------------------
# Route: Serve the SPA
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index_e4.html")

# ---------------------------------------------------------------------------
# API: Auth
# ---------------------------------------------------------------------------

@app.route("/api/login", methods=["POST"])
@limiter.limit("5 per minute")
def api_login():

    data     = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON request."}), 400
    
    username = data.get("username", "")
    password = data.get("password", "")

    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "Invalid credentials format."}), 400

    username = username.strip().lower()

    if len(username) > 100 or len(password) > 256:
        return jsonify({"error": "Input exceeds allowed length."}), 400
    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400

    user = authenticate(username, password)
    if user is None:
        return jsonify({"error": "Invalid username or password."}), 401

    token = issue_token(user)
    return jsonify({
        "token": token,
        "user": {
            "name":       user["name"],
            "role":       user["role"],
            "student_id": user["student_id"],
            "sub":        user["sub"],
        },
    })


@app.route("/api/me")
@require_auth
def api_me(caller):
    """Return current user info extracted from the JWT."""
    return jsonify({
        "sub":        caller["sub"],
        "name":       caller["name"],
        "role":       caller["role"],
        "student_id": caller.get("student_id"),
    })

# ---------------------------------------------------------------------------
# API: Students (all protected + authorized)
# ---------------------------------------------------------------------------

@app.route("/api/stats")
@require_auth
def api_stats(caller):
    """Return dashboard statistics."""
    from database.database import get_connection
    with get_connection() as conn:
        total_students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        total_faculty = conn.execute("SELECT COUNT(*) FROM faculty").fetchone()[0]
        total_departments = conn.execute("SELECT COUNT(*) FROM departments").fetchone()[0]
    return jsonify({
        "total_students": total_students,
        "total_faculty": total_faculty,
        "total_departments": total_departments,
        "total_tools": 4,
    })


@app.route("/api/students")
@require_auth
def api_students(caller):

    role = caller.get("role")

    if role == "admin":
        from database.database import fetch_all_students
        return jsonify(fetch_all_students())

    if role == "teacher":
        faculty_id = caller.get("faculty_id")

        if not faculty_id:
            return jsonify({"error": "Faculty identity missing"}), 403

        from database.database import fetch_students_for_faculty

        return jsonify(
            fetch_students_for_faculty(faculty_id)
        )

    if role == "student":
        profile = fetch_student(caller["student_id"])
        return jsonify([profile] if profile else [])

    return jsonify({"error": "Unauthorized role"}), 403

@app.route("/api/students/top-cgpa")
@require_auth
def api_top_students(caller):
    """Return top students ranked by CGPA (restricted to faculty and admin)."""
    result = allow_request(caller, "get_top_students_by_cgpa", None)
    log_access(caller, "get_top_students_by_cgpa", None, result.allowed, result.reason)
    if not result.allowed:
        return jsonify({"error": result.reason, "authorized": False}), 403

    from database.database import fetch_top_students_by_cgpa
    limit = request.args.get("limit", 10, type=int)
    dept = request.args.get("department", None)
    return jsonify(fetch_top_students_by_cgpa(limit=limit, department=dept))


@app.route("/api/student/<int:student_id>/profile")
@require_auth
def api_student_profile(caller, student_id):
    result = allow_request(caller, "get_student_profile", student_id)
    log_access(caller, "get_student_profile", student_id, result.allowed, result.reason)

    if not result.allowed:
        return jsonify({"error": result.reason, "authorized": False}), 403

    profile = fetch_student(student_id)
    if profile is None:
        return jsonify({"error": f"Student {student_id} not found"}), 404
    return jsonify({**profile, "authorized": True})


@app.route("/api/student/<int:student_id>/attendance")
@require_auth
def api_student_attendance(caller, student_id):
    result = allow_request(caller, "get_attendance", student_id)
    log_access(caller, "get_attendance", student_id, result.allowed, result.reason)

    if not result.allowed:
        return jsonify({"error": result.reason, "authorized": False}), 403

    profile = fetch_student(student_id)
    if profile is None:
        return jsonify({"error": f"Student {student_id} not found"}), 404
    records = fetch_attendance(student_id)
    return jsonify({
        "student_id":   student_id,
        "student_name": profile["name"],
        "department":   profile["department"],
        "attendance":   records,
        "authorized":   True,
    })


@app.route("/api/student/<int:student_id>/grades")
@require_auth
def api_student_grades(caller, student_id):
    result = allow_request(caller, "get_grades", student_id)
    log_access(caller, "get_grades", student_id, result.allowed, result.reason)

    if not result.allowed:
        return jsonify({"error": result.reason, "authorized": False}), 403

    profile = fetch_student(student_id)
    if profile is None:
        return jsonify({"error": f"Student {student_id} not found"}), 404
    records = fetch_grades(student_id)
    return jsonify({
        "student_id":   student_id,
        "student_name": profile["name"],
        "department":   profile["department"],
        "cgpa":         profile.get("cgpa", 0.0),
        "grades":       records,
        "authorized":   True,
    })

# ---------------------------------------------------------------------------
# API: Audit Log (admin only)
# ---------------------------------------------------------------------------

@app.route("/api/audit-log")
@require_auth
def api_audit_log(caller):
    """
    GET /api/audit-log
    Returns the audit log.
    Only admin role is permitted.
    """
    if caller["role"] != "admin":
        return jsonify({
            "error": "Access denied. Audit log is restricted to admin users.",
            "authorized": False,
        }), 403

    limit = request.args.get("limit", default=100, type=int)

    if limit is None or not 1 <= limit <= 500:
        return jsonify({
        "error": "Audit log limit must be between 1 and 500."
    }), 400

    records = fetch_audit_log(limit=limit)
    return jsonify(records)

# ---------------------------------------------------------------------------
# API: Security Gap Comparison (E2 vs E3 demo)
# ---------------------------------------------------------------------------

@app.route("/api/security-comparison")
@require_auth
def api_security_comparison(caller):
    """
    Demonstrates how E3 fixes the E2 security gap.
    Shows what WOULD happen under E2 (no check) vs what E3 does (policy enforced).
    """
    if caller["role"] != "admin":
        return jsonify({"error": "Admin only."}), 403

    # Simulate: student Rahul (101) trying to access Aman (102)'s data
    simulated_student = {"sub": "101", "name": "Rahul", "role": "student", "student_id": 101}
    e2_result = "ALLOWED (no check) -- E2 returns Aman's grades to Rahul"
    e3_result = allow_request(simulated_student, "get_grades", 102)

    return jsonify({
        "scenario": "Rahul (student 101) requests grades for student 102 (Aman)",
        "e2_behavior": e2_result,
        "e3_behavior": {
            "allowed": e3_result.allowed,
            "reason":  e3_result.reason,
        },
        "gap_closed": not e3_result.allowed,
    })

# ---------------------------------------------------------------------------
# API: Chat with Qwen3 + Secured MCP Agent
# ---------------------------------------------------------------------------

async def _chat_with_agent_e3(question: str, caller: dict, caller_token: str, history: list = None) -> str:
    """
    Run a question through Qwen3 + the E3/E4 secured MCP server.
    The caller_token is injected into every tool call so the MCP server
    can enforce authorization.
    Supports multi-turn chat history for contextual follow-ups.
    """
    import ollama
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    def mcp_tools_to_ollama_format(mcp_tools):
        tools = []
        for t in mcp_tools:
            # Hide caller_token from the LLM's tool schema -- we inject it ourselves
            schema = dict(t.input_schema or {})
            props  = dict(schema.get("properties", {}))
            props.pop("caller_token", None)
            required = [r for r in schema.get("required", []) if r != "caller_token"]
            schema = {**schema, "properties": props, "required": required}
            tools.append({
                "type": "function",
                "function": {
                    "name":        t.name,
                    "description": t.description or "",
                    "parameters":  schema,
                },
            })
        return tools

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER_SCRIPT],
        env=os.environ.copy(),
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools_response  = await session.list_tools()
            ollama_tools    = mcp_tools_to_ollama_format(tools_response.tools)

            student_id_hint = f", student_id: {caller.get('student_id')}" if caller.get("student_id") else ""
            if caller.get("role") == "student":
                ranking_instruction = (
                    "Students are strictly prohibited from viewing peer rankings, academic leaderboards, or other students' grades. "
                    "If the user asks for top students, highest CGPA, or another student's records, refuse and report that peer academic rankings and other students' grades are confidential and restricted to faculty and administration."
                )
            else:
                ranking_instruction = "When asked for top students or CGPA rankings, call get_top_students_by_cgpa."

            system_prompt = (
                f"You are a secure College ERP academic assistant. "
                f"The authenticated user is {caller['name']} (role: {caller['role']}{student_id_hint}). "
                f"When the user asks for their own records (grades, attendance, profile, timetable), immediately call the corresponding tool with student_id={caller.get('student_id')}. "
                f"{ranking_instruction} "
                f"You have access to a database of 500 students across 5 departments (CSE, ECE, EE, ME, DS). "
                f"If the user asks to format or present previous results (e.g., in a table or list), use the conversation history to format the data directly. "
                f"If the user asks about data they are not authorized to see, report the denial clearly. "
                f"Format responses clearly with Markdown tables or lists when appropriate. Be concise, direct, and helpful."
            )

            messages = [{"role": "system", "content": system_prompt}]

            if history and isinstance(history, list):
                for turn in history[-8:]:
                    r = turn.get("role")
                    c = (turn.get("content") or "").strip()
                    if r in ["user", "assistant"] and c and c != question:
                        messages.append({"role": r, "content": c})

            messages.append({"role": "user", "content": question})

            tool_calls_log = []
            max_iterations = 5

            for _ in range(max_iterations):
                response = ollama.chat(
                    model=OLLAMA_MODEL,
                    messages=messages,
                    tools=ollama_tools,
                    options={"temperature": 0, "num_predict": 2048},
                )

                message       = response.message if hasattr(response, "message") else response["message"]
                raw_tool_calls = message.tool_calls if hasattr(message, "tool_calls") else message.get("tool_calls")
                tool_calls    = raw_tool_calls or []

                if not tool_calls:
                    raw_content  = message.content if hasattr(message, "content") else message.get("content", "")
                    final_answer = (raw_content or "").strip()
                    if "<think>" in final_answer:
                        parts        = final_answer.split("</think>")
                        final_answer = parts[-1].strip() if len(parts) > 1 else final_answer
                    # Do NOT return raw thinking internal monologue to the user
                    if not final_answer:
                        final_answer = "Could you please specify which information you would like (for example: your grades, your attendance records, or top students by CGPA)?"
                    return json.dumps({
                        "answer":        final_answer,
                        "tool_calls_log": tool_calls_log,
                    })

                serialized_tool_calls = []
                for tc in tool_calls:
                    if hasattr(tc, "function"):
                        serialized_tool_calls.append({
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            }
                        })
                    else:
                        serialized_tool_calls.append(tc)

                messages.append({
                    "role": message.role if hasattr(message, "role") else message.get("role", "assistant"),
                    "content": message.content if hasattr(message, "content") else message.get("content", "") or "",
                    "tool_calls": serialized_tool_calls,
                })

                for tc in tool_calls:
                    if hasattr(tc, "function"):
                        fn_name = tc.function.name
                        fn_args = tc.function.arguments
                    else:
                        fn_name = tc["function"]["name"]
                        fn_args = tc["function"]["arguments"]

                    if isinstance(fn_args, str):
                        import json as _json
                        fn_args = _json.loads(fn_args)

                    # Inject the caller's JWT token before sending to the MCP server
                    fn_args["caller_token"] = caller_token

                    result      = await session.call_tool(fn_name, fn_args)
                    tool_result = result.content[0].text if result.content else "{}"

                    tool_calls_log.append({
                        "tool":           fn_name,
                        "args":           {k: v for k, v in fn_args.items() if k != "caller_token"},
                        "result_preview": tool_result[:300],
                    })

                    messages.append({"role": "tool", "content": tool_result})

    return json.dumps({"answer": "(no answer)", "tool_calls_log": tool_calls_log})


@app.route("/api/chat", methods=["POST"])
@require_auth
def api_chat(caller):
    """
    POST /api/chat  (requires JWT)
    Body: { "question": "What are my grades?", "history": [...] }
    Returns: { "answer": "...", "tool_calls_log": [...] }
    """
    token    = extract_token_from_header(request.headers.get("Authorization"))
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON request."}), 400

    question = data.get("question", "")
    history = data.get("history", [])

    if not isinstance(question, str):
        return jsonify({"error": "Question must be a string."}), 400

    question = question.strip()

    if not question:
        return jsonify({"error": "No question provided."}), 400

    if len(question) > 2000:
        return jsonify({"error": "Question is too long."}), 400

    if not isinstance(history, list):
        return jsonify({"error": "Invalid conversation history."}), 400

    if len(history) > 8:
        return jsonify({"error": "Conversation history is too long."}), 400

    for turn in history:
        if not isinstance(turn, dict):
            return jsonify({"error": "Invalid history entry."}), 400

        if turn.get("role") not in ("user", "assistant"):
            return jsonify({"error": "Invalid history role."}), 400

        if not isinstance(turn.get("content"), str):
            return jsonify({"error": "Invalid history content."}), 400

        if len(turn["content"]) > 4000:
            return jsonify({"error": "History entry is too long."}), 400

        if not question:
            return jsonify({"error": "No question provided"}), 400

    try:
        result_json = run_async(_chat_with_agent_e3(question, caller, token, history=history))
        return Response(result_json, content_type="application/json")
    except Exception as e:
        app.logger.exception("Chat agent request failed")

        error_msg = str(e).lower()

        if "connection" in error_msg or "refused" in error_msg:
            return jsonify({
            "error": "AI service unavailable. Please ensure Ollama is running."
            }), 503

        return jsonify({
        "error": "The assistant could not process your request."
        }), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  College ERP Web Dashboard  --  E4 FINAL")
    print("  Open: http://localhost:5002")
    print("=" * 60)
    print()
    print("  Demo users:")
    print("    rahul / rahul123   (student, ID 101)")
    print("    aman  / aman123    (student, ID 102)")
    print("    priya / priya123   (student, ID 103)")
    print("    teacher / teacher123 (teacher)")
    print("    admin / admin123   (admin -- sees all)")
    print("=" * 60)
    app.run(
    host="127.0.0.1",
    port=5002,
    debug=False,
    use_reloader=False
)
