from google.adk.agents.llm_agent import Agent
from toolbox_core import ToolboxSyncClient

bq_toolbox  = ToolboxSyncClient("http://127.0.0.1:5000")
bq_tools    = bq_toolbox.load_toolset('my_bq_toolset')

root_agent = Agent(
    model='gemini-2.5-flash',
    name='root_agent',
    description="Agent to answer questions about Google Cloud Release notes.",
    instruction="""
        You are a helpful agent with acces to bq_tools. 
        Your goal is to fully utilize the bq_tools and the answer user's question about Google Cloud Release notes
        """,
    tools=bq_tools,
)
