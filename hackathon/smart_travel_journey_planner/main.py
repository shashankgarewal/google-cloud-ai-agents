"""
main.py — FastAPI app for Smart Travel Journey Planner.

Routes
------
GET  /                         Landing search page (HTML)
POST /query                    Freeform orchestrator chat (JSON)
GET  /recommendations          Train recommendations (JSON API)
POST /recommendations          Train recommendations (JSON API, POST body)
GET  /ui                       Recommendations page (HTML, runs agents)
GET  /ui/insight/{train_id}    HTMX partial: why-recommended insight
POST /confirm                  SSE: confirms booking + runs productivity agent
GET  /check-auth               JSON: confirms workspace-mcp auth status


SINGLE-USER MODE
-----------------
This app uses workspace-mcp in --single-user mode.  Credentials for
USER_GOOGLE_EMAIL are cached on disk by setup_credentials.py.
No per-request OAuth flow is needed — set USER_GOOGLE_EMAIL in .env
and run `python setup_credentials.py` once before starting.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from schemas.output_schemas import TrainRecommendationResponse, _Recommendation
from schemas.input_schemas import TrainQuery, BookingConfirmation

from agents.base import run_agent_turn, stream_agent_turns
from agents.agent import root_agent
from agents.data_fetcher import data_fetching_agent
from agents.recommendor import recommendor_agent
from agents.productivity import get_productivity_agent

load_dotenv(override=True)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Single-user configuration
# ---------------------------------------------------------------------------
# Set USER_GOOGLE_EMAIL in .env.  Before building the Docker image, run:
#   python setup_credentials.py
# This writes credentials/<email>.json which the Dockerfile copies into the image.
USER_GOOGLE_EMAIL = os.getenv("USER_GOOGLE_EMAIL", "")


app = FastAPI(title="Smart Travel Journey Planner")

# Session middleware (kept for session storage of search state)
SECRET_KEY = os.getenv("SECRET_KEY", "hackathon-secret-key-12345")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

templates = Jinja2Templates(directory="templates")

# ---------------------------------------------------------------------------
# Productivity task tracker — only one job runs at a time.
# When a new /ui recommendation query arrives the old task is cancelled.
# ---------------------------------------------------------------------------
_active_productivity_task: Optional[asyncio.Task] = None

# Auth preflight: path where workspace-mcp caches credentials on disk
def _get_creds_dir() -> str:
    custom = os.getenv("WORKSPACE_MCP_CREDENTIALS_DIR") or os.getenv("GOOGLE_MCP_CREDENTIALS_DIR")
    if custom:
        return os.path.expanduser(custom)
    return os.path.join(os.path.expanduser("~"), ".google_workspace_mcp", "credentials")


def _is_workspace_authenticated(email: str) -> bool:
    """True if a credential file with a refresh_token exists for *email*."""
    cred_file = os.path.join(_get_creds_dir(), f"{email}.json")
    if not os.path.exists(cred_file):
        return False
    try:
        with open(cred_file) as f:
            data = json.load(f)
        return bool(data.get("refresh_token"))
    except Exception:
        return False


def _get_configured_user() -> Optional[dict]:
    """
    Returns a user dict for the configured USER_GOOGLE_EMAIL if a valid
    credential file exists on disk.  Returns None if not yet authenticated.
    Used to drive the 'Productivity Unlocked' UI without any browser OAuth.
    """
    if not USER_GOOGLE_EMAIL:
        return None
    if not _is_workspace_authenticated(USER_GOOGLE_EMAIL):
        return None
    name = USER_GOOGLE_EMAIL.split("@")[0].replace(".", " ").title()
    return {"email": USER_GOOGLE_EMAIL, "name": name, "picture": ""}


# ---------------------------------------------------------------------------
# In-memory train cache — populated by generate_recommendations() so that
# /confirm and /ui/insight can look up trains by ID without re-running agents.
# ---------------------------------------------------------------------------
train_cache: dict[str, _Recommendation] = {}


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class RecommendRequest(BaseModel):
    source: str
    destination: str
    date: str
    preference: Optional[str] = None


class QueryRequest(BaseModel):
    query: str


# ---------------------------------------------------------------------------
# Core agent pipeline
# ---------------------------------------------------------------------------

async def generate_recommendations(
    source: str,
    destination: str,
    date: str,
    preference: Optional[str],
) -> TrainRecommendationResponse:
    """
    Runs data_fetcher → recommendor pipeline via run_agent_turn() and
    returns a validated TrainRecommendationResponse.  Falls back to safe
    mock data if either agent fails.
    """
    query = TrainQuery(source=source, destination=destination, date=date, preference=preference)

    # --- Step 1: data_fetching_agent ---
    try:
        raw_data_text = await run_agent_turn(data_fetching_agent, query)
        logger.info("data_fetching_agent responded (%d chars)", len(raw_data_text))
    except Exception as exc:
        logger.warning("data_fetching_agent failed: %s", exc)
        raw_data_text = f"Data fetch failed: {exc}"

    # --- Step 2: recommendor_agent ---
    recommender_prompt = (
        f"Source: {source}\nDestination: {destination}\nDate: {date}\n"
        f"Preference: {preference or 'none'}\n\nRaw train data:\n{raw_data_text}"
    )
    final_rec: TrainRecommendationResponse | None = None
    try:
        rec_text = await run_agent_turn(recommendor_agent, recommender_prompt)
        logger.info("recommendor_agent responded (%d chars)", len(rec_text))

        # The recommendor has output_schema=TrainRecommendationResponse so ADK
        # should return structured JSON — try every JSON object in the response
        # until one validates against TrainRecommendationResponse.
        import re
        json_candidates = re.findall(r"\{.*?\}", rec_text, re.DOTALL)
        # Also try the full greedy match as last resort
        greedy_match = re.search(r"\{.*\}", rec_text, re.DOTALL)
        if greedy_match and greedy_match.group() not in json_candidates:
            json_candidates.append(greedy_match.group())
        for candidate in json_candidates:
            try:
                final_rec = TrainRecommendationResponse.model_validate_json(candidate)
                break  # Found a valid response
            except Exception:
                continue  # Try next candidate
    except Exception as exc:
        logger.warning("recommendor_agent failed or returned invalid JSON: %s", exc)

    # --- Fallback mock data ---
    if final_rec is None:
        logger.warning("Using fallback mock data for %s → %s", source, destination)
        mock_trains = [
            _Recommendation(
                train_id="11007", train_name="Deccan Express",
                departure_time="06:45", arrival_time="09:00",
                reliability_score=0.98, availability="Available",
                reason="Highest punctuality on this corridor over 90 days with zero cancellations. Fastest option — arrives 30 min earlier than alternatives.",
                buy_now_link=f"https://www.makemytrip.com/railways/search/railsTravelerPage?from={source}&to={destination}&departure={date.replace('-','')}&trainNumber=11007&classCode=SL&quota=GN",
            ),
            _Recommendation(
                train_id="12025", train_name="Shatabdi Express",
                departure_time="07:15", arrival_time="09:45",
                reliability_score=0.85, availability="Available",
                reason="Good overall record with occasional 10-15 min weekend delays. Less crowded, more seat availability.",
                buy_now_link=f"https://www.makemytrip.com/railways/search/railsTravelerPage?from={source}&to={destination}&departure={date.replace('-','')}&trainNumber=12025&classCode=SL&quota=GN",
            ),
            _Recommendation(
                train_id="12123", train_name="Pragati Express",
                departure_time="08:00", arrival_time="10:30",
                reliability_score=0.72, availability="Available",
                reason="Higher delay risk with average delays of 20-25 min. Budget option — significantly cheaper fare.",
                buy_now_link=f"https://www.makemytrip.com/railways/search/railsTravelerPage?from={source}&to={destination}&departure={date.replace('-','')}&trainNumber=12123&classCode=SL&quota=GN",
            ),
        ]
        final_rec = TrainRecommendationResponse(
            source=source, destination=destination, date=date,
            recommended_train=mock_trains[0],
            alternatives=mock_trains[1:],
            insights={"summary": "Fallback mock data — agent pipeline unavailable."},
        )

    # Populate train_cache for subsequent /confirm and /ui/insight lookups
    train_cache[final_rec.recommended_train.train_id] = final_rec.recommended_train
    for alt in final_rec.alternatives:
        train_cache[alt.train_id] = alt

    return final_rec


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    user = _get_configured_user()
    return templates.TemplateResponse("search.html", {"request": request, "user": user})



@app.get("/check-auth")
async def check_auth(request: Request):
    """Returns workspace-mcp credential status for the configured user."""
    authenticated = _is_workspace_authenticated(USER_GOOGLE_EMAIL) if USER_GOOGLE_EMAIL else False
    return JSONResponse({
        "authenticated": authenticated,
        "email": USER_GOOGLE_EMAIL,
        "mode": "single-user",
        "message": (
            f"Ready — credentials loaded for {USER_GOOGLE_EMAIL}" if authenticated
            else "Not authenticated — run: python setup_credentials.py"
        )
    })





@app.post("/query")
async def process_query(req: QueryRequest):
    """Freeform orchestrator agent chat."""
    try:
        response = await run_agent_turn(root_agent, req.query)
        return {"response": response}
    except Exception as exc:
        logger.error("Orchestrator error: %s", exc)
        return {"response": f"Agent error: {exc}"}


@app.get("/recommendations")
async def api_get_recommendations(
    source: str, destination: str, date: str,
    preference: Optional[str] = None,
):
    return await generate_recommendations(source, destination, date, preference)


@app.post("/recommendations")
async def api_post_recommendations(req: RecommendRequest):
    return await generate_recommendations(req.source, req.destination, req.date, req.preference)


@app.get("/ui", response_class=HTMLResponse)
async def ui_recommendations(
    request: Request,
    source: str,
    destination: str,
    date: str,
    preference: Optional[str] = None,
):
    global _active_productivity_task

    # Cancel any in-flight productivity agent when user starts a new search
    if _active_productivity_task and not _active_productivity_task.done():
        logger.info("New recommendation query — cancelling previous productivity task")
        _active_productivity_task.cancel()
        try:
            await asyncio.wait_for(_active_productivity_task, timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        _active_productivity_task = None

    user = _get_configured_user()
    rec = await generate_recommendations(source, destination, date, preference)
    return templates.TemplateResponse("recommendations.html", {
        "request": request,
        "user": user,
        "source": source,
        "destination": destination,
        "date": date,
        "preference": preference,
        "recommended": rec.recommended_train,
        "alternatives": rec.alternatives,
    })


@app.get("/ui/insight/{train_id}", response_class=HTMLResponse)
async def insight_partial(request: Request, train_id: str):
    train = train_cache.get(train_id)
    if not train:
        return HTMLResponse("")
    return templates.TemplateResponse("partials/insight.html", {
        "request": request,
        "train": train,
    })


# ---------------------------------------------------------------------------
# SSE: /confirm — book + run productivity agent
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# SSE: /confirm — book + run productivity agent
# ---------------------------------------------------------------------------

# Tool names returned in function_response parts when the MCP tool actually ran.
# ONLY these signal a step is truly complete — no text scanning fallback.
_STEP_TOOL_NAMES = {
    "calendar": "manage_event",
    "gmail":    "draft_gmail_message",
    "tasks":    "manage_task",
}


def _detect_step_from_event(event, completed: dict) -> list[str]:
    """
    Inspect an ADK event and return a list of step names ("calendar", "gmail", "tasks")
     que have just completed in this event.
    """
    found = []
    if not event.content or not event.content.parts:
        return found

    for part in event.content.parts:
        if hasattr(part, "function_response") and part.function_response:
            fn_name = (part.function_response.name or "").lower()
            for step, tool_name in _STEP_TOOL_NAMES.items():
                if not completed[step] and tool_name in fn_name:
                    found.append(step)
    
    return found


async def _run_productivity_agent(
    action_input: TrainRecommendationResponse,
    user_email: str,
    queue: asyncio.Queue,
    access_token: str = "",
    timeout: float = 180.0,
):
    """
    Runs productivity_agent DIRECTLY (bypasses orchestrator) so MCP
    function_response events are visible in the stream.

    Flow: /confirm → productivity_agent → MCP tools (manage_event, manage_task, draft_gmail_message)

    Step detection is dual-mode:
      Primary  : function_response parts in the event stream (tool already ran)
      Fallback : final text response parsed for completion signals

    Edge cases handled:
    - Workspace not authenticated → immediate error for all 3 steps
    - asyncio.CancelledError → marks remaining steps as cancelled
    - Timeout (180s) → marks remaining steps as timed-out
    - Any other exception → marks remaining steps with the error message
    """
    completed = {"calendar": False, "gmail": False, "tasks": False}

    async def _put(step: str, status: str, detail: str):
        await queue.put({"data": json.dumps({"step": step, "status": status, "detail": detail})})

    async def _fail_remaining(detail: str, status: str = "error"):
        for step in ("calendar", "gmail", "tasks"):
            if not completed[step]:
                await _put(step, status, detail)

    # --- Auth preflight ---
    # HTTP Bearer mode: if we have an access_token, workspace-mcp handles auth itself.
    # Stdio fallback mode: check credential file exists.
    if not access_token and not _is_workspace_authenticated(user_email):
        msg = (
            f"Workspace not authenticated for {user_email}. "
            "Please sign in via the 'Sign in to Unlock Productivity' button."
        )
        logger.error(msg)
        await _fail_remaining(msg)
        await queue.put(None)  # sentinel
        return

    train = action_input.recommended_train
    booking = BookingConfirmation(
        intent="booking_confirmed",
        source=action_input.source,
        destination=action_input.destination,
        date=action_input.date,
        train_id=train.train_id,
        train_name=train.train_name,
        departure_time=train.departure_time,
        arrival_time=train.arrival_time,
        reliability_score=train.reliability_score,
        reason=train.reason,
        buy_now_link=train.buy_now_link,
    )

    # Pass booking JSON DIRECTLY to productivity_agent.
    # The agent instruction already explains the 3-step workflow so no
    # orchestrator wrapper is needed — and bypassing it is what makes
    # MCP function_response events visible in the stream.
    message = booking.model_dump_json(indent=2)

    step_details = {
        "calendar": f"Calendar event created for {booking.train_name}",
        "gmail":    "Gmail draft created",
        "tasks":    f"Cab reminder set for {booking.departure_time}",
    }

    logger.info(
        "Running productivity agent directly: %s → %s on %s (train %s)",
        booking.source, booking.destination, booking.date, booking.train_id,
    )

    try:
        async with asyncio.timeout(timeout):
            prod_agent = get_productivity_agent(user_email=user_email, access_token=access_token)
            async for event in stream_agent_turns(prod_agent, message, user_id=user_email):

                # --- Primary detection: function_response parts ---
                new_steps = _detect_step_from_event(event, completed)
                for step in new_steps:
                    completed[step] = True
                    await _put(step, "done", step_details[step])
                    logger.info("Productivity step done (function_response): %s", step)

                # --- Fallback detection: parse the agent's final summary text ---
                if event.is_final_response():
                    final_text = (getattr(event, "_safe_text", None) or "").lower()
                    logger.info(
                        "Productivity agent final response (%d chars): %s",
                        len(final_text), final_text[:400],
                    )
                    # Keywords that indicate a step was attempted/completed in the summary
                    text_signals = {
                        "calendar": ["calendar", "event", "manage_event"],
                        "tasks":    ["task", "reminder", "manage_task", "cab"],
                        "gmail":    ["email", "draft", "gmail", "draft_gmail"],
                    }
                    error_signals = ["error", "fail", "exception", "could not", "unable to"]
                    for step in ("calendar", "gmail", "tasks"):
                        if not completed[step]:
                            keywords_found = any(kw in final_text for kw in text_signals[step])
                            errors_found   = any(s  in final_text for s  in error_signals)
                            if keywords_found and errors_found:
                                await _put(step, "error", "Agent reported an issue — check server logs")
                            else:
                                # Agent ran and produced a summary — assume step completed
                                completed[step] = True
                                await _put(step, "done", step_details[step])
                    break  # final response — stop streaming

                if all(completed.values()):
                    break  # All 3 done early

    except asyncio.CancelledError:
        logger.info("Productivity agent cancelled (new recommendation query)")
        await _fail_remaining("Cancelled — a new recommendation query was started", "cancelled")
        raise  # re-raise so asyncio knows the task is done

    except TimeoutError:
        logger.warning("Productivity agent timed out after %ss", timeout)
        await _fail_remaining(f"Timed out after {int(timeout)}s — workspace-mcp did not respond")

    except Exception as exc:
        err = str(exc)
        logger.error("Productivity agent error: %s", err)
        await _fail_remaining(err)

    finally:
        await queue.put(None)  # always send sentinel so the SSE generator exits


async def _productivity_sse(
    action_input: TrainRecommendationResponse,
    user_email: str,
    access_token: str = "",
):
    """
    Async generator that drives the productivity agent and yields SSE events.
    Stores the running task in _active_productivity_task so it can be cancelled
    if a new recommendation query arrives before this one completes.
    """
    global _active_productivity_task

    # Cancel any previous productivity run
    if _active_productivity_task and not _active_productivity_task.done():
        logger.info("Cancelling previous productivity task")
        _active_productivity_task.cancel()
        try:
            await asyncio.wait_for(_active_productivity_task, timeout=3.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(
        _run_productivity_agent(action_input, user_email, queue, access_token=access_token)
    )
    _active_productivity_task = task

    # Stream events from the queue until the sentinel (None) arrives
    while True:
        try:
            item = await asyncio.wait_for(queue.get(), timeout=200.0)
        except asyncio.TimeoutError:
            # Safety net — should never happen since the agent itself times out at 180s
            yield {"data": json.dumps({"step": "calendar", "status": "error",
                                       "detail": "SSE stream timeout"})}
            break

        if item is None:  # sentinel — agent finished
            break
        yield item

    # Ensure task is cleaned up if client disconnects early
    if not task.done():
        task.cancel()


@app.post("/confirm")
async def confirm_booking(request: Request):
    """
    SSE endpoint — confirms a train and triggers the productivity agent.
    Single-user mode: always uses USER_GOOGLE_EMAIL from env.
    No session auth check needed — credentials are pre-baked in the image.
    """
    user_email = USER_GOOGLE_EMAIL
    if not user_email:
        async def _no_creds():
            for step in ("calendar", "gmail", "tasks"):
                yield {"data": json.dumps({"step": step, "status": "error",
                                           "detail": "USER_GOOGLE_EMAIL not set. Run setup_credentials.py first."})}
        return EventSourceResponse(_no_creds())

    if not _is_workspace_authenticated(user_email):
        async def _not_auth():
            for step in ("calendar", "gmail", "tasks"):
                yield {"data": json.dumps({"step": step, "status": "error",
                                           "detail": "No credentials found. Run: python setup_credentials.py"})}
        return EventSourceResponse(_not_auth())

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        train_id    = body.get("train_id")
        source      = body.get("source", "")
        destination = body.get("destination", "")
        date        = body.get("date", "")
    else:
        form        = await request.form()
        train_id    = form.get("train_id")
        source      = form.get("source", "")
        destination = form.get("destination", "")
        date        = form.get("date", "")

    if not train_id:
        raise HTTPException(status_code=422, detail="Missing train_id")

    train = train_cache.get(train_id)
    if not train:
        raise HTTPException(status_code=422, detail=f"train_id '{train_id}' not in recent recommendations")

    action_input = TrainRecommendationResponse(
        source=source or "Unknown",
        destination=destination or "Unknown",
        date=date or "2026-04-08",
        recommended_train=train,
        alternatives=[],
        insights={},
    )
    return EventSourceResponse(_productivity_sse(action_input, user_email))


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    is_cloud  = "PORT" in os.environ
    host      = "0.0.0.0" if is_cloud else "127.0.0.1"
    port      = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,   # Disabled: reload kills active agent SSL connections on Windows
        # Use watchfiles (thread-based) not the default multiprocessing reloader.
        # This prevents CancelledError when GCP credential fetch runs in a
        # spawned subprocess that has no event loop.
        reload_delay=0.5,
        workers=1,
    )
