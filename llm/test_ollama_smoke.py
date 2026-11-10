"""
Quick smoke test for the Ollama + MCP integration.
Run as: python llm/test_ollama_smoke.py
This is NOT the interactive demo - it just tests one question automatically.
"""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from llm.ollama_client import run_agent, mcp_tools_to_ollama_format, OLLAMA_MODEL, VENV_PYTHON, SERVER_SCRIPT
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def smoke_test():
    print(f"Testing with model: {OLLAMA_MODEL}")
    server_params = StdioServerParameters(command=VENV_PYTHON, args=[SERVER_SCRIPT], env=None)
    async with stdio_client(server_params) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            tools_resp = await session.list_tools()
            ollama_tools = mcp_tools_to_ollama_format(tools_resp.tools)
            print(f"Tools loaded: {[t['function']['name'] for t in ollama_tools]}")
            print()
            # Test question 1
            await run_agent("What are Rahul's grades?", session, ollama_tools)
            print()

if __name__ == "__main__":
    asyncio.run(smoke_test())
