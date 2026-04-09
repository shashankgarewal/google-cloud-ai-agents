FROM python:3.11-slim

WORKDIR /app

# ---- System dependencies ----
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ---- Python dependencies ----
# workspace-mcp is in requirements.txt → installed to /usr/local/bin/workspace-mcp
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- uv (fallback — lets `uvx workspace-mcp` work if the pip binary is missing) ----
RUN pip install --no-cache-dir uv

# ---- Application code ----
COPY . .

# ---- Credential directory ----
# Created at build time so it exists; populated at runtime via the web OAuth flow.
# Pre-baked credentials can also be volume-mounted here for zero-cold-start auth.
RUN mkdir -p /root/.google_workspace_mcp/credentials

# ---- Runtime ----
# Cloud Run injects PORT; fall back to 8080 for local docker run.
EXPOSE 8080
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1
