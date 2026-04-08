"""
agents/base.py

Shared utility: run an ADK LlmAgent with a single user message and
return the final text response.  All agents use this helper.
"""
from __future__ import annotations

import logging
import ssl
from typing import Any, Optional, List

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
from google.adk.tools.mcp_tool.mcp_toolset import (
    McpToolset,
    MCPTool as McpTool,
    BaseTool,
)
from google.adk.agents.readonly_context import ReadonlyContext
from mcp.types import ListToolsResult
import tenacity

logger = logging.getLogger(__name__)

_APP_NAME = "smart_train_recommender"


# ---------------------------------------------------------------------------
# Schema patcher — fixes Vertex AI incompatibilities in MCP tool schemas
# ---------------------------------------------------------------------------

class PatchedMcpToolset(McpToolset):
    """
    Repairs tool schemas returned by MCP servers for Vertex AI compatibility:
    - Ensures every parameter has a 'type'
    - Strips 'anyOf' (not supported by Vertex) and replaces with a plain type
    - Recursively fixes nested properties/items
    """

    def __init__(self, *args, allowed_tools: Optional[set[str]] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.allowed_tools = allowed_tools

    async def get_tools(
        self, readonly_context: Optional[ReadonlyContext] = None
    ) -> List[BaseTool]:
        tools_response: ListToolsResult = await self._execute_with_session(
            lambda session: session.list_tools(),
            "Failed to get tools from MCP server",
            readonly_context,
        )

        def fix_schema(schema: dict):
            if not isinstance(schema, dict):
                return

            # Vertex AI does not support 'anyOf' or 'oneOf'.
            # If present, we pick the most complex type (object/array) or the first non-null type.
            if "anyOf" in schema or "oneOf" in schema:
                key = "anyOf" if "anyOf" in schema else "oneOf"
                choices = [
                    c for c in schema[key]
                    if isinstance(c, dict) and c.get("type") not in (None, "null")
                ]
                if choices:
                    # Heuristic: favor structured types (array, object) over primitives
                    best = next(
                        (c for c in choices if c.get("type") in ("array", "object")),
                        choices[0]
                    )
                    schema.update(best.copy())
                schema.pop(key, None)

            # Vertex AI requires 'type' at every level
            if "type" not in schema:
                if "properties" in schema:
                    schema["type"] = "object"
                elif "items" in schema:
                    schema["type"] = "array"
                else:
                    schema["type"] = "string"

            # Vertex AI requires 'items' for many array types
            if schema.get("type") == "array" and "items" not in schema:
                schema["items"] = {"type": "string"}

            # Recurse into object properties
            if schema.get("type") == "object" and "properties" in schema:
                for v in schema["properties"].values():
                    fix_schema(v)

            # Recurse into array items
            if schema.get("type") == "array" and "items" in schema:
                fix_schema(schema["items"])

        tools = []
        for tool in tools_response.tools:
            # If allowed_tools is set, filter by name
            if self.allowed_tools and tool.name not in self.allowed_tools:
                continue

            if hasattr(tool, "inputSchema") and isinstance(tool.inputSchema, dict):
                fix_schema(tool.inputSchema)

            mcp_tool = McpTool(
                mcp_tool=tool,
                mcp_session_manager=self._mcp_session_manager,
                auth_scheme=self._auth_scheme,
                auth_credential=self._auth_credential,
                require_confirmation=self._require_confirmation,
                header_provider=self._header_provider,
                progress_callback=(
                    self._progress_callback
                    if hasattr(self, "_progress_callback")
                    else None
                ),
            )

            if self._is_tool_selected(mcp_tool, readonly_context):
                tools.append(mcp_tool)

        return tools


def _extract_text(event) -> Optional[str]:
    """Safely pull text from an ADK event, ignoring function_call / tool parts."""
    if not (event.content and event.content.parts):
        return None
    texts = [
        part.text
        for part in event.content.parts
        if hasattr(part, "text") and part.text
    ]
    return " ".join(texts).strip() or None


def _is_transient_error(exc: BaseException) -> bool:
    """
    Returns True for transient network / SSL / quota errors worth retrying:
    - 429 / RESOURCE_EXHAUSTED (rate limit)
    - SSL EOF (unexpected close of TLS connection)
    - Connection aborted / remote disconnected
    - TCP reset / broken pipe
    """
    err_str = str(exc).lower()
    transient_markers = (
        "429",
        "resource_exhausted",
        "eof occurred",
        "unexpected_eof",
        "connection aborted",
        "remote end closed",
        "remotedisconnected",
        "connection reset",
        "broken pipe",
        "socket.timeout",
        "ssl",
    )
    if any(m in err_str for m in transient_markers):
        return True
    if isinstance(
        exc,
        (
            ssl.SSLError,
            ConnectionError,
            ConnectionAbortedError,
            ConnectionResetError,
            BrokenPipeError,
            OSError,
        ),
    ):
        return True
    # httpx-level errors (optional dependency)
    try:
        import httpx
        if isinstance(exc, (httpx.ConnectError, httpx.RemoteProtocolError, httpx.NetworkError)):
            return True
    except ImportError:
        pass
    return False


@tenacity.retry(
    wait=tenacity.wait_exponential(multiplier=1, min=3, max=20),
    stop=tenacity.stop_after_attempt(3),
    retry=tenacity.retry_if_exception(_is_transient_error),
    before_sleep=lambda retry_state: logger.warning(
        "Transient error on attempt %d — retrying: %s",
        retry_state.attempt_number,
        retry_state.outcome.exception(),
    ),
)
async def run_agent_turn(
    agent: Any,
    message: Any,
    user_id: str = "default",
    initial_state: Optional[dict] = None,
) -> str:
    """
    Create a fresh in-memory session, send *message* to *agent*, and
    return the agent's final text reply.

    Parameters
    ----------
    agent:
        An ADK Agent instance (LlmAgent, etc.).
    message:
        The user-turn text to send, or a Pydantic model (serialized to JSON).
    user_id:
        Logical user identifier (used by the session service).
    initial_state:
        Optional dict of session state variables to pre-populate before the
        agent runs (e.g. {"user_email": "foo@gmail.com"}).

    Returns
    -------
    str
        The agent's final text response.

    Raises
    ------
    RuntimeError
        If the agent returns no final text response.
    """
    session_service = InMemorySessionService()

    runner = Runner(
        agent=agent,
        app_name=_APP_NAME,
        session_service=session_service,
    )

    session = await session_service.create_session(
        app_name=_APP_NAME,
        user_id=user_id,
        state=initial_state or {},
    )

    # Handle both string messages and Pydantic objects as input
    if isinstance(message, str):
        part = genai_types.Part(text=message)
    else:
        # Pass the Pydantic object's JSON to the agent
        part = genai_types.Part(text=message.model_dump_json())

    user_content = genai_types.Content(
        role="user",
        parts=[part],
    )

    final_text: str | None = None

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=user_content,
    ):
        if event.is_final_response():
            final_text = _extract_text(event)
            if final_text:
                break

    if final_text is None:
        raise RuntimeError(
            f"Agent '{agent.name}' did not produce a final text response."
        )

    logger.debug("Agent '%s' responded: %s", agent.name, final_text[:200])
    return final_text


async def stream_agent_turns(
    agent: Any,
    message: Any,
    user_id: str = "default",
    initial_state: Optional[dict] = None,
):
    """
    Like run_agent_turn but yields every event for SSE streaming.
    Used by the /confirm endpoint to stream productivity agent progress.

    Parameters
    ----------
    agent:
        An ADK Agent instance (LlmAgent, etc.).
    message:
        The user-turn text to send, or a Pydantic model.
    user_id:
        Logical user identifier.
    initial_state:
        Optional dict of session state variables to pre-populate before the
        agent runs (e.g. {"user_email": "foo@gmail.com"}).
    """
    session_service = InMemorySessionService()

    runner = Runner(
        agent=agent,
        app_name=_APP_NAME,
        session_service=session_service,
    )

    session = await session_service.create_session(
        app_name=_APP_NAME,
        user_id=user_id,
        state=initial_state or {},
    )

    if isinstance(message, str):
        part = genai_types.Part(text=message)
    else:
        part = genai_types.Part(text=message.model_dump_json())

    user_content = genai_types.Content(role="user", parts=[part])

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=user_content,
    ):
        # Attach a helper so callers can do event._safe_text without triggering warnings
        event._safe_text = _extract_text(event)
        yield event
