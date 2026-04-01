import os
import sys
import dotenv
from pathlib import Path
from ..tools import gmap_bigquery as gmap_bigquery_tools
from google.adk.agents import LlmAgent

dotenv.load_dotenv(Path(__file__).parent.parent / ".env")

PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT', 'project_not_set')

maps_toolset = gmap_bigquery_tools.get_maps_mcp_toolset()
bigquery_toolset = gmap_bigquery_tools.get_bigquery_mcp_toolset()

root_agent = LlmAgent(
    model='gemini-3.1-pro-preview',
    name='root_agent',
    instruction=f"""
                Help the user answer questions by strategically combining insights from two sources:
                
                1.  **BigQuery toolset:** Access demographic (inc. foot traffic index), product pricing, and historical sales data in the  mcp_bakery dataset. Do not use any other dataset.
                Run all query jobs from project id: {PROJECT_ID}. 

                2.  **Maps Toolset:** Use this for real-world location analysis, finding competition/places and calculating necessary travel routes.
                    Include a hyperlink to an interactive map in your response where appropriate.
            """,
    tools=[maps_toolset, bigquery_toolset]
)

