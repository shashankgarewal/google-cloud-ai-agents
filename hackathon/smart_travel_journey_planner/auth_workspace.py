import asyncio
import os
import re
import traceback
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioConnectionParams, StdioServerParameters

async def main():
    print("\n--- Google Workspace Authentication Helper ---")
    print("Initiating connection to Workspace MCP to fetch OAuth URLs...\n")
    
    env_vars = os.environ.copy()
    connection_params = StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uvx",
            args=["workspace-mcp", "--tool-tier", "core"],
            env=env_vars
        ),
        timeout=60.0
    )
    
    toolset = McpToolset(connection_params=connection_params)
    tools = await toolset.get_tools()
    
    auth_urls = {}
    
    for tool in tools:
        if tool.name in ["manage_event", "manage_task", "send_gmail_message"]:
            print(f"Checking {tool.name}...")
            try:
                # We trigger the tool with a valid-looking payload
                # Workspace MCP v3.2.1 requires 'action' and 'user_google_email'
                await tool._run(
                    user_google_email=env_vars.get("USER_GOOGLE_EMAIL", "garewal.sk26@gmail.com"), 
                    action="insert",
                    # Add dummy required params for some tools to avoid "missing param" instead of "auth error"
                    task_list_id="@default",
                    calendar_id="primary",
                    summary="Auth Check",
                    start_time="2026-04-09T10:00:00Z",
                    end_time="2026-04-09T11:00:00Z",
                    to="me",
                    subject="Auth Check",
                    body="Checking auth"
                )
                print(f"  [OK] {tool.name} appears already authenticated.")
            except Exception as e:
                error_str = str(e)
                # Look for the auth URL
                match = re.search(r'(https://accounts\.google\.com/o/oauth2/auth[^\s\)]+)', error_str)
                if match:
                    url = match.group(1)
                    auth_urls[tool.name] = url
                    print(f"  [AUTH] {tool.name} requires authentication.")
                else:
                    print(f"  [ERROR] {tool.name} failed with unexpected error: {error_str[:100]}...")
    
    if not auth_urls:
        print("\nSUCCESS: No authentication required for configured tools!")
    else:
        print("\nACTION REQUIRED: Please authorize the following links in your browser:")
        for tool_name, url in auth_urls.items():
            print(f"\n{tool_name.upper()}:")
            print(url)
        
    print("\n----------------------------------------------\n")

if __name__ == "__main__":
    asyncio.run(main())
