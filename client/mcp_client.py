"""
mcp_client.py  --  Standalone MCP Client for College ERP
----------------------------------------------------------
WHAT IT IS:
  A Python client that connects to the MCP server using stdio transport,
  discovers available tools, and can call them.

WHY WE NEED IT:
  This proves the MCP transport layer works independently of the LLM.
  We can call get_grades(101) through the full MCP protocol and see the result.

HOW IT CONNECTS:
  This script  -->  launches mcp_server.py as a subprocess
              -->  communicates via stdin/stdout (stdio transport)
              -->  MCP protocol (JSON-RPC under the hood)
              -->  mcp_server.py  -->  database.py  -->  erp.db

HOW TO RUN:
  python client/mcp_client.py
"""

import asyncio
import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# Path to Python in the virtual environment (fallback to sys.executable if not present)
_default_venv = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".venv", "Scripts", "python.exe")
)
VENV_PYTHON = _default_venv if os.path.exists(_default_venv) else sys.executable

# Path to the MCP server script
SERVER_SCRIPT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "server", "mcp_server.py")
)


async def run_demo():
    """
    Connect to the MCP server and run a series of demo tool calls.
    This demonstrates the MCP client -> server -> SQLite -> result flow.
    """
    print("=" * 60)
    print(" MCP CLIENT -- College ERP Demo")
    print("=" * 60)
    print()

    # StdioServerParameters tells the MCP client HOW to launch the server:
    # - command: the Python executable in our venv
    # - args: the server script to run
    server_params = StdioServerParameters(
        command=os.path.abspath(VENV_PYTHON),
        args=[os.path.abspath(SERVER_SCRIPT)],
        env=None,  # inherit current environment
    )

    # stdio_client launches the server as a subprocess and gives us
    # two streams: read_stream (server -> client) and write_stream (client -> server)
    async with stdio_client(server_params) as (read_stream, write_stream):
        # ClientSession wraps the streams and implements the MCP protocol
        async with ClientSession(read_stream, write_stream) as session:

            # Step 1: Initialize (handshake with server)
            await session.initialize()
            print("[OK] Connected to MCP server")
            print()

            # Step 2: List available tools
            tools_response = await session.list_tools()
            print(f"[Tools Available] {len(tools_response.tools)} tools registered:")
            for tool in tools_response.tools:
                print(f"  - {tool.name}: {tool.description[:60]}...")
            print()

            # ---------------------------------------------------------------
            # Demo calls
            # ---------------------------------------------------------------

            print("-" * 60)
            print("DEMO 1: get_student_profile(student_id=101)")
            print("-" * 60)
            result = await session.call_tool("get_student_profile", {"student_id": 101})
            print("Result:", format_result(result))
            print()

            print("-" * 60)
            print("DEMO 2: get_grades(student_id=101)")
            print("-" * 60)
            result = await session.call_tool("get_grades", {"student_id": 101})
            print("Result:", format_result(result))
            print()

            print("-" * 60)
            print("DEMO 3: get_attendance(student_id=102)")
            print("-" * 60)
            result = await session.call_tool("get_attendance", {"student_id": 102})
            print("Result:", format_result(result))
            print()

            print("-" * 60)
            print("DEMO 4: get_grades(student_id=999) -- student not found")
            print("-" * 60)
            result = await session.call_tool("get_grades", {"student_id": 999})
            print("Result:", format_result(result))
            print()

    print("[Done] MCP client demo completed.")


def format_result(result) -> str:
    """Extract text content from MCP tool result and pretty-print it."""
    if result.content:
        # MCP returns content as a list of ContentBlock objects
        # For structured tool results, we get TextContent
        text = result.content[0].text if result.content else "(empty)"
        try:
            # Try to parse as JSON for nice formatting
            data = json.loads(text)
            return json.dumps(data, indent=2)
        except (json.JSONDecodeError, TypeError):
            return text
    return "(no content)"


if __name__ == "__main__":
    asyncio.run(run_demo())
