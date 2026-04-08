"""
agents/orchestrator_agent.py
LLM-powered planner / coordinator.
This is the root of the agent hierarchy.
"""
from __future__ import annotations
from google.adk.agents import LlmAgent
from schemas.input_schemas import TrainQuery


orchestrator_agent = LlmAgent(
    name="orchestrator",
    model="gemini-2.5-flash",
    description="Main AI planner for the smart travel journey assistant system.",
    instruction="""
You are the lead Train Recommendation AI.
Receiving a valid TrainQuery. 
""",
    input_schema=TrainQuery,

)