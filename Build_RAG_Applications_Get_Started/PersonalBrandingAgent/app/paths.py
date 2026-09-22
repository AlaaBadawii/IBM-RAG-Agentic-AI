"""Canonical, working-directory-independent paths for the project.

Every module that touches the filesystem goes through here, so CLIs work
from any CWD (see Part 16 of the milestone spec).
"""
from pathlib import Path

# app/paths.py -> app/ -> PersonalBrandingAgent/
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
CHROMA_DIR = PROJECT_ROOT / "chroma_db"
LOG_DIR = PROJECT_ROOT / "logs"
GOLD_QUERIES_PATH = PROJECT_ROOT / "tests" / "gold_queries.json"

# Environment file. Loaded by path, never by CWD: a workflow started by a
# scheduler does not run from the project root (PLAN.md Step 5).
ENV_FILE = PROJECT_ROOT / ".env"

# The LinkedIn credential. Written by Auth_handling/linkedin_oauth_setup.py and
# read by everything else. Defined **once, here**, so the writer and the readers
# cannot drift apart — the defect Step 5 exists to fix was a token created in one
# directory and looked for in another. The three Auth_handling scripts resolve
# the same file relative to their own location; a test asserts the two agree.
LINKEDIN_TOKEN_FILE = PROJECT_ROOT / "Auth_handling" / "linkedin_tokens.json"

# The source registry: declarative configuration naming exactly which
# directories outside this project are evidence about the user. This is
# *definition*, not state — the last-processed revision for each source lives
# in the operational store's sync_checkpoints table, never here.
SOURCES_FILE = PROJECT_ROOT / "sources.yaml"

# Operational state (workflow runs, publish intents, publications, failures,
# notifications, locks). Deliberately NOT inside chroma_db/: knowledge state
# and operational state are separate stores with separate authority
# (PLAN.md §6). Gitignored like chroma_db/ and logs/, but unlike them it is
# NOT rebuildable — local publication history is authoritative (§5.1).
STATE_DB_DIR = PROJECT_ROOT / "state_db"
STATE_DB_PATH = STATE_DB_DIR / "operational_state.db"


def ensure_runtime_dirs() -> None:
    """Create runtime directories that the app may write to (idempotent)."""
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DB_DIR.mkdir(parents=True, exist_ok=True)
