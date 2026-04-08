"""
tools/utils.py
generic tools used by multi-agent system.
"""

from google.adk.tools.function_tool import ToolContext
from datetime import datetime
from zoneinfo import ZoneInfo

def get_current_time(tool_context: ToolContext) -> dict:
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M:%S")

    # Write into state so the agent can see it later
    state = tool_context.state
    state["current_date_india"] = current_date
    state["current_time_india"] = current_time
    state["timezone"] = "Asia/Kolkata (IST)"

    return {
        "current_date": current_date,
        "current_time": current_time,
        "timezone": "Asia/Kolkata (IST)",
    }
