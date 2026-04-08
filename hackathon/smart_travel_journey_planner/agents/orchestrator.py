"""
agents/orchestrator.py
LLM-powered planner / coordinator.
This is the root of the agent hierarchy.
"""
from __future__ import annotations
from google.adk.agents import LlmAgent
from agents.data_fetcher import data_fetching_agent
from schemas.input_schemas import TrainQuery


orchestrator_agent = LlmAgent(
    name="orchestrator",
    model="gemini-2.5-flash",
    description="Main AI planner for the smart travel journey assistant system.",
    instruction="""
You are the lead Train Recommendation AI.
Receiving a valid TrainQuery. 
1. DELEGATE to 'data_fetching_agent' to get live train options and delays.
2. ANALYZE the results yourself. Compare trains based on timing, reliability (low delay), and user preferences (default: less expected delay and official travel time).
""",
    input_schema=TrainQuery,
    sub_agents=[data_fetching_agent],
)