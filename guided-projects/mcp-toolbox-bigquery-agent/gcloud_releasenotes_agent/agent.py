from google.adk.agents.llm_agent import Agent
from toolbox_core import ToolboxSyncClient

bq_toolbox  = ToolboxSyncClient("http://127.0.0.1:5000")
bq_tools    = bq_toolbox.load_toolset('my_bq_toolset')

root_agent = Agent(
    model='gemini-2.5-flash',
    name='root_agent',
    description='A helpful assistant for user questions.',
    instruction='Answer user questions to the best of your knowledge',
    tools=bq_tools,
)
