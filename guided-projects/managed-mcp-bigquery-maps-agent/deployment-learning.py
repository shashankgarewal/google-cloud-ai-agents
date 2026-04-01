## Deployment Learnings — managed-mcp-bigquery-maps-agent

### Project Structure
- ADK deploy uses the folder name as agent name — must be a valid Python identifier (underscores, no hyphens)
- When deploying with `.` (root), ADK uses root folder as agent — root folder name must also be valid identifier
- `tools/` must be inside the agent folder OR at root level with proper `sys.path` setup
- Final working structure: root folder `managed_mcp_bigquery_maps_agent/` with `__init__.py` exposing `root_agent`
- `__init__.py` must expose `root_agent` directly: `from .gmap_location_analyzer.agent import root_agent`

### Auth & Credentials
- `gcloud auth login` → authenticates gcloud CLI
- `gcloud auth application-default login` → authenticates Python code (ADC) — separate file
- All terminals share the same ADC credentials file (`~/.config/gcloud/application_default_credentials.json`)
- On Cloud Run, `google.auth.default()` uses metadata server → picks up attached SA automatically
- OAuth tokens expire in ~1 hour — use `header_provider=` callback in `McpToolset` for auto-refresh
- `MCPToolset` is deprecated → use `McpToolset` (newer ADK versions)
- `header_provider` takes a function reference, not a function call: `header_provider=fn` not `header_provider=fn()`

### IAM & Permissions
- `gcloud projects add-iam-policy-binding` → grants SA access to resources
- `gcloud iam service-accounts add-iam-policy-binding` → grants access to the SA itself
- IAM changes take effect immediately (no redeploy needed)
- BigQuery MCP requires `roles/bigquery.admin` — lower roles (`dataViewer`, `jobUser`, `user`) are not enough for MCP tool calls
- Vertex AI requires `roles/aiplatform.user` on the SA
- MCP connection (200) succeeding ≠ tool calls (403) working — they need different permissions

### Cloud Run Deployment
- Code changes → full redeploy needed
- Config/IAM changes → no redeploy, instant
- Env var updates → `gcloud run services update --update-env-vars KEY=VALUE` (no redeploy)
- Reuse existing image → `gcloud run deploy --image=IMAGE_URL` (no rebuild)
- `--service_name` takes hyphens (Cloud Run rule), agent folder name takes underscores (Python rule) — different things
- ADK uses Cloud Run service region for model location — override with `GOOGLE_CLOUD_LOCATION=global` env var
- `.env` file is baked into Docker image — env var set via `gcloud run services update` overrides it

### Common Errors
- `Invalid agent name` → folder name has hyphens
- `No root_agent found` → `__init__.py` not exposing `root_agent` directly
- `No module named 'tools'` → `tools/` not inside agent folder or `sys.path` not set
- `file:///app does not appear to be Python project` → `-e .` in `requirements.txt` leftover from pyproject.toml attempt
- `gemini-3.1-pro-preview not found at us-central1` → model only available at `global` location
- `Connection closed` after 403 → ADK retries on 403 then gives up — root cause is always the 403
- `RESOURCE_EXHAUSTED 429` → Vertex AI per-minute quota hit, not billing issue

### Windows-specific
- `pscp` renames files with UUID prefix → use `git pull` instead
- Windows `\r\n` line endings in `.env` → fix with `sed -i 's/\r//' .env`