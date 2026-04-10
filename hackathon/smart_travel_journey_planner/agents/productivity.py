"""
Productivity agent — uses workspace-mcp in External OAuth Provider mode.

Architecture
------------
workspace-mcp now runs as a persistent HTTP server (--transport streamable-http)
with EXTERNAL_OAUTH21_PROVIDER=true.  Our FastAPI app already handles OAuth via
/login → /auth/callback and stores the user's access_token in their session.

For every productivity request we:
  1. Pass the user's access_token as  "Authorization: Bearer <token>"  via
     an ADK header_provider callback injected into McpToolset.
  2. workspace-mcp validates the token against Google and routes all API calls
     to that user's account — genuine multi-user isolation.

No --single-user, no per-user subprocess hacks, no credential file sharing.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
import time
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StdioConnectionParams,
    StreamableHTTPConnectionParams,
)
from google.adk.agents.readonly_context import ReadonlyContext
from mcp import StdioServerParameters

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WORKSPACE_MCP_URL     = os.getenv("WORKSPACE_MCP_URL", "").strip()
WORKSPACE_MCP_COMMAND = os.getenv("WORKSPACE_MCP_COMMAND", "workspace-mcp")
WORKSPACE_MCP_HTTP_PORT = int(os.getenv("WORKSPACE_MCP_HTTP_PORT", "8765"))

_raw_args = os.getenv("WORKSPACE_MCP_ARGS", "--tool-tier extended")
# Strip any legacy flags that workspace-mcp no longer accepts
for _bad in ("--single-user", "--multi-user"):
    _raw_args = _raw_args.replace(_bad, "")
WORKSPACE_MCP_ARGS = _raw_args.split()


# ---------------------------------------------------------------------------
# Binary detection (cross-platform)
# ---------------------------------------------------------------------------

def _find_mcp_executable() -> str:
    """Return the path to the workspace-mcp binary, or the command fallback."""
    base = os.path.dirname(os.path.dirname(__file__))
    candidates = [
        os.path.join(base, "venv", "Scripts", "workspace-mcp.exe"),  # Windows venv
        os.path.join(base, "venv", "bin",     "workspace-mcp"),       # Linux venv
        "/usr/local/bin/workspace-mcp",                                # Docker pip install
        "/app/venv/bin/workspace-mcp",                                 # Docker /app workdir
    ]
    for path in candidates:
        if os.path.exists(path):
            logger.info("workspace-mcp binary: %s", path)
            return path
    logger.info("workspace-mcp not found in known paths — using: %s", WORKSPACE_MCP_COMMAND)
    return WORKSPACE_MCP_COMMAND


MCP_EXECUTABLE = _find_mcp_executable()


# ---------------------------------------------------------------------------
# HTTP server management
# Workspace-mcp is launched once as a long-running HTTP server; all users
# share the same process but are isolated via their Bearer access_token.
# ---------------------------------------------------------------------------

_mcp_http_proc: Optional[subprocess.Popen] = None
_mcp_http_url:  str = ""


def _ensure_mcp_http_server() -> str:
    """
    Ensure workspace-mcp is running as an HTTP server.
    Returns the base URL (e.g. http://127.0.0.1:8765).
    Idempotent — safe to call on every request.
    """
    global _mcp_http_proc, _mcp_http_url

    # Re-use existing process if still alive
    if _mcp_http_proc is not None and _mcp_http_proc.poll() is None:
        return _mcp_http_url

    port = WORKSPACE_MCP_HTTP_PORT
    url  = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env["EXTERNAL_OAUTH21_PROVIDER"] = "true"   # ← key flag: skip internal OAuth
    env["PORT"]                       = str(port)

    cmd = [
        MCP_EXECUTABLE,
        "--transport", "streamable-http",
    ] + WORKSPACE_MCP_ARGS

    logger.info("Starting workspace-mcp HTTP server: %s", " ".join(cmd))
    try:
        _mcp_http_proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        # Give it a moment to bind the port
        time.sleep(1.5)
        if _mcp_http_proc.poll() is not None:
            err = (_mcp_http_proc.stderr.read() or b"").decode()
            raise RuntimeError(f"workspace-mcp exited immediately: {err[:400]}")
        _mcp_http_url = url
        logger.info("workspace-mcp HTTP server ready at %s", url)
        return url
    except Exception as exc:
        logger.error("Failed to start workspace-mcp HTTP server: %s", exc)
        _mcp_http_proc = None
        raise


# ---------------------------------------------------------------------------
# Patched toolset (schema fixes for Vertex AI compatibility)
# ---------------------------------------------------------------------------

class PatchedMcpToolset(McpToolset):
    """
    Wraps McpToolset and repairs common workspace-mcp schema issues that cause
    Vertex AI 400 INVALID_ARGUMENT errors.

    Fixes applied per-tool on first get_tools() call:
      • attendees: missing 'items' → inject  {"type": "string"}
      • any other array-typed param missing 'items' → same fix
    """

    async def get_tools(self, readonly_context=None):
        tools = await super().get_tools(readonly_context)
        for tool in tools:
            schema = getattr(tool, "_tool_schema", None) or {}
            params = (
                schema.get("parameters", {})
                      .get("properties", {})
            )
            for pname, pdef in (params or {}).items():
                if pdef.get("type") == "array" and "items" not in pdef:
                    pdef["items"] = {"type": "string"}
                    logger.debug(
                        "Patched schema for tool=%s param=%s",
                        getattr(tool, "name", "?"), pname,
                    )
        return tools


# ---------------------------------------------------------------------------
# Connection factory
# ---------------------------------------------------------------------------

def _make_connection_params(access_token: str) -> StreamableHTTPConnectionParams:
    """
    Build StreamableHTTPConnectionParams that injects the user's Bearer token
    so workspace-mcp routes the request to the correct Google account.
    """
    if WORKSPACE_MCP_URL:
        # Explicit override (e.g. Cloud Run sidecar or remote instance)
        base_url = WORKSPACE_MCP_URL.rstrip("/")
    else:
        base_url = _ensure_mcp_http_server()

    mcp_endpoint = f"{base_url}/mcp"

    def _header_provider(ctx: ReadonlyContext) -> Dict[str, str]:
        return {"Authorization": f"Bearer {access_token}"}

    return StreamableHTTPConnectionParams(
        url=mcp_endpoint,
        timeout=60.0,
        headers={"Authorization": f"Bearer {access_token}"},
    )


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

def get_productivity_agent(user_email: str = "", access_token: str = "") -> LlmAgent:
    """
    Builds a fresh LlmAgent scoped to the authenticated user.

    Parameters
    ----------
    user_email:
        The signed-in user's Google email address (used in the agent prompt).
    access_token:
        The user's OAuth access_token (used as Bearer header to workspace-mcp).
        Falls back to stdio / single-user mode when empty.
    """
    if not user_email:
        user_email = os.getenv("USER_GOOGLE_EMAIL", "")
    if not user_email:
        user_email = "me"

    _instruction = f"""
You are a productivity assistant for a train travel booking system.

You will receive a JSON object describing a confirmed train recommendation.
Your job is to execute exactly THREE actions using your tools — no more, no less.

The user's Google account email is: {user_email}
Use this email as user_google_email in every tool call.

============================================================
STEP 1 — Google Tasks (manage_task)
============================================================
Create a reminder task with these exact parameters:

    action            = "create"
    user_google_email = "{user_email}"
    task_list_id      = "@default"

    title = "Book cab to <source> station"

    due = RFC3339 timestamp computed as:
        Logic: travel_date + departure_time minus 2 hours
        Timestamp Format: YYYY-MM-DDTHH:MM:SSZ
        Example:
            travel_date="2026-04-17"
            departure_time="06:45"
            → due="2026-04-17T04:45:00Z"

    notes = "Train Live: https://www.makemytrip.com/railways/railStatus/?q1=<train_id>&q3=<YYYY-MM-DD>"

============================================================
STEP 2 — Google Calendar (manage_event)
============================================================
Create a calendar event with these exact parameters:

    action              = "create"
    user_google_email   = "{user_email}"
    calendar_id         = "primary"

    summary             = "<train_id> | <train_name> | <source> → <destination>"

    start_time          = "<date>T<departure_time>:00" (RFC3339 Format: YYYY-MM-DDTHH:MM:SSZ)

    end_time            = "<date>T<arrival_time>:00" (RFC3339 Format: YYYY-MM-DDTHH:MM:SSZ) (add 1 day if arrival < departure)

    description         = "Train Journey

                        📍 Route: <source> → <destination>
                        🚂 Train: <train_name> (<train_id>)
                        📅 Date: <travel_date>
                        ⏰ Departure: <departure_time>  |  Arrival: <arrival_time>

                        🔴 Live Status: https://www.makemytrip.com/railways/railStatus/?q1=<train_id>&q3=<YYYY-MM-DD>
                        🍽 Order Food: https://www.railrestro.com/trains/<train_name with + instead of space>?DOJ=<DDMMYYYY format of travel date>

                        ✅ Booked via Smart Travel Journey Planner
                        "

    location            = "<source> Railway Station"

============================================================
STEP 3 — Gmail Draft (draft_gmail_message)
============================================================
Create a Gmail draft with these exact parameters:

    user_google_email = "{user_email}"
    to                = "[EMAIL_ADDRESS]"
    subject           = "Travelling on <human-readable-date> – <source> to <destination>"
                        Example:
                        "Travelling on 17 April 2026 – Delhi to Mumbai"

    body              = "Hi,

                        I'll be travelling on <human-readable-date> and may have limited availability during this time.

                        Train: <train_name> (<train_id>)
                        Route: <source> → <destination>
                        Departure: <departure_time>
          Arrival: <arrival_time>

          I'll respond once I'm reachable.

Thanks.
"

============================================================
RULES
============================================================

1. Execute ALL THREE steps even if one fails.
2. Do NOT skip any step.
3. Do NOT write Python. Do NOT explain — just call the tools.
4. After all three calls complete, write a brief summary of what was done
   (including any errors encountered).
"""

    # Determine connection: HTTP with Bearer token (multi-user) or stdio fallback
    if access_token:
        try:
            connection_params = _make_connection_params(access_token)
            logger.info("Productivity agent using HTTP Bearer token for %s", user_email)
        except Exception as exc:
            logger.warning(
                "Failed to start workspace-mcp HTTP server (%s), falling back to stdio", exc
            )
            connection_params = _make_stdio_params()
    else:
        # Fallback: stdio + --single-user (for dev/test with no session token)
        logger.warning(
            "No access_token for %s — using stdio single-user fallback", user_email
        )
        connection_params = _make_stdio_params()

    return LlmAgent(
        name="productivity_agent",
        model="gemini-2.5-flash",
        description=(
            "Creates a Google Task, Calendar event, and drafts a Gmail reminder "
            "for a confirmed train booking."
        ),
        instruction=_instruction,
        tools=[PatchedMcpToolset(connection_params=connection_params)],
    )


def _make_stdio_params() -> StdioConnectionParams:
    """Fallback: stdio + --single-user for local dev without access_token."""
    env = os.environ.copy()
    args = ["--single-user"] + [a for a in WORKSPACE_MCP_ARGS if a != "--single-user"]
    return StdioConnectionParams(
        server_params=StdioServerParameters(
            command=MCP_EXECUTABLE,
            args=args,
            env=env,
        ),
        timeout=90.0,
    )


# ---------------------------------------------------------------------------
# Module-level fallback instance — for ADK web / adk run / orchestrator
# ---------------------------------------------------------------------------
productivity_agent = get_productivity_agent()
