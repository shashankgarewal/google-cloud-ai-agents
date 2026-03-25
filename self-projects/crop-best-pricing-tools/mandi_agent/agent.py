from google.adk.agents.llm_agent import Agent
from .function_tools import get_mandi_prices, estimate_transport_cost
from google.adk.tools import FunctionTool

root_agent = Agent(
    model='gemini-2.5-flash',
    name='root_agent',
    description='You are an agricultural assistant who help farmer find best price and general farming guidance',
    instruction="""
    Your job:
    - Help farmers find the best market (mandi) to sell crops
    - Always use the get_mandi_prices tool when crop price is needed
    Be concise and practical.
    """,
    tools=[FunctionTool(get_mandi_prices), 
           FunctionTool(estimate_transport_cost)],
)
