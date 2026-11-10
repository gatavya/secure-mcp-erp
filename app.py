"""
app.py  --  Flask Web Dashboard for College ERP MCP
-----------------------------------------------------
WHAT IT IS:
  A thin Flask REST API that bridges the web UI to the existing
  database layer and MCP/LLM pipeline.

HOW IT CONNECTS:
  Browser  -->  Flask (this file)  -->  database.py  -->  erp.db
                                   -->  ollama_client.py  -->  MCP Server  -->  Qwen3

HOW TO RUN:
  python app.py
  Then open: http://localhost:5000
"""

import asyncio
import json
import os
import sys
import threading
import sqlite3

from flask import Flask, jsonify, request, render_template, Response, stream_with_context

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from database.database import fetch_student, fetch_attendance, fetch_grades

app = Flask(__name__)

# ---------------------------------------------------------------------------
# MCP / LLM configuration (mirrors ollama_client.py)
# ---------------------------------------------------------------------------

_default_venv = os.path.abspath(
    os.path.join(os.path.dirname(__file__), ".venv", "Scripts", "python.exe")
)
VENV_PYTHON = _default_venv if os.path.exists(_default_venv) else sys.executable
SERVER_SCRIPT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "server", "mcp_server.py")
)
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b")

# Known students (so the UI can list them without a DB call)
KNOWN_STUDENTS = [101, 102, 103]

# ---------------------------------------------------------------------------
# Helper: run async coroutine from sync Flask context
# ---------------------------------------------------------------------------

