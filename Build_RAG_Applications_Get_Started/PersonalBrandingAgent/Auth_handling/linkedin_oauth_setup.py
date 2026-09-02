"""
One-time LinkedIn OAuth authorization script.

Run this ONCE to get your first access token + refresh token.
After this, your daily posting script will use the saved tokens
and refresh them automatically without you doing this again.

SETUP BEFORE RUNNING:
    Set these as environment variables (don't hardcode secrets in code):

        export LINKEDIN_CLIENT_ID="783pis53u8ro4m"
        export LINKEDIN_CLIENT_SECRET="your-client-secret-here"

    (On Windows PowerShell: $env:LINKEDIN_CLIENT_ID="...")

WHAT THIS SCRIPT DOES:
    1. Opens your browser to LinkedIn's consent screen
    2. You log in and click "Allow"
    3. LinkedIn redirects back to localhost:8000/callback with a code
    4. This script catches that code and exchanges it for tokens
    5. Tokens are saved to linkedin_tokens.json in this folder

Run:
    python linkedin_oauth_setup.py
"""

import json
import os
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ.get("LINKEDIN_CLIENT_ID")
CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8000/callback"
SCOPES = "openid profile w_member_social email"
TOKEN_FILE = "linkedin_tokens.json"

if not CLIENT_ID or not CLIENT_SECRET:
    raise SystemExit(
        "Missing LINKEDIN_CLIENT_ID or LINKEDIN_CLIENT_SECRET environment variables.\n"
        "Set them before running this script (see docstring above)."
    )

authorization_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global authorization_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            authorization_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<h2>Success! You can close this tab and go back to your terminal.</h2>"
            )
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Something went wrong. No authorization code received.")

    def log_message(self, format, *args):
        pass  # suppress default request logging


def get_authorization_code():
    auth_params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
    }
    auth_url = (
        "https://www.linkedin.com/oauth/v2/authorization?"
        + urllib.parse.urlencode(auth_params)
    )

    print("Opening your browser for LinkedIn authorization...")
    print("If it doesn't open automatically, visit this URL manually:\n")
    print(auth_url)
    print()
    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", 8000), CallbackHandler)
    print("Waiting for you to approve access in the browser...")
    server.handle_request()  # blocks until one request is received
    server.server_close()

    if not authorization_code:
        raise SystemExit("No authorization code received. Try again.")

    return authorization_code


def exchange_code_for_tokens(code):
    response = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    if response.status_code != 200:
        raise SystemExit(
            f"Token exchange failed: {response.status_code} {response.text}"
        )

    return response.json()


def main():
    code = get_authorization_code()
    print("Authorization code received. Exchanging for tokens...")

    tokens = exchange_code_for_tokens(code)

    with open(TOKEN_FILE, "w") as f:
        json.dump(tokens, f, indent=2)

    print(f"\nDone. Tokens saved to {TOKEN_FILE}")
    print(f"Access token expires in {tokens.get('expires_in')} seconds (~2 months).")
    print("\nIMPORTANT: Add linkedin_tokens.json to your .gitignore — never commit it.")


if __name__ == "__main__":
    main()
