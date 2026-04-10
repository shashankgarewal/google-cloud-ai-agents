import asyncio
import os
import re
from mcp import ClientSession, StdioServerParameters as mcp_StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

async def main():
    load_dotenv()
    print("\n" + "="*50)
    print("   GOOGLE WORKSPACE AUTHENTICATION HELPER")
    print("="*50)
    
    # Locate the executable
    mcp_executable = os.path.join(os.getcwd(), "venv", "Scripts", "workspace-mcp.exe")
    if not os.path.exists(mcp_executable):
        print(f"ERROR: Workspace-MCP not found at {mcp_executable}")
        print("Please run: pip install workspace-mcp")
        return

    env_vars = os.environ.copy()
    
    # Check for credentials in environment
    if not env_vars.get("GOOGLE_OAUTH_CLIENT_ID") or not env_vars.get("GOOGLE_OAUTH_CLIENT_SECRET"):
        print("ERROR: GOOGLE_OAUTH_CLIENT_ID or GOOGLE_OAUTH_CLIENT_SECRET not found in .env")
        return

    print(f"Using Client ID: {env_vars.get('GOOGLE_OAUTH_CLIENT_ID')[:10]}...")
    print("Connecting to MCP server to check status...")

    server_params = mcp_StdioServerParameters(
        command=mcp_executable,
        args=["--tool-tier", "core"],
        env=env_vars
    )
    
    auth_links = []
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Check tools one by one
                tools_to_check = ["manage_task", "manage_event", "send_gmail_message"]
                user_email = env_vars.get("USER_GOOGLE_EMAIL", "garewal.sk26@gmail.com")
                
                for tool in tools_to_check:
                    print(f"Checking {tool}...")
                    # Trigger an insert/send to see if it requires auth
                    try:
                        # Dummy call with minimal required params
                        params = {
                            "user_google_email": user_email,
                            "action": "insert",
                            "task_list_id": "@default",
                            "title": "Auth Check",
                            "calendar_id": "primary",
                            "summary": "Auth Check",
                            "start_time": "2026-04-10T10:00:00Z",
                            "end_time": "2026-04-10T11:00:00Z",
                            "to": "me",
                            "subject": "Auth Check",
                            "body": "Auth Check"
                        }
                        await session.call_tool(tool, params)
                        print(f"  [OK] {tool} is already authorized.")
                    except Exception as e:
                        msg = str(e)
                        if "Authentication Needed" in msg or "https://accounts.google.com" in msg:
                            match = re.search(r'(https://accounts\.google\.com/o/oauth2/auth[^\s\)]+)', msg)
                            if match:
                                auth_links.append((tool, match.group(1)))
                                print(f"  [AUTH] {tool} needs authorization.")
                            else:
                                print(f"  [ERROR] {tool} needs auth but no URL found in response.")
                        else:
                            print(f"  [STDOUT/ERROR] {msg[:200]}")

    except Exception as e:
        print(f"CRITICAL ERROR connecting to MCP: {e}")
        return

    if not auth_links:
        print("\n" + "*"*50)
        print("SUCCESS: Your account is fully authorized!")
        print("*"*50)
    else:
        print("\n" + "!"*50)
        print("ACTION REQUIRED: PLEASE AUTHORIZE BELOW")
        print("!"*50)
        print("Copy the links below into your browser, log in, and authorize.")
        print("Note: You only need to authorize ONE of these links if they use the same account.")
        
        for name, link in auth_links:
            print(f"\n[{name.upper()}]:")
            print(link)
            
    print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