def run_async(coro):
    """Run an async coroutine in a new event loop (called from sync Flask handlers)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Route: Serve the Single-Page App
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# API: Students
# ---------------------------------------------------------------------------

@app.route("/api/students")
def api_students():
    """Return a list of all student profiles."""
    from database.database import fetch_all_students
    return jsonify(fetch_all_students())


@app.route("/api/student/<int:student_id>/profile")
def api_student_profile(student_id):
    profile = fetch_student(student_id)
    if profile is None:
        return jsonify({"error": f"Student {student_id} not found"}), 404
    return jsonify(profile)


@app.route("/api/student/<int:student_id>/attendance")
def api_student_attendance(student_id):
    profile = fetch_student(student_id)
    if profile is None:
        return jsonify({"error": f"Student {student_id} not found"}), 404
    records = fetch_attendance(student_id)
    return jsonify({
        "student_id": student_id,
        "student_name": profile["name"],
        "department": profile["department"],
        "attendance": records,
    })


@app.route("/api/student/<int:student_id>/grades")
def api_student_grades(student_id):
    profile = fetch_student(student_id)
    if profile is None:
        return jsonify({"error": f"Student {student_id} not found"}), 404
    records = fetch_grades(student_id)
    return jsonify({
        "student_id": student_id,
        "student_name": profile["name"],
        "department": profile["department"],
        "cgpa": profile.get("cgpa", 0.0),
        "grades": records,
    })


# ---------------------------------------------------------------------------
# API: Security Gap Demo
# ---------------------------------------------------------------------------

@app.route("/api/security-gap-demo")
def api_security_gap_demo():
    """
    Demonstrates the E2 baseline security gap:
    Authenticated user = 101 (Rahul), but they can access student 102's data.
    """
    authenticated_user_id = 101
    target_student_id = 102

    auth_profile = fetch_student(authenticated_user_id)
    target_grades = fetch_grades(target_student_id)
    target_profile = fetch_student(target_student_id)

    return jsonify({
        "authenticated_user": auth_profile,
        "requested_student_id": target_student_id,
        "target_student": target_profile,
        "data_returned": target_grades,
        "authorization_enforced": False,
        "gap_explanation": (
            "The MCP server does NOT check whether the authenticated user (Rahul, ID 101) "
            "is allowed to access student 102 (Aman)'s grades. "
            "Any caller that knows a student_id can retrieve that student's data."
        ),
    })


# ---------------------------------------------------------------------------
# API: Chat with Qwen3 + MCP Agent
# ---------------------------------------------------------------------------

async def _chat_with_agent(question: str) -> str:
    """
    Run a single question through the Qwen3 + MCP pipeline.
    Returns the final natural-language answer.
    """
    import ollama
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    def mcp_tools_to_ollama_format(mcp_tools):
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": t.input_schema or {},
                },
            }
            for t in mcp_tools
        ]

    server_params = StdioServerParameters(
        command=VENV_PYTHON,
        args=[SERVER_SCRIPT],
        env=None,
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools_response = await session.list_tools()
            ollama_tools = mcp_tools_to_ollama_format(tools_response.tools)

            system_prompt = (
                "/no_think "
                "You are a helpful College ERP assistant. "
                "You have access to a database of students: "
                "Rahul (ID 101, CSE), Aman (ID 102, CSE), Priya (ID 103, ECE). "
                "When the user asks about a student's grades, attendance, or profile, "
                "use the appropriate tool to look up the real data. "
                "Always use tools to get real data. Give a short, direct answer in 1-2 sentences."
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ]

            tool_calls_log = []
            max_iterations = 5

            for _ in range(max_iterations):
                response = ollama.chat(
                    model=OLLAMA_MODEL,
                    messages=messages,
                    tools=ollama_tools,
                    options={"temperature": 0, "num_predict": 512},
                )

                # Support both object-style (newer ollama lib) and dict-style responses
                message = response.message if hasattr(response, "message") else response["message"]
                raw_tool_calls = message.tool_calls if hasattr(message, "tool_calls") else message.get("tool_calls")
                tool_calls = raw_tool_calls or []

                if not tool_calls:
                    raw_content = message.content if hasattr(message, "content") else message.get("content", "")
                    final_answer = (raw_content or "").strip()
                    # Strip <think>...</think> tags from Qwen3
                    if "<think>" in final_answer:
                        parts = final_answer.split("</think>")
                        final_answer = parts[-1].strip() if len(parts) > 1 else final_answer
                    # If content is still empty, fall back to the thinking field
                    # (happens when Qwen3 uses thinking mode and num_predict cuts off before </think>)
                    if not final_answer:
                        thinking = getattr(message, "thinking", None) or ""
                        if thinking:
                            # Extract a usable sentence from the thinking output as last resort
                            final_answer = "(Model response was empty — please try again or rephrase your question.)"
                    return json.dumps({
                        "answer": final_answer,
                        "tool_calls_log": tool_calls_log,
                    })

                # Append message as dict for the next round
                msg_dict = message if isinstance(message, dict) else {"role": message.role, "content": message.content or "", "tool_calls": raw_tool_calls}
                messages.append(msg_dict)

                for tc in tool_calls:
                    # Support both object-style and dict-style tool calls
                    if hasattr(tc, "function"):
                        fn_name = tc.function.name
                        fn_args = tc.function.arguments
                    else:
                        fn_name = tc["function"]["name"]
                        fn_args = tc["function"]["arguments"]
                    if isinstance(fn_args, str):
                        fn_args = json.loads(fn_args)

                    result = await session.call_tool(fn_name, fn_args)
                    tool_result = result.content[0].text if result.content else "{}"

                    tool_calls_log.append({
                        "tool": fn_name,
                        "args": fn_args,
                        "result_preview": tool_result[:300],
                    })

                    messages.append({
                        "role": "tool",
                        "content": tool_result,
                    })

    return json.dumps({"answer": "(no answer)", "tool_calls_log": tool_calls_log})


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """
    POST /api/chat
    Body: { "question": "What are Rahul's grades?" }
    Returns: { "answer": "...", "tool_calls_log": [...] }
    """
    data = request.get_json(force=True)
    question = (data or {}).get("question", "").strip()

    if not question:
        return jsonify({"error": "No question provided"}), 400

    try:
        result_json = run_async(_chat_with_agent(question))
        return Response(result_json, content_type="application/json")
    except Exception as e:
        error_msg = str(e)
        # Provide a helpful message if Ollama is not running
        if "connection" in error_msg.lower() or "refused" in error_msg.lower():
            return jsonify({
                "error": "Ollama is not running. Please start Ollama with: ollama serve",
                "detail": error_msg,
            }), 503
        return jsonify({"error": f"Agent error: {error_msg}"}), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  College ERP Web Dashboard")
    print("  Open: http://localhost:5000")
    print("=" * 60)
    app.run(debug=True, port=5000, use_reloader=False)
