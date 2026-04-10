"""
authenticate_workspace.py
=========================
One-time setup script to authenticate your Google account with workspace-mcp.

Run this ONCE before starting the main application:
    python authenticate_workspace.py

This script:
1. Starts the workspace-mcp OAuth callback server
2. Opens a browser to Google's auth page
3. Saves the token to ~/.google_workspace_mcp/credentials/
4. All subsequent workspace-mcp tool calls reuse the saved token

After running this, no more per-tool auth URLs will appear.
"""

import os
import sys
import json
import webbrowser
import urllib.request
import urllib.parse
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
USER_EMAIL = os.getenv("USER_GOOGLE_EMAIL")

# Same scopes that workspace-mcp core tier uses
SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/tasks",
]

REDIRECT_URI = "http://localhost:8080/oauth2callback"
AUTH_CODE = None


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global AUTH_CODE
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            AUTH_CODE = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <html><body style="font-family:sans-serif;text-align:center;padding:40px">
                <h2 style="color:green">&#10003; Authentication Successful!</h2>
                <p>You can close this tab and return to the terminal.</p>
                </body></html>
            """)
        else:
            error = params.get("error", ["Unknown error"])[0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(f"<html><body><h2>Error: {error}</h2></body></html>".encode())

    def log_message(self, format, *args):
        pass  # Suppress server logs


def get_credentials_dir():
    """Matches the path workspace-mcp uses to store credentials."""
    workspace_creds_dir = os.getenv("WORKSPACE_MCP_CREDENTIALS_DIR")
    if workspace_creds_dir:
        return os.path.expanduser(workspace_creds_dir)
    google_creds_dir = os.getenv("GOOGLE_MCP_CREDENTIALS_DIR")
    if google_creds_dir:
        return os.path.expanduser(google_creds_dir)
    return os.path.join(os.path.expanduser("~"), ".google_workspace_mcp", "credentials")


def already_authenticated(creds_dir: str, email: str) -> bool:
    """Check if valid credentials already exist for this email."""
    # workspace-mcp stores as <email>.json
    cred_file = os.path.join(creds_dir, f"{email}.json")
    if os.path.exists(cred_file):
        try:
            with open(cred_file) as f:
                data = json.load(f)
            # Check if refresh_token exists (means we can refresh without re-auth)
            if data.get("refresh_token"):
                return True
        except Exception:
            pass
    return False


def exchange_code_for_tokens(code: str) -> dict:
    """Exchange authorization code for access/refresh tokens."""
    data = urllib.parse.urlencode({
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode()

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        method="POST",
    )
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def get_user_email_from_token(access_token: str) -> str:
    """Fetch the authenticated user's email from Google."""
    req = urllib.request.Request(
        f"https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    with urllib.request.urlopen(req) as resp:
        info = json.loads(resp.read().decode())
    return info.get("email", "")


def save_credentials(creds_dir: str, email: str, tokens: dict):
    """Save credentials in the format workspace-mcp expects."""
    os.makedirs(creds_dir, exist_ok=True)

    import datetime
    expiry = None
    if "expires_in" in tokens:
        expiry = (
            datetime.datetime.utcnow() +
            datetime.timedelta(seconds=int(tokens["expires_in"]))
        ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    # workspace-mcp uses google.oauth2.credentials.Credentials JSON format
    cred_data = {
        "token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scopes": SCOPES,
        "expiry": expiry,
    }

    cred_file = os.path.join(creds_dir, f"{email}.json")
    with open(cred_file, "w") as f:
        json.dump(cred_data, f, indent=2)

    print(f"\nCredentials saved to: {cred_file}")
    return cred_file


def build_auth_url() -> str:
    """Build the Google OAuth authorization URL."""
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",  # Force to always get refresh_token
    }
    if USER_EMAIL:
        params["login_hint"] = USER_EMAIL

    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)


def main():
    print("=" * 55)
    print("   Google Workspace MCP — One-Time Authentication")
    print("=" * 55)

    # Validate env vars
    if not CLIENT_ID or not CLIENT_SECRET:
        print("\nERROR: GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET")
        print("   must be set in your .env file.")
        sys.exit(1)

    print(f"\n  Email: {USER_EMAIL or '(will be detected after auth)'}")
    print(f"  Client ID: {CLIENT_ID[:20]}...")

    creds_dir = get_credentials_dir()
    print(f"  Credentials will be saved to: {creds_dir}")

    # Check if already authenticated
    if USER_EMAIL and already_authenticated(creds_dir, USER_EMAIL):
        print(f"\n[OK] Already authenticated as {USER_EMAIL}!")
        print("   workspace-mcp will use these cached credentials.")
        print("   If tools still fail, delete the file and re-run this script:")
        print(f"   {os.path.join(creds_dir, USER_EMAIL + '.json')}")
        return

    # Start local callback server
    server = HTTPServer(("localhost", 8080), OAuthCallbackHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    # Open browser
    auth_url = build_auth_url()
    print(f"\n>> Opening browser for Google authorization...")
    print(f"   If browser doesn't open, visit this URL manually:\n")
    print(f"   {auth_url}\n")
    webbrowser.open(auth_url)

    # Wait for OAuth callback
    print("... Waiting for authorization (up to 120 seconds)...")
    timeout = 120
    start = time.time()
    while AUTH_CODE is None and (time.time() - start) < timeout:
        time.sleep(0.5)

    server.shutdown()

    if AUTH_CODE is None:
        print("\nERROR: Timed out waiting for authorization.")
        print("   Please re-run this script and complete the browser login within 2 minutes.")
        sys.exit(1)

    print("\nExchanging authorization code for tokens...")
    try:
        tokens = exchange_code_for_tokens(AUTH_CODE)
    except Exception as e:
        print(f"\nERROR: Token exchange failed: {e}")
        print("   Make sure http://localhost:8080/oauth2callback is in your OAuth client's")
        print("   authorized redirect URIs in Google Cloud Console.")
        sys.exit(1)

    if "error" in tokens:
        print(f"\nERROR: Token error: {tokens}")
        sys.exit(1)

    # Get the authenticated email
    email = USER_EMAIL
    if not email:
        try:
            email = get_user_email_from_token(tokens["access_token"])
            print(f"Authenticated as: {email}")
        except Exception:
            email = "unknown@gmail.com"

    # Save credentials
    cred_file = save_credentials(creds_dir, email, tokens)

    print("\n" + "=" * 55)
    print("Authentication Complete!")
    print("=" * 55)
    print(f"\nworkspace-mcp will now use these credentials automatically")
    print(f"when running in --single-user mode.")
    print(f"\nYou can now start the application:")
    print(f"    python main.py")
    print()


if __name__ == "__main__":
    main()
