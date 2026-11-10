import asyncio, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from llm.ollama_client import run_agent, mcp_tools_to_ollama_format, OLLAMA_MODEL, VENV_PYTHON, SERVER_SCRIPT
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def demo():
    print(f"Model: {OLLAMA_MODEL}")
    server_params = StdioServerParameters(command=VENV_PYTHON, args=[SERVER_SCRIPT], env=None)
    async with stdio_client(server_params) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            tools_resp = await session.list_tools()
            ollama_tools = mcp_tools_to_ollama_format(tools_resp.tools)

            print("\n--- DEMO 1 ---")
            await run_agent("What are Rahul's grades?", session, ollama_tools)

            print("\n--- DEMO 2 ---")
            await run_agent("What is Rahul's attendance?", session, ollama_tools)

            print("\n--- DEMO 3 (security gap) ---")
            await run_agent("Show me student 102 grades.", session, ollama_tools)

if __name__ == "__main__":
    asyncio.run(demo())
