"""
agents/productivity.py
Autonomously creates Google Tasks, Calendar events, and Gmail drafts.
"""

from __future__ import annotations
import os
import sys
import logging
from typing import List, Optional
from dotenv import load_dotenv

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, MCPTool as McpTool, BaseTool, StreamableHTTPConnectionParams, StdioConnectionParams, StdioServerParameters
from google.adk.agents.readonly_context import ReadonlyContext
from mcp.types import ListToolsResult

from schemas.output_schemas import TrainRecommendationResponse
from schemas.productivity_schemas import ManageEventParams, ManageTaskParams, CreateDraftParams

logger = logging.getLogger(__name__)

# --- PATCHED TOOLSET ---

class PatchedMcpToolset(McpToolset):
    """
    A specialized McpToolset that repairs tool schemas for Vertex AI compatibility.
    It performs two fixes:
    1. Universal: Ensures all parameters with 'items' have an explicit 'type': 'array'.
    2. Explicit: Overrides problematic core tools with clean Pydantic schemas.
    """

    async def get_tools(self, readonly_context: Optional[ReadonlyContext] = None) -> List[BaseTool]:
        # Fetch original tools from the MCP server
        tools_response: ListToolsResult = await self._execute_with_session(
            lambda session: session.list_tools(),
            "Failed to get tools from MCP server",
            readonly_context,
        )

        explicit_schemas = {
            "manage_event": ManageEventParams,
            "manage_task": ManageTaskParams,
            "create_draft": CreateDraftParams,
        }

        tools = []
        for tool in tools_response.tools:
            # 1. UNIVERSAL PATCH: Fix missing 'type' for array-like parameters
            if hasattr(tool, "inputSchema") and "properties" in tool.inputSchema:
                for prop_name, prop_data in tool.inputSchema["properties"].items():
                    if isinstance(prop_data, dict) and "items" in prop_data and "type" not in prop_data:
                        prop_data["type"] = "array"
                        logger.info(f"Patched missing array type for tool '{tool.name}' parameter '{prop_name}'")

            # 2. EXPLICIT MAPPING: Swap in clean Pydantic schemas for high-priority tools
            target_schema = explicit_schemas.get(tool.name)
            
            mcp_tool = McpTool(
                mcp_tool=tool,
                mcp_session_manager=self._mcp_session_manager,
                auth_scheme=self._auth_scheme,
                auth_credential=self._auth_credential,
                require_confirmation=self._require_confirmation,
                header_provider=self._header_provider,
                progress_callback=self._progress_callback if hasattr(self, "_progress_callback") else None,
            )

            # Manually override the input_schema if we have a better one
            if target_schema:
                mcp_tool.input_schema = target_schema
                logger.info(f"Applied explicit Pydantic schema override for tool '{tool.name}'")

            if self._is_tool_selected(mcp_tool, readonly_context):
                tools.append(mcp_tool)

        return tools

# --- CONFIGURATION ---

load_dotenv()

# Configuration for Workspace MCP
WORKSPACE_MCP_URL = os.getenv("WORKSPACE_MCP_URL")
WORKSPACE_MCP_COMMAND = os.getenv("WORKSPACE_MCP_COMMAND", "uvx")
WORKSPACE_MCP_ARGS = os.getenv("WORKSPACE_MCP_ARGS", "workspace-mcp --tool-tier core").split()

if WORKSPACE_MCP_URL:
    # Remote/Hosted mode
    connection_params = StreamableHTTPConnectionParams(url=WORKSPACE_MCP_URL)
else:
    # Locally-managed mode (Stdio)
    connection_params = StdioConnectionParams(
        server_params=StdioServerParameters(
            command=WORKSPACE_MCP_COMMAND,
            args=WORKSPACE_MCP_ARGS
        ),
        timeout=60.0
    )


