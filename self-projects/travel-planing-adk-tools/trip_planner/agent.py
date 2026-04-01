from google.adk.agents.llm_agent import Agent
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool

google_search_analyzer = Agent(
    model       ='gemini-2.5-flash',
    name        ='google_search_analyzer',
    description ='A search analyzer that uses google search to find latest informaition about current events, weather, or business hours.',
    instruction ="""
    Use google search to answer user questions about real-time, logistical information.
    ALWAYS end every response with a "Sources" section with title and text of corresponding metadata in this exact format:
    **Sources:**
    - ["title"]: ["uri"]
    - ["title"]: ["uri"]

    Never omit the Sources section. Never summarize without citing where the data came from.
    """,
    tools       =[google_search],
 )

root_agent = Agent(
    model='gemini-2.5-flash',
    name='root_agent',
    description='A helpful assistant for user questions.',
    instruction="""When you use the google_search_analyzer, you must include the 
    'Sources' section exactly as provided by the tool in your final response.
    """,
    tools       =[AgentTool(agent=google_search_analyzer)],
)
