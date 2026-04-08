"""
agents/base.py

Shared utility: run an ADK LlmAgent with a single user message and
return the final text response.  All agents use this helper.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
import tenacity

logger = logging.getLogger(__name__)

_APP_NAME = "smart_train_recommender"


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


@tenacity.retry(
    wait=tenacity.wait_exponential(multiplier=1, min=2, max=10),
    stop=tenacity.stop_after_attempt(5),
    retry=tenacity.retry_if_exception_message(match=".*429.*|.*RESOURCE_EXHAUSTED.*"),
    before_sleep=lambda retry_state: logger.warning(
        f"Rate limited (429). Retrying attempt {retry_state.attempt_number}..."
    ),
)
async def run_agent_turn(agent: Any, message: Any, user_id: str = "default") -> str:
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


async def stream_agent_turns(agent: Any, message: Any, user_id: str = "default"):
    """
    Like run_agent_turn but yields every event for SSE streaming.
    Used by the /confirm endpoint to stream productivity agent progress.
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
        # Attach a helper so callers can do event.safe_text without triggering warnings
        event._safe_text = _extract_text(event)
        yield event
