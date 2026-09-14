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


def ensure_runtime_dirs() -> None:
    """Create runtime directories that the app may write to (idempotent)."""
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
