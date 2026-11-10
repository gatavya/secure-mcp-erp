"""
ollama_client.py  --  Qwen3 + MCP Tool-Calling Agent
------------------------------------------------------
WHAT IT IS:
  The main interactive entry point for E2.
  It connects the user's natural-language question to Qwen3,
  and Qwen3 uses MCP tools to answer from the real database.

WHY WE NEED IT:
  Without this, the user would have to speak SQL or MCP protocol directly.
  With this, the user types "What are Rahul's grades?" and gets a real answer.

HOW IT CONNECTS:
  User (natural language)
    --> Qwen3 (decides which tool to call)
    --> MCP Client (executes the tool via MCP protocol)
    --> MCP Server (queries SQLite)
    --> Result sent back to Qwen3
    --> Qwen3 writes a natural language answer

SECURITY NOTE (E2 Baseline):
  The LLM is NOT the authorization authority.
  It decides WHICH tool to call, but the server does not verify
  whether the caller is allowed to access that student's data.
  This gap is intentional and will be addressed in the next phase.

HOW TO RUN:
  python llm/ollama_client.py
"""

import asyncio
import json
import os
import sys

import ollama

# Add project root to path so we can import 'client' and 'database' modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# You can override the model by setting OLLAMA_MODEL environment variable
# e.g.  set OLLAMA_MODEL=qwen3:1.7b  (if your machine is slow)
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b")

_default_venv = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".venv", "Scripts", "python.exe")
)
VENV_PYTHON = _default_venv if os.path.exists(_default_venv) else sys.executable
SERVER_SCRIPT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "server", "mcp_server.py")
)

# ---------------------------------------------------------------------------
# Helper: Convert MCP tool definitions -> Ollama tool format
# ---------------------------------------------------------------------------

def mcp_tools_to_ollama_format(mcp_tools) -> list[dict]:
    """
    Convert MCP tool objects into the dict format Ollama expects.

    Ollama expects each tool as:
    {
      "type": "function",
      "function": {
        "name": "...",
        "description": "...",
        "parameters": { "type": "object", "properties": {...}, "required": [...] }
      }
    }
    """
    ollama_tools = []
    for tool in mcp_tools:
        # MCP tools carry their input schema in tool.input_schema
        schema = tool.input_schema or {}
        ollama_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": schema,
            },
        })
    return ollama_tools


# ---------------------------------------------------------------------------
# Helper: Execute a tool call via the MCP session
# ---------------------------------------------------------------------------

async def execute_mcp_tool(session: ClientSession, tool_name: str, tool_args: dict) -> str:
    """Call one MCP tool and return its result as a JSON string."""
    result = await session.call_tool(tool_name, tool_args)
    # Extract the text from the result content blocks
    if result.content:
        return result.content[0].text
    return json.dumps({"error": "No content returned from tool"})


# ---------------------------------------------------------------------------
# Core: Agentic tool-calling loop
# ---------------------------------------------------------------------------

async def run_agent(user_question: str, session: ClientSession, ollama_tools: list[dict]):
    """
    Send the user's question to Qwen3 with available tools.
    If Qwen3 wants to call a tool, execute it via MCP and send the result back.
    Repeat until Qwen3 gives a final natural-language answer.
    """
    print(f"\n[User] {user_question}")
    print()

    # System prompt: explains the context and what data is available
    system_prompt = (
        "/no_think "
        "You are a helpful College ERP assistant. "
        "You have access to a database of students: "
        "Rahul (ID 101, CSE), Aman (ID 102, CSE), Priya (ID 103, ECE). "
        "When the user asks about a student's grades, attendance, or profile, "
        "use the appropriate tool to look up the real data. "
        "Always use the tools to get real data -- do not make up answers. "
        "Give a clear, concise answer in plain English."
    )

    # Build the initial conversation
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_question},
    ]

    # Agentic loop: keep going until Qwen3 gives a final answer (no more tool calls)
    max_iterations = 5  # safety limit
    for iteration in range(max_iterations):

        # Ask Qwen3 (with tool definitions attached)
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=messages,
            tools=ollama_tools,
            options={"temperature": 0},
        )

        # Support both object-style (newer ollama lib) and dict-style responses
        message = response.message if hasattr(response, "message") else response["message"]
        raw_tool_calls = message.tool_calls if hasattr(message, "tool_calls") else message.get("tool_calls")

        # Did Qwen3 request tool calls?
        tool_calls = raw_tool_calls or []

        if not tool_calls:
            # No tool call -- this is the final natural-language answer
            raw_content = message.content if hasattr(message, "content") else message.get("content", "")
            final_answer = (raw_content or "").strip()
            # Strip thinking tags if present (qwen3 sometimes includes <think>...</think>)
            if "<think>" in final_answer:
                # Keep only the part after </think>
                parts = final_answer.split("</think>")
                final_answer = parts[-1].strip() if len(parts) > 1 else final_answer
            print(f"[Qwen3] {final_answer}")
            return final_answer

        # Qwen3 wants to call tools -- execute each one via MCP
        fn_names = [tc.function.name if hasattr(tc, "function") else tc["function"]["name"] for tc in tool_calls]
        print(f"[Qwen3 -> Tool calls]: {fn_names}")

        # Add Qwen3's tool-call request to the conversation as a plain dict
        msg_dict = message if isinstance(message, dict) else {"role": message.role, "content": message.content or "", "tool_calls": raw_tool_calls}
        messages.append(msg_dict)

        # Execute each tool call and add results to the conversation
        for tc in tool_calls:
            # Support both object-style and dict-style tool calls
            if hasattr(tc, "function"):
                fn_name = tc.function.name
                fn_args = tc.function.arguments
            else:
                fn_name = tc["function"]["name"]
                fn_args = tc["function"]["arguments"]

            # fn_args might be a string or a dict depending on the Ollama version
            if isinstance(fn_args, str):
                fn_args = json.loads(fn_args)

            print(f"  [Executing] {fn_name}({fn_args})")
            tool_result = await execute_mcp_tool(session, fn_name, fn_args)
            print(f"  [MCP Result] {tool_result[:200]}")  # truncate for readability

            # Add tool result back to conversation so Qwen3 can use it
            messages.append({
                "role": "tool",
                "content": tool_result,
            })

        # Continue loop: Qwen3 will now read the tool results and respond

    print("[Warning] Maximum iterations reached without a final answer.")
    return "(no final answer)"


# ---------------------------------------------------------------------------
# Main interactive loop
# ---------------------------------------------------------------------------

async def main():
    """Start the MCP server and enter the interactive Q&A loop."""
    print("=" * 60)
    print(" College ERP -- Qwen3 + MCP Assistant")
    print(f" Model: {OLLAMA_MODEL}")
    print("=" * 60)
    print()
    print("Type your question and press Enter.")
    print("Type 'quit' or 'exit' to stop.")
    print()

    server_params = StdioServerParameters(
        command=VENV_PYTHON,
        args=[SERVER_SCRIPT],
        env=None,
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # Get the tools once and convert to Ollama format
            tools_response = await session.list_tools()
            ollama_tools = mcp_tools_to_ollama_format(tools_response.tools)

            print(f"[Connected] {len(ollama_tools)} MCP tools available:")
            for t in ollama_tools:
                print(f"  - {t['function']['name']}")
            print()

            # Interactive loop
            while True:
                try:
                    user_input = input("You: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n[Exiting]")
                    break

                if not user_input:
                    continue
                if user_input.lower() in ("quit", "exit", "q"):
                    print("[Exiting]")
                    break

                await run_agent(user_input, session, ollama_tools)
                print()


if __name__ == "__main__":
    asyncio.run(main())

