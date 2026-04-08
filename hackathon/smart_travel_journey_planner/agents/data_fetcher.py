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
    model="gemini-2.5-flash",
    description="Fetches live train schedules and delays from Railway MCP.",
    input_schema=TrainQuery,
    instruction="""
You are an expert at fetching indian railway data. 
1. Use 'Search-trains' to find trains between the listed source and destination for the specific date.
2. For each train found:
   - If travel date is TODAY: Use 'Get-train-live-status' to get current delay minutes.
   - If travel date is NOT today: Use 'Get-train-delay-info' to get historical delay patterns and average delay.
   - Fetch seat availability: Use 'Get-seat-availability' for the train number and date.
3. Return the data structured as a TrainDataResponse, ensuring the 'availability' field is populated for every train.

Do not provide advice or ranking; just fetch and return the structured data.
""",
    tools=[
        MCPToolset(connection_params=StreamableHTTPConnectionParams(url=TRAIN_DATA_MCP_URL))
    ],
    output_schema=TrainDataResponse
)
