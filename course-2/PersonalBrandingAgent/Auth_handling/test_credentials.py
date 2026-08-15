"""
Tests whether your current LinkedIn credentials can fetch data.

Checks, in order:
  1. The saved access token + refresh token are still valid / refreshable.
  2. The token can hit the userinfo endpoint (openid / profile scopes).
  3. The token can read a documented sample profile (r_liteprofile via
     /v2/people/(id:...) or the OpenID /v2/userinfo).

Run:
    python test_credentials.py
"""

import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN_FILE = "linkedin_tokens.json"
REDIRECT_URI = "http://localhost:8000/callback"

CLIENT_ID = os.environ.get("LINKEDIN_CLIENT_ID")
CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET")


def load_tokens():
    with open(TOKEN_FILE) as f:
        return json.load(f)


def refresh_access_token(tokens):
    if "refresh_token" not in tokens:
        return None, "no refresh_token present in token file"

    try:
        resp = requests.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
    except requests.RequestException as e:
        return None, f"request failed: {e}"

    if resp.status_code != 200:
        return None, f"refresh failed: {resp.status_code} {resp.text}"

    new_tokens = resp.json()
    tokens.update(new_tokens)
    with open(TOKEN_FILE, "w") as f:
        json.dump(tokens, f, indent=2)
    return new_tokens["access_token"], None


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("FAIL: LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET missing in .env")
        return

    tokens = load_tokens()
    access_token = tokens.get("access_token")
    if not access_token:
        print("FAIL: no access_token in token file")
        return

    print("== Step 1: try saved access token ==")
    try:
        resp = requests.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
    except requests.RequestException as e:
        print(f"  network error: {e}")
        return

    if resp.status_code == 401:
        print("  access token rejected (401). Trying refresh_token...")
        new_token, err = refresh_access_token(tokens)
        if err:
            print(f"  FAIL: {err}")
            return
        access_token = new_token
        print("  refreshed access token OK.")
        resp = requests.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )

    print(f"  userinfo endpoint -> {resp.status_code}")
    if resp.status_code != 200:
        print(f"  FAIL: {resp.text}")
        return

    data = resp.json()
    print(f"  OK. Authenticated as {data.get('name')} (sub={data.get('sub')})")
    print(f"  email: {data.get('email')} | verified: {data.get('email_verified')}")

    print()
    print("== Step 2: r_liteprofile / profile read via people API ==")
    sub = data.get("sub")
    sample_urn = "urn:li:person:uvNqN5Xf5g"
    for label, urn in (("you", f"urn:li:person:{sub}"), ("sample profile", sample_urn)):
        r = requests.get(
            f"https://api.linkedin.com/v2/people/(id:{urn.split(':')[-1]})",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "projection": "(id,localizedFirstName,localizedLastName,profilePicture(displayImage~:playableStreams))"
            },
            timeout=30,
        )
        print(f"  {label} -> {r.status_code}")
        if r.status_code == 200:
            print(f"    {r.json()}")
        elif r.status_code != 403:
            print(f"    {r.text[:200]}")


if __name__ == "__main__":
    main()