import os
import dotenv
from pathlib import Path
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams 

MAPS_MCP_URL = "https://mapstools.googleapis.com/mcp" 

def get_gmap_tools():
    dotenv.load_dotenv(Path(__file__).parent.parent / ".env")
    maps_api_key = os.getenv('MAPS_API_KEY', 'no_api_found')
    
    tools = MCPToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=MAPS_MCP_URL,
            headers={
                "X-Goog-Api-Key": maps_api_key
            },
            timeout=30.0,          
            sse_read_timeout=300.0
        )
    )
    print("MCP Toolset configured for Streamable HTTP connection.")
    return tools