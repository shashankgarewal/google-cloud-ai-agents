"""
agents/orchestrator.py
LLM-powered planner / coordinator.
This is the root of the agent hierarchy.
"""

from google.adk.agents import LlmAgent
from agents.data_fetcher import data_fetching_agent
from agents.recommendor import recommendor_agent
from agents.productivity import productivity_agent

from schemas.input_schemas import TrainQuery

from google.adk.tools import FunctionTool
from tools.utils import get_current_time


orchestrator_agent = LlmAgent(
    name="orchestrator",
    model="gemini-2.5-flash",
    description="Main AI planner for the smart travel journey assistant system.",
    instruction="""
You are the lead Train Recommendation AI.
As soon as user query is received, use 'get_current_time' and save current_date and current_time in state. 

Receiving a TrainQuery:
1. DELEGATE to 'data_fetching_agent' to get raw train options.
   - If travel date is same as current_date: Guide it to fetch LIVE status.
   - If travel date is in the future: Guide it to fetch HISTORICAL delay info using 'Get-train-delay-info'.
   - ALWAYS mandate fetching seat availability.
2. DELEGATE the raw results + user preferences to 'recommendor_agent'.
   - It will rank trains based on availability, reliability, and preferences.
3. DELEGATE the final recommendation to 'productivity_agent' to create Tasks, Calendar events, and Gmail drafts.

Wait for all confirmations and present the final recommendation + productivity summary.

If the user query is for a past date, reject it immediately with a friendly message.
If you don't receive a response in a valid schema from sub-agents, guide the user about valid queries.
""",
    input_schema=TrainQuery,
    sub_agents=[data_fetching_agent, recommendor_agent, productivity_agent],
    tools=[FunctionTool(get_current_time)],
)