#!/usr/bin/env python3
"""Read-only Tavily test for discovering public LinkedIn profile/post content.

What this script does:
1. Loads TAVILY_API_KEY from a .env file.
2. Runs a few targeted web searches for a public LinkedIn profile and posts.
3. Attempts Tavily Extract on the profile URL and a few post URLs found in results.
4. Saves full API responses to tavily_test_results.json for inspection.

It does not log in to LinkedIn, publish anything, or bypass access restrictions.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from tavily import TavilyClient


# -------- Configuration --------
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = SCRIPT_DIR / "tavily_test_results.json"
PROFILE_URL = "https://www.linkedin.com/in/alaabadawii/"
MAX_RESULTS_PER_QUERY = 5
MAX_POST_URLS_TO_EXTRACT = 4  # In addition to the profile URL.
SEARCH_DEPTH = "advanced"  # Change to "basic" to reduce search cost.

SEARCH_QUERIES = [
    'site:linkedin.com/in/alaabadawii',
    'site:linkedin.com/posts/ "Alaa Badawii" OR "alaabadawii"',
    'site:linkedin.com/feed/update/ "Alaa Badawii" OR "alaabadawii"',
]

# Look only for identifiers explicitly present in retrieved text.
LINKEDIN_URN_RE = re.compile(
    r"urn:li:(?:activity|share|ugcPost|comment):[^\s\"'<>]+",
    flags=re.IGNORECASE,
)


def load_api_key() -> str:
    """Load the key from .env beside this script, or from the current environment."""
    env_file = SCRIPT_DIR / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file, override=False)
    else:
        # Also search the current directory / parent directories for a .env file.
        load_dotenv(override=False)

    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "TAVILY_API_KEY was not found. Add this line to your .env file:\n"
            "TAVILY_API_KEY=tvly-your-key-here\n"
            f"Expected .env location: {env_file}"
        )
    return api_key


def is_linkedin_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == "linkedin.com" or host.endswith(".linkedin.com")


def is_post_url(url: str) -> bool:
    """Return True for common public LinkedIn post URL patterns."""
    if not is_linkedin_url(url):
        return False
    path = urlparse(url).path.lower()
    return "/posts/" in path or "/feed/update/" in path or "/pulse/" in path


def compact_text(value: Any, limit: int = 500) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text if len(text) <= limit else text[:limit] + "... [truncated in console; full response is in JSON]"


def run_search(client: TavilyClient, query: str) -> dict[str, Any]:
    print(f"\n[SEARCH] {query}")
    try:
        response = client.search(
            query=query,
            search_depth=SEARCH_DEPTH,
            max_results=MAX_RESULTS_PER_QUERY,
            include_raw_content=True,
            include_answer=False,
        )
        results = response.get("results", []) if isinstance(response, dict) else []
        print(f"  Results returned: {len(results)}")
        return {"query": query, "response": response}
    except Exception as exc:  # Keep running so one failed query doesn't discard others.
        message = f"{type(exc).__name__}: {exc}"
        print(f"  ERROR: {message}")
        return {"query": query, "error": message}


def collect_candidate_post_urls(search_runs: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for run in search_runs:
        response = run.get("response", {})
        if not isinstance(response, dict):
            continue
        for item in response.get("results", []):
            url = item.get("url", "")
            if not isinstance(url, str) or not is_post_url(url):
                continue
            normalized = url.rstrip("/")
            if normalized not in seen:
                seen.add(normalized)
                urls.append(url)
    return urls[:MAX_POST_URLS_TO_EXTRACT]


def run_extract(client: TavilyClient, urls: list[str]) -> dict[str, Any]:
    print("\n[EXTRACT]")
    for url in urls:
        print(f"  - {url}")

    try:
        response = client.extract(
            urls=urls,
            extract_depth="advanced",
            format="markdown",
            timeout=60,
        )
        results = response.get("results", []) if isinstance(response, dict) else []
        failures = response.get("failed_results", []) if isinstance(response, dict) else []
        print(f"  Extracted successfully: {len(results)}")
        print(f"  Failed URLs: {len(failures)}")
        return {"urls_requested": urls, "response": response}
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        print(f"  ERROR: {message}")
        return {"urls_requested": urls, "error": message}


def iter_text_for_identifier_scan(payload: dict[str, Any]):
    """Yield retrieved text only; identifiers are never guessed or fabricated."""
    for run in payload.get("searches", []):
        response = run.get("response", {})
        if not isinstance(response, dict):
            continue
        for result in response.get("results", []):
            yield str(result.get("url", ""))
            yield str(result.get("title", ""))
            yield str(result.get("content", ""))
            yield str(result.get("raw_content", "") or "")

    extract = payload.get("extract", {})
    response = extract.get("response", {})
    if isinstance(response, dict):
        for result in response.get("results", []):
            yield str(result.get("url", ""))
            yield str(result.get("raw_content", "") or result.get("content", ""))


def print_summary(payload: dict[str, Any]) -> None:
    print("\n" + "=" * 78)
    print("TAVILY TEST SUMMARY")
    print("=" * 78)

    total_results = 0
    for run in payload.get("searches", []):
        print(f"\nQuery: {run['query']}")
        if "error" in run:
            print(f"  Error: {run['error']}")
            continue

        response = run.get("response", {})
        results = response.get("results", []) if isinstance(response, dict) else []
        total_results += len(results)
        for index, result in enumerate(results, start=1):
            print(f"  {index}. {result.get('title', '(no title)')}")
            print(f"     URL: {result.get('url', '')}")
            print(f"     Score: {result.get('score', 'n/a')}")
            print(f"     Snippet: {compact_text(result.get('content', ''), 350)}")
            raw = result.get("raw_content")
            print(f"     Search raw content available: {'yes' if raw else 'no'}")

    extract = payload.get("extract", {})
    extract_response = extract.get("response", {})
    if isinstance(extract_response, dict):
        print("\nExtract results:")
        for result in extract_response.get("results", []):
            content = result.get("raw_content", "") or result.get("content", "") or ""
            print(f"  URL: {result.get('url', '')}")
            print(f"  Extracted characters: {len(content)}")
            print(f"  Preview: {compact_text(content, 700)}")
        failed = extract_response.get("failed_results", [])
        if failed:
            print("\nExtract failures:")
            for item in failed:
                print(f"  {item}")
    elif "error" in extract:
        print(f"\nExtract error: {extract['error']}")

    found_urns: set[str] = set()
    for text in iter_text_for_identifier_scan(payload):
        found_urns.update(LINKEDIN_URN_RE.findall(text))

    print(f"\nTotal search results across all queries: {total_results}")
    if found_urns:
        print("LinkedIn URNs explicitly found in retrieved text:")
        for urn in sorted(found_urns):
            print(f"  {urn}")
    else:
        print("No LinkedIn URNs were explicitly found in retrieved text.")
        print("This does not prove the IDs do not exist; Tavily may not expose them.")

    print(f"\nFull response JSON saved to: {OUTPUT_PATH}")
    print("Note: search snippets/extracted text are not guaranteed to include all posts, comments, or IDs.")


def main() -> int:
    print("Tavily LinkedIn public-content retrieval test (read-only)")
    print(f"Script directory: {SCRIPT_DIR}")

    try:
        api_key = load_api_key()
        client = TavilyClient(api_key=api_key)
    except Exception as exc:
        print(f"SETUP ERROR: {exc}", file=sys.stderr)
        return 1

    started_at = datetime.now(timezone.utc).isoformat()
    payload: dict[str, Any] = {
        "started_at_utc": started_at,
        "profile_url": PROFILE_URL,
        "search_depth": SEARCH_DEPTH,
        "searches": [],
        "extract": {},
        "notes": [
            "Read-only test; no LinkedIn login, posting, commenting, or interaction is performed.",
            "Tavily returns only content its search/extraction service can access.",
            "Detected identifiers are copied from retrieved text; the script does not infer missing IDs.",
        ],
    }

    for query in SEARCH_QUERIES:
        payload["searches"].append(run_search(client, query))

    post_urls = collect_candidate_post_urls(payload["searches"])
    # Test direct extraction of the profile plus a small sample of discovered post URLs.
    urls_to_extract = [PROFILE_URL, *post_urls]
    payload["extract"] = run_extract(client, urls_to_extract)
    payload["finished_at_utc"] = datetime.now(timezone.utc).isoformat()

    try:
        OUTPUT_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"Could not write output JSON: {exc}", file=sys.stderr)

    print_summary(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
