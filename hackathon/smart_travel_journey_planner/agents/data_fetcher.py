"""
agents/data_fetcher.py
Data fetcher agent using live MCP tools.
"""

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StreamableHTTPConnectionParams
from schemas.output_schemas import TrainDataResponse
from schemas.input_schemas import TrainQuery

from dotenv import load_dotenv
import os

load_dotenv()
TRAIN_DATA_MCP_URL = os.getenv("TRAIN_DATA_MCP_URL")


data_fetching_agent = LlmAgent(
    name="data_fetching_agent",
    model="gemini-1.5-flash-lite",
    description="Fetches live train schedules and delays from Railway MCP.",
    input_schema=TrainQuery,
    instruction="""
You are an expert at fetching indian railway data. 
1. Use the MCP railway tools to query available trains between the listed source and destination.
2. Gather timing and real-time delay minutes.
3. Return the data structured as a TrainDataResponse.

Do not provide advice or ranking; just fetch and return the data.
""",
    tools=[
        MCPToolset(connection_params=StreamableHTTPConnectionParams(url=TRAIN_DATA_MCP_URL))
    ],
    output_schema=TrainDataResponse
)
