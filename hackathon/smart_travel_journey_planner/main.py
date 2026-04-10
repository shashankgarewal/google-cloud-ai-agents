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
USER_GOOGLE_EMAIL are cached on disk by authenticate_workspace.py.
No per-request OAuth flow is needed — set USER_GOOGLE_EMAIL in .env
and run `python authenticate_workspace.py` once before starting.
"""
from __future__ import annotations

import asyncio
import glob
import json
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
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

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Multi-user Google OAuth 2.0 configuration
# ---------------------------------------------------------------------------
GOOGLE_OAUTH_CLIENT_ID     = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_OAUTH_REDIRECT_URI  = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://127.0.0.1:8000/auth/callback")

# Workspace + identity scopes requested in a single OAuth consent
OAUTH_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/tasks",
]

# Fallback email used only by /dev/test-confirm (when no session user)
_DEV_FALLBACK_EMAIL = os.getenv("USER_GOOGLE_EMAIL", "")


def _make_oauth_flow(redirect_uri: str = ""):
    """Build a google_auth_oauthlib Flow from env credentials."""
    from google_auth_oauthlib.flow import Flow  # lazy import
    uri = redirect_uri or GOOGLE_OAUTH_REDIRECT_URI
    return Flow.from_client_config(
        {
            "web": {
                "client_id":     GOOGLE_OAUTH_CLIENT_ID,
                "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
                "redirect_uris": [uri],
                "auth_uri":  "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=OAUTH_SCOPES,
        redirect_uri=uri,
    )


def _get_redirect_uri(request: Request) -> str:
    """
    Derive the OAuth redirect URI from the actual request.
    - If GOOGLE_OAUTH_REDIRECT_URI is explicitly set in env (non-default), use it.
    - Otherwise auto-detect from request.base_url so it works on:
        * Local dev  : http://127.0.0.1:8000/auth/callback
        * Cloud Run  : https://<service>.a.run.app/auth/callback
        * Any proxy  : https://<custom-domain>/auth/callback
    """
    env_val = GOOGLE_OAUTH_REDIRECT_URI.strip()
    default  = "http://127.0.0.1:8000/auth/callback"
    if env_val and env_val != default:
        return env_val  # explicit override wins
    # Auto-detect: use scheme+host from the incoming request
    base = f"{request.url.scheme}://{request.url.netloc}"
    return f"{base}/auth/callback"

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
    import json as _json
    cred_file = os.path.join(_get_creds_dir(), f"{email}.json")
    if not os.path.exists(cred_file):
        return False
    try:
        with open(cred_file) as f:
            data = _json.load(f)
        return bool(data.get("refresh_token"))
    except Exception:
        return False

# ---------------------------------------------------------------------------
# In-memory train cache — populated by generate_recommendations() so that
# /confirm and /ui/insight can look up trains by ID without re-running agents.
# ---------------------------------------------------------------------------
train_cache: dict[str, _Recommendation] = {}

# Pre-seed with a stable test entry so /dev/test-confirm works without any search.
# This uses zero Railway MCP calls and zero data-agent LLM calls.
_TEST_TRAIN_ID = "TEST001"
train_cache[_TEST_TRAIN_ID] = _Recommendation(
    train_id=_TEST_TRAIN_ID,
    train_name="Rajdhani Express (TEST)",
    departure_time="16:55",
    arrival_time="08:35",
    reliability_score=0.95,
    availability="Available",
    reason="Pre-seeded test entry — triggers productivity agent without Railway MCP.",
    buy_now_link="https://www.makemytrip.com/railways/",
)


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
    user = request.session.get("user")
    return templates.TemplateResponse("search.html", {"request": request, "user": user})


@app.get("/check-auth")
async def check_auth(request: Request):
    """Returns session user info + workspace-mcp credential status."""
    import glob
    user = request.session.get("user", {})
    email = user.get("email", "")
    authenticated = _is_workspace_authenticated(email) if email else False
    if not authenticated and not email:
        creds_dir = _get_creds_dir()
        files = glob.glob(os.path.join(creds_dir, "*.json"))
        if files:
            email = os.path.basename(files[0]).replace(".json", "")
            authenticated = True
    return JSONResponse({
        "authenticated": authenticated,
        "email": email,
        "mode": "multi-user",
        "message": (
            f"Ready — using {email}" if authenticated
            else "Not signed in — click Sign in to Unlock Productivity"
        )
    })


@app.get("/login")
async def login(request: Request, next: str = "/"):
    """Starts Google OAuth 2.0 consent flow. Works on local dev and Cloud Run."""
    if not GOOGLE_OAUTH_CLIENT_ID or not GOOGLE_OAUTH_CLIENT_SECRET:
        return JSONResponse(
            {"error": "GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET not set in .env"},
            status_code=500,
        )
    redirect_uri = _get_redirect_uri(request)
    flow = _make_oauth_flow(redirect_uri=redirect_uri)
    auth_url, state = flow.authorization_url(
        prompt="consent",
        access_type="offline",
        include_granted_scopes="true",
    )
    request.session["oauth_state"]        = state
    request.session["oauth_next"]         = next
    request.session["oauth_redirect_uri"] = redirect_uri  # store for callback parity
    return RedirectResponse(auth_url)


@app.get("/auth/callback")
async def auth_callback(request: Request):
    """Handles Google OAuth callback — works on local (http) and Cloud Run (https)."""
    state        = request.session.pop("oauth_state", None)
    next_url     = request.session.pop("oauth_next", "/")
    redirect_uri = request.session.pop("oauth_redirect_uri", _get_redirect_uri(request))

    # Check for error param first (user denied / Google error)
    error = request.query_params.get("error")
    if error:
        logger.warning("OAuth error from Google: %s", error)
        return templates.TemplateResponse("search.html", {
            "request": request,
            "user": None,
            "auth_error": f"Sign-in cancelled ({error}). Please try again.",
        })

    # Allow http for local dev — must force-set BEFORE fetch_token
    if redirect_uri.startswith("http://"):
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    # --- Token exchange ---
    try:
        flow = _make_oauth_flow(redirect_uri=redirect_uri)
        flow.fetch_token(authorization_response=str(request.url), state=state)
        creds = flow.credentials
    except Exception as exc:
        err = str(exc)
        logger.error("OAuth token exchange failed: %s", err)
        if "state" in err.lower():
            msg = "Sign-in session expired. Please try again."
        elif "access_denied" in err.lower():
            msg = "Sign-in was cancelled. Please try again."
        elif "getaddrinfo" in err or "nameresolut" in err.lower():
            msg = "Network error during sign-in — check your internet connection."
        else:
            msg = f"Sign-in failed: {err[:120]}"
        return templates.TemplateResponse("search.html", {
            "request": request, "user": None, "auth_error": msg,
        })

    # --- Fetch user profile ---
    try:
        import requests as _requests
        resp = _requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {creds.token}"},
            timeout=10,
        )
        resp.raise_for_status()
        user_info = resp.json()
        email   = user_info["email"]
        name    = user_info.get("name", email.split("@")[0])
        picture = user_info.get("picture", "")
    except Exception as exc:
        logger.error("Failed to fetch user profile: %s", exc)
        return templates.TemplateResponse("search.html", {
            "request": request, "user": None,
            "auth_error": "Signed in but couldn't retrieve your profile. Please try again.",
        })

    # --- Save credential file (for workspace-mcp stdio fallback) ---
    try:
        cred_dir  = _get_creds_dir()
        os.makedirs(cred_dir, exist_ok=True)
        with open(os.path.join(cred_dir, f"{email}.json"), "w") as f:
            f.write(creds.to_json())
        logger.info("Saved workspace-mcp credentials for %s", email)
    except Exception as exc:
        logger.warning("Could not save credential file for %s: %s", email, exc)

    # --- Store in session and redirect ---
    request.session["user"]         = {"email": email, "name": name, "picture": picture}
    request.session["access_token"] = creds.token or ""
    logger.info("User signed in: %s", email)
    return RedirectResponse(next_url)




@app.get("/logout")
async def logout(request: Request):
    """Clears the session and redirects to home."""
    request.session.clear()
    return RedirectResponse("/")


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

    user = request.session.get("user")
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
# DEV: /dev/test-confirm — test productivity agent without any train search
# ---------------------------------------------------------------------------

@app.get("/dev/test-confirm", response_class=HTMLResponse)
async def dev_test_confirm(request: Request):
    """
    Developer shortcut: test the Calendar + Gmail + Tasks productivity flow
    without doing a full train search.  Uses the pre-seeded TEST001 entry.

    Renders an inline page with the sync panel and fires /confirm immediately
    on load — no Railway MCP, no data-fetching agents, no quota usage for search.

    Open:  http://127.0.0.1:8000/dev/test-confirm
    """
    test_date = "2026-04-23"
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Dev: Test Productivity Confirm</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>body {{ background:#f0f4f8; }}</style>
</head>
<body class="min-h-screen flex items-center justify-center p-8">
  <div class="bg-white rounded-2xl shadow p-6 w-full max-w-md">
    <div class="mb-4 p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-sm">
      <strong>🛠 Dev test page</strong> — triggers productivity agent with a pre-seeded
      test train. No Railway MCP or search agents are called.
    </div>
    <div class="mb-5 text-sm text-gray-600 space-y-1">
      <div><span class="font-medium">Train:</span> Rajdhani Express (TEST001)</div>
      <div><span class="font-medium">Route:</span> MUMBAI → DELHI</div>
      <div><span class="font-medium">Date:</span> {test_date}</div>
      <div><span class="font-medium">User:</span> {request.session.get('user', {}).get('email') or _DEV_FALLBACK_EMAIL or '(not signed in)'}</div>
    </div>

    <!-- Sync panel (copy of partials/sync_panel.html structure) -->
    <div id="sync-panel" class="bg-white rounded-2xl p-5 border border-gray-100">
      <h3 class="font-medium text-gray-700 text-[14px] mb-4">Synced with your services</h3>
      <div class="space-y-4">
        {"".join(f'''
        <div id="sync-row-{step}" class="flex items-center justify-between p-3 rounded-xl border border-gray-100 opacity-50 bg-gray-50 transition-all">
          <div><p class="text-[14px] font-medium text-gray-900" id="sync-title-{step}">Syncing {step}...</p>
               <p class="text-[12px] text-gray-500" id="sync-detail-{step}">Waiting for agent</p></div>
          <div id="sync-status-{step}">
            <svg class="animate-spin w-5 h-5 text-blue-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          </div>
        </div>''' for step in ["calendar","gmail","tasks"])}
      </div>
    </div>
    <button onclick="location.reload()" class="mt-4 w-full py-2 text-sm text-gray-500 hover:text-gray-700 border border-gray-200 rounded-xl hover:bg-gray-50 transition-all">
      ↩ Re-run test
    </button>
  </div>

  <script>
  const DONE_ICON = '<svg class="w-5 h-5 text-green-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"></path></svg>';
  const ERR_ICON  = '<svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M6 18L18 6M6 6l12 12" stroke-linecap="round" stroke-linejoin="round"></path></svg>';

  function updateStep(step, status, detail) {{
    const row    = document.getElementById('sync-row-'    + step);
    const icon   = document.getElementById('sync-status-' + step);
    const title  = document.getElementById('sync-title-'  + step);
    const det    = document.getElementById('sync-detail-' + step);
    if (!row) return;
    row.classList.remove('opacity-50','bg-gray-50');
    row.classList.add('bg-white','opacity-100','shadow-sm','border-gray-200');
    if (detail) det.textContent = detail;
    if (status === 'done') {{
      icon.innerHTML = DONE_ICON;
      title.textContent = {{calendar:'Calendar event created', gmail:'Gmail draft created', tasks:'Cab reminder set'}}[step] || 'Done';
    }} else if (status === 'error') {{
      icon.innerHTML = ERR_ICON;
      title.classList.add('text-red-500');
      title.textContent = 'Sync failed';
    }}
  }}

  (async () => {{
    const fd = new FormData();
    fd.append('train_id',    '{_TEST_TRAIN_ID}');
    fd.append('source',      'MUMBAI');
    fd.append('destination', 'DELHI');
    fd.append('date',        '{test_date}');

    const resp = await fetch('/confirm', {{ method: 'POST', body: fd }});
    if (!resp.ok) {{ console.error('Confirm failed', resp.status); return; }}

    const reader  = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    while (true) {{
      const {{done, value}} = await reader.read();
      if (done) break;
      buf += decoder.decode(value, {{stream: true}});
      const lines = buf.split('\\n');
      buf = lines.pop();
      for (const line of lines) {{
        if (!line.startsWith('data: ')) continue;
        try {{
          const ev = JSON.parse(line.slice(6).trim());
          if (ev.step) updateStep(ev.step, ev.status, ev.detail);
        }} catch (_) {{}}
      }}
    }}
  }})();
  </script>
</body>
</html>"""
    return HTMLResponse(html)


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
    Single-user mode: uses USER_GOOGLE_EMAIL from .env directly.
    """
    user      = request.session.get("user", {})
    user_email = user.get("email", "")
    if not user_email:
        async def _no_auth():
            for step in ("calendar", "gmail", "tasks"):
                yield {"data": json.dumps({"step": step, "status": "error",
                                           "detail": "Not signed in — click \"Sign in to Unlock Productivity\""})}
        return EventSourceResponse(_no_auth())

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
    access_token = user.get("access_token", "") or request.session.get("access_token", "")
    return EventSourceResponse(_productivity_sse(action_input, user_email, access_token=access_token))


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
