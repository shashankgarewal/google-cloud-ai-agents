#!/usr/bin/env python3
"""
setup_credentials.py — One-time local authentication for Cloud Run deployment.

Run this script ONCE on your local machine before building the Docker image.
It opens a browser window to complete Google OAuth, then saves the credential
file to  credentials/<your-email>.json  in this project directory.

The Dockerfile copies that file into the container image at build time, so
Cloud Run has valid credentials without any browser interaction post-deploy.

Usage
-----
    python setup_credentials.py

Requirements
------------
    pip install google-auth-oauthlib requests python-dotenv

Steps after running
-------------------
    1. docker build -t smart-travel-planner .
    2. Set USER_GOOGLE_EMAIL=<your-email> in Cloud Run environment variables
    3. gcloud run deploy ...
"""

import json
import os
import sys
from pathlib import Path

# ── Load .env so GOOGLE_OAUTH_CLIENT_ID etc. are available ──────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv optional — fall back to environment

GOOGLE_OAUTH_CLIENT_ID     = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()

# Scopes needed by workspace-mcp tools (calendar, gmail, tasks)
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/tasks",
]


def main() -> None:
    if not GOOGLE_OAUTH_CLIENT_ID or not GOOGLE_OAUTH_CLIENT_SECRET:
        print("❌  GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET must be set in .env")
        sys.exit(1)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        import requests as _requests
    except ImportError:
        print("❌  Missing dependency. Run: pip install google-auth-oauthlib requests")
        sys.exit(1)

    # InstalledAppFlow opens a browser and handles the loopback redirect automatically
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"   # only needed for localhost redirect

    client_config = {
        "installed": {
            "client_id":     GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
            "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
            "token_uri":     "https://oauth2.googleapis.com/token",
        }
    }

    print("\n🔑  Starting Google OAuth flow …")
    print("    A browser window will open. Sign in and grant the requested permissions.\n")

    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    creds = flow.run_local_server(
        port=0,
        prompt="consent",
        access_type="offline",
    )

    if not creds.refresh_token:
        print("⚠️  No refresh_token received. Re-run and ensure you grant offline access.")
        sys.exit(1)

    # Fetch user email
    resp = _requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {creds.token}"},
        timeout=10,
    )
    resp.raise_for_status()
    user_info = resp.json()
    email = user_info["email"]

    # ── Save to credentials/ (Docker build context folder) ──────────────────
    project_cred_dir = Path(__file__).parent / "credentials"
    project_cred_dir.mkdir(exist_ok=True)
    project_cred_file = project_cred_dir / f"{email}.json"
    project_cred_file.write_text(creds.to_json())

    # ── Also save to ~/.google_workspace_mcp/credentials/ (local dev) ───────
    home_cred_dir = Path.home() / ".google_workspace_mcp" / "credentials"
    home_cred_dir.mkdir(parents=True, exist_ok=True)
    home_cred_file = home_cred_dir / f"{email}.json"
    home_cred_file.write_text(creds.to_json())

    print(f"\n✅  Credentials saved!")
    print(f"    Project (Docker build context): {project_cred_file}")
    print(f"    Local dev (~/.google_workspace_mcp): {home_cred_file}")
    print(f"\n    Email: {email}")
    print(f"\nNext steps:")
    print(f"  1. Set  USER_GOOGLE_EMAIL={email}  in your .env")
    print(f"  2. Build the Docker image:  docker build -t smart-travel-planner .")
    print(f"  3. Deploy to Cloud Run with  --set-env-vars USER_GOOGLE_EMAIL={email}")
    print(f"\n⚠️  Keep credentials/{email}.json out of git! It is already in .gitignore.")


if __name__ == "__main__":
    main()
