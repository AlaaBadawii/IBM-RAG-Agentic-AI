"""
Sends a single test post to your own LinkedIn profile.

This is the manual verification tool for the proven publish path. The path an
unattended workflow uses is ``app/integrations/linkedin/publish_to_linkedin``,
which is the same request without a person at the keyboard, with the
credential lifecycle, timeouts and error classification this script does not
have — see ``docs/architecture/linkedin-integration.md``.

Run this after linkedin_oauth_setup.py has created linkedin_tokens.json
in the same folder.

Run:
    python test_post.py
"""

import json
from pathlib import Path

import requests
from dotenv import load_dotenv

# Resolved relative to this file, never to the current working directory.
HERE = Path(__file__).resolve().parent
load_dotenv(HERE.parent / ".env")

TOKEN_FILE = Path(__file__).parent / "linkedin_tokens.json"

TIMEOUT_SECONDS = 30


def load_access_token():
    with open(TOKEN_FILE) as f:
        tokens = json.load(f)
    return tokens["access_token"]


def get_person_urn(access_token):
    """Fetch your LinkedIn member ID (needed to construct the post author URN)."""
    response = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    return f"urn:li:person:{data['sub']}"


def create_post(access_token, author_urn, text):
    payload = {
        "author": author_urn,
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    response = requests.post(
        "https://api.linkedin.com/rest/posts",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202607",
        },
        json=payload,
        timeout=TIMEOUT_SECONDS,
    )

    if response.status_code == 201:
        post_id = response.headers.get("x-restli-id", "unknown")
        print(f"Post published successfully. Post ID: {post_id}")
    else:
        print(f"Failed: {response.status_code}")
        print(response.text)


def main():
    access_token = load_access_token()
    author_urn = get_person_urn(access_token)
    print(f"Authenticated as: {author_urn}")

    test_text = (
        "Testing my personal content automation pipeline — this post was "
        "published programmatically via the LinkedIn API as part of a "
        "project I'm building to document my AI/backend engineering journey. "
        "More real posts coming soon."
    )

    confirm = input(f"\nAbout to publish this post:\n\n{test_text}\n\nProceed? (y/n): ")
    if confirm.lower() == "y":
        create_post(access_token, author_urn, test_text)
    else:
        print("Cancelled.")


if __name__ == "__main__":
    main()
