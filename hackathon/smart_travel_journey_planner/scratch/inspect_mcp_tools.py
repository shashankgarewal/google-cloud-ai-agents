import asyncio
import os
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

load_dotenv()

async def list_tools():
    # USAGE: Run this in your terminal where uvx is available:
    # python scratch\inspect_mcp_tools.py
    
    command = os.getenv("WORKSPACE_MCP_COMMAND", "uvx")
    args = os.getenv("WORKSPACE_MCP_ARGS", "workspace-mcp --tool-tier core").split()
    
    print(f"Connecting to MCP server: {command} {' '.join(args)}...")
    
    server_params = StdioServerParameters(
        command=command,
        args=args
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                for tool in tools.tools:
                    if tool.name == "manage_event":
                        print(f"\n✅ Found tool: {tool.name}")
                        print("\nFULL INPUT SCHEMA:")
                        print(json.dumps(tool.inputSchema, indent=2))
                        return
                print("❌ Tool 'manage_event' not found in the tools list.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nTIP: Make sure you run this in a terminal where 'uvx' is in your PATH.")

if __name__ == "__main__":
    asyncio.run(list_tools())
