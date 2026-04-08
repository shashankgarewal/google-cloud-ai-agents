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

# ---- Application code ----
COPY . .

# ---- Pre-baked credentials ----
# credentials/ is populated locally by running: python setup_credentials.py
# It is gitignored but NOT dockerignored — included in the build context.
# This copies  credentials/<email>.json  into the standard workspace-mcp
# credentials directory so --single-user mode works without any browser auth.
RUN mkdir -p /root/.google_workspace_mcp/credentials
COPY credentials/ /root/.google_workspace_mcp/credentials/

# ---- Runtime ----
# Cloud Run injects PORT; fall back to 8080 for local docker run.
EXPOSE 8080
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1