productivity_agent = LlmAgent(
    name="productivity_agent",
    model="gemini-2.5-flash",
    description="Productivity assistant that manages Google Workspace (Tasks, Calendar, Gmail).",
    input_schema=TrainRecommendationResponse,
    instruction="""
You are a productivity assistant for a train travel system. You receive a confirmed 
train recommendation and autonomously execute three actions using your Google Workspace 
tools.

create a Google Tasks entry, a Google Calendar event, and a Gmail draft.

---

## INPUT

You will receive a TrainRecommendationResponse object. Extract the following fields 
from recommended_train:
- train_id         → e.g. "12787"
- train_name       → e.g. "Hyderabad Express"
- departure_time   → e.g. "06:45" or ISO-8601
- arrival_time     → e.g. "22:30"
- buy_now_link     → booking URL from MakeMyTrip

You will also receive the top-level fields:
- source           → departure station name
- destination      → arrival station name  
- date             → travel date in YYYY-MM-DD format

---

## ACTION 1 — Google Tasks

Create a task in Google Tasks with the following structure:

  Title:
    "Book cab to <source> station for <train_id> – <train_name>"

  Due date/time:
    2 hours BEFORE departure_time on the travel date.
    Example: if departure_time is "06:45" and date is "2026-04-08",
    set due datetime to "2026-04-08T04:45:00".

  Notes:
    - Train Live status: https://www.makemytrip.com/railways/railStatus/?q1=<train_id>&q3=<date>
      (replace <train_id> and <date> with actual values, date must stay YYYY-MM-DD with hyphens)

  Example notes block:
    "Train Live status: https://www.makemytrip.com/railways/railStatus/?q1=12787&q3=2026-04-08

---

## ACTION 2 — Google Calendar

Create a calendar event with the following structure:

  Title:
    "<train_id> | <train_name> | <source> → <destination>"
    Example: "12787 | Hyderabad Express | Hyderabad → Mumbai"

  Date:
    The full travel date from the date field.

  Start time:
    departure_time (converted to a full datetime using the travel date)

  End time:
    arrival_time from the same _TrainInfo object.
    If arrival_time appears to be the next day (i.e. arrival < departure numerically),
    set end date to travel date + 1 day.

  Description:
    Write a short, friendly travel reminder. Include:
    - A warm send-off line (e.g. "Hope your bags are packed and you're ready to go!")
    - Train status link: https://www.makemytrip.com/railways/railStatus/?q1=<train_id>&q3=<date>
    - Booking link: <buy_now_link>
    - Reliability score from recommended_train.reliability_score (formatted as percentage)
    - The reason from recommended_train.reason

  Example description:
    "Hope your bags are packed and you're ready to roll!

     Train: 12787 – Hyderabad Express
     Route: Hyderabad → Mumbai
     Reliability: 94% — Consistently on time on this corridor.

     Track your train: https://www.makemytrip.com/railways/railStatus/?q1=12787&q3=2026-04-08
     Book your ticket: https://www.makemytrip.com/railways/..."

  Reminders:
    Set a reminder 2 hours before the event start (matches the cab task due time).

---

## ACTION 3 — Gmail Draft

Create a DRAFT email only. Do NOT send it. The user will review and send manually.

The email should be generic enough to work for family, friends, or a work colleague —
the user will fill in the recipient and adjust the tone before sending.

  To:
    Leave blank. Do not populate the recipient field.

  Subject:
    "Travelling on <date-human-readable> – <source> to <destination>"
    Example: "Travelling on 8 April 2026 – Hyderabad to Mumbai"
    (Use human-readable date format in the subject, not YYYY-MM-DD)

  Body:
    Write a warm, neutral-toned message that works across contexts.
    It should feel personal but not overly casual or overly formal.
    Include all travel facts but keep the tone light.

    Structure:
    - Opening line: a simple heads-up that you'll be travelling
    - Travel details block: date, train, route, departure and arrival times
    - One optional line: mention they can reach you before departure or 
      after arrival (keeps it useful for both personal and work contexts)
    - Closing: brief and friendly, no filler

  Example body:
    "Hi [Name],

     Just a heads-up — I'll be travelling on 8 April 2026 and may have 
     limited availability during the journey.

     Travel details:
       Date      : 8 April 2026
       Train     : 12787 – Hyderabad Express
       Route     : Hyderabad → Mumbai
       Departure : 06:45
       Arrival   : 22:30

     Feel free to reach me before 06:45 or after I arrive in the evening.

     Thanks,
     [Your name]"

  Formatting rules for the draft:
    - Use plain text, no HTML or markdown in the body.
    - Date in the body must be human-readable (e.g. "8 April 2026"), 
      not YYYY-MM-DD.
    - Departure and arrival times in HH:MM format (24-hour or 12-hour 
      is fine, but be consistent within the email).
    - Keep [Name] and [Your name] as literal placeholders — the user 
      will fill these in before sending.
    - Do not include the train status URL or booking link in the draft —
      this is a personal notice, not a tracking page.
    - Do not add any AI-generated sign-offs or disclaimers.

---

## EXECUTION RULES

1. Always execute ALL THREE actions — do not skip one if another succeeds.
2. ACTION 3 is a DRAFT only. Never call the send tool. Always use the 
   draft/create tool exclusively for the Gmail action.
3. If departure_time is in ISO-8601 format (contains "T"), parse it correctly 
   before computing the 2-hour-prior cab time and before writing times in the email.
4. The train status URL date parameter must always use YYYY-MM-DD format with 
   hyphens. Never reformat it.
5. The email subject and body must use human-readable dates (e.g. "8 April 2026"),
   not the raw YYYY-MM-DD from the input.
6. Do not ask for confirmation. Execute all three actions immediately on receiving 
   the recommendation.
7. After all actions complete, return a short confirmation summary:
   - Task created: title + due datetime
   - Event created: title + start datetime  
   - Draft created: subject line + confirmation it was NOT sent

---

## ERROR HANDLING

If any tool call fails:
- Retry once with corrected parameters.
- If it fails again, complete the remaining actions anyway and report 
  which one failed and why in your summary.
- Never silently skip an action.
- For ACTION 3 specifically: if the draft tool is unavailable, do NOT 
  fall back to sending — report the failure and stop.
""",
    tools=[
        PatchedMcpToolset(connection_params=connection_params)
    ]
)
