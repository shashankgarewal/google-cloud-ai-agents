# Smart Travel Journey Planner

A multi-agent AI system that recommends the most reliable trains by analyzing delay patterns and real-time data. It uses Model Context Protocol (MCP) tools and LLM reasoning to fetch, evaluate, and rank train options based on performance and user preferences. The system provides structured, explainable recommendations through an API-ready interface and an interactive UI.

## Features

- **Multi-Agent Architecture**: Built with `google-adk`, splitting responsibilities between data fetching, recommendation reasoning, and productivity automation.
- **Explainable Recommendations**: Get tailored train suggestions complete with reliability scores, fallback options, and direct "Buy Now" links.
- **Productivity Integration (Workspace MCP)**: After booking confirmation, an automated agent schedules calendar events, drafts an email with itinerary details, and sets a task/reminder for your cab.
- **HTMX-Powered UI**: A lightweight interactive frontend for searching journeys, viewing detailed AI insights for each train option, and confirming booking actions.
- **Cloud Run Ready**: Containerized configuration and straightforward scripts to deploy the whole setup seamlessly to Google Cloud Run.

## Architecture

1. **Orchestrator/Root Agent** (`agents/orchestrator.py`): Handles free-form chat routing.
2. **Data Fetching Agent** (`agents/data_fetcher.py`): Gathers train schedules and context.
3. **Recommendor Agent** (`agents/recommendor.py`): Analyzes the fetched train options alongside the user's preferences to provide structured JSON recommendations.
4. **Productivity Agent** (`agents/productivity.py`): Initiated when a booking is confirmed. Connects to Workspace MCP tools to interact with Google Workspace (Calendar, Gmail, Tasks).

---

## Local Development

### 1. Prerequisites
- Python 3.11+
- Google Cloud SDK (`gcloud` CLI) installed (if you want to deploy or use GCP services)

### 2. Install Dependencies
```bash
python -m venv venv
source venv/bin/activate  # Or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

### 3. Environment Variables
Copy `.env-template` to `.env` and fill in your keys (especially `GOOGLE_OAUTH_CLIENT_ID` and `SECRET`).
```bash
cp .env-template .env
```

### 4. Authenticate Google Workspace
Run this script once to link your Google account (for Calendar, Gmail, Tasks):
```bash
python setup_credentials.py
```
This opens a browser for login and saves credentials to `credentials/` (for Docker) and your home directory (for local dev). Update `USER_GOOGLE_EMAIL` in your `.env` to match the account you used.

### 5. Run the Server
Use Uvicorn via `main.py` directly:
```bash
python main.py
```
This runs the local development server at `http://127.0.0.1:8000`.

---

## API Reference

The Journey Planner exposes REST APIs and Server-Sent Events (SSE) endpoints.

### `GET /recommendations`
Get structured AI-driven train recommendations.

**Query Parameters:**
- `source` (string): Departure station/city.
- `destination` (string): Arrival station/city.
- `date` (string): Date of travel (e.g. `YYYY-MM-DD`).
- `preference` (string, optional): Specific user priorities (e.g., "fastest route", "morning departures only").

**Response** (JSON - `TrainRecommendationResponse` format):
```json
{
  "source": "City A",
  "destination": "City B",
  "date": "2026-04-10",
  "recommended_train": {
    "train_id": "11007",
    "train_name": "Deccan Express",
    "departure_time": "06:45",
    "arrival_time": "09:00",
    "reliability_score": 0.98,
    "availability": "Available",
    "reason": "Highest punctuality on this corridor...",
    "buy_now_link": "https://www.makemytrip.com/..."
  },
  "alternatives": [ ... ],
  "insights": {
     "summary": "..."
  }
}
```

### `POST /recommendations`
Same as the `GET` endpoint but accepts a JSON body instead.
**Request Body:**
```json
{
  "source": "City A",
  "destination": "City B",
  "date": "2026-04-10",
  "preference": "fastest"
}
```

### `POST /confirm`
Confirms a train booking choice and triggers the background productivity agent to sync across Google Workspace (Calendar, Tasks, Gmail). It streams the progress via Server-Sent Events (SSE).

**Request Body (JSON or Form-Data):**
- `train_id` (string)
- `source` (string)
- `destination` (string)
- `date` (string)

**Stream Response (SSE):**
Yields intermediate JSON payload status indicating the completion of each sub-agent step:
```json
{"step": "calendar", "status": "done", "detail": "Calendar event created"}
{"step": "gmail", "status": "done", "detail": "Gmail travel draft created"}
{"step": "tasks", "status": "done", "detail": "Cab reminder set for 06:45"}
```

---

## Deployment (Google Cloud)

Deploying to Cloud Run involves three broad steps.

### 1. Set up Infrastructure
Enable Google APIs, create Service Accounts, and assign necessary IAM roles.
```bash
./shell/setup_infrastructure.sh
```

### 2. Set up Deployment Defaults
Configure deployment APIs and assign roles for Cloud Build and Compute.
```bash
./shell/setup_defaults.sh
```

### 3. Deploy to Cloud Run
Build the Docker image and deploy it.
```bash
./shell/deploy_cloud_run.sh
```

> NOTE: Windows users can utilize the `.ps1` equivalents mapping to the same deployment phases.