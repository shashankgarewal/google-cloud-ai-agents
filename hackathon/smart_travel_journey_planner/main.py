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
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from schemas.output_schemas import TrainRecommendationResponse, _Recommendation
from schemas.input_schemas import TrainQuery

from agents.base import run_agent_turn, stream_agent_turns
from agents.agent import root_agent
from agents.data_fetcher import data_fetching_agent
from agents.recommendor import recommendor_agent
from agents.productivity import productivity_agent

logger = logging.getLogger(__name__)

app = FastAPI(title="Smart Travel Journey Planner")
templates = Jinja2Templates(directory="templates")

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
    return templates.TemplateResponse("search.html", {"request": request})


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
    rec = await generate_recommendations(source, destination, date, preference)
    return templates.TemplateResponse("recommendations.html", {
        "request": request,
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

async def _productivity_sse(action_input: TrainRecommendationResponse):
    """Async generator that yields SSE dicts as the productivity agent runs."""
    completed = {"calendar": False, "gmail": False, "tasks": False}
    try:
        async for event in stream_agent_turns(productivity_agent, action_input):
            # Use the pre-computed _safe_text attached by stream_agent_turns
            # (skips function_call parts — avoids the ADK non-text warning)
            text_lower = (getattr(event, "_safe_text", None) or "").lower()

            if not completed["calendar"] and "event created" in text_lower:
                completed["calendar"] = True
                yield {"data": json.dumps({"step": "calendar", "status": "done",
                                           "detail": "Calendar event created"})}

            if not completed["gmail"] and "draft created" in text_lower:
                completed["gmail"] = True
                yield {"data": json.dumps({"step": "gmail", "status": "done",
                                           "detail": "Gmail travel draft created"})}

            if not completed["tasks"] and "task created" in text_lower:
                completed["tasks"] = True
                dep_time = action_input.recommended_train.departure_time
                yield {"data": json.dumps({"step": "tasks", "status": "done",
                                           "detail": f"Cab reminder set for {dep_time}"})}

    except Exception as exc:
        err = str(exc)
        logger.error("Productivity agent error: %s", err)
        for step in ("calendar", "gmail", "tasks"):
            if not completed[step]:
                yield {"data": json.dumps({"step": step, "status": "error",
                                           "detail": err})}


@app.post("/confirm")
async def confirm_booking(request: Request):
    """SSE endpoint — confirms a train and triggers the productivity agent."""
    if not os.getenv("WORKSPACE_MCP_URL") and not os.getenv("WORKSPACE_MCP_COMMAND"):
        async def _mcp_missing():
            yield {"data": json.dumps({"step": "calendar", "status": "error",
                                       "detail": "Workspace MCP not configured"})}
        return EventSourceResponse(_mcp_missing(), status_code=503)

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        train_id   = body.get("train_id")
        source     = body.get("source", "")
        destination = body.get("destination", "")
        date       = body.get("date", "")
    else:
        form       = await request.form()
        train_id   = form.get("train_id")
        source     = form.get("source", "")
        destination = form.get("destination", "")
        date       = form.get("date", "")

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
    return EventSourceResponse(_productivity_sse(action_input))


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
        reload=not is_cloud,
        # Use watchfiles (thread-based) not the default multiprocessing reloader.
        # This prevents CancelledError when GCP credential fetch runs in a
        # spawned subprocess that has no event loop.
        reload_delay=0.5,
        workers=1,
    )
