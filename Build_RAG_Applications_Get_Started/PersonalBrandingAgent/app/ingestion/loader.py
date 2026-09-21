"""Markdown discovery and loading over the knowledge base.

Policy: data/ is discovered recursively; each top-level directory under
data/ becomes the `category` metadata. Category README.md files are index
documents that duplicate content-file summaries — by default they are
EXCLUDED from the corpus (config.EXCLUDE_READMES) to keep retrieval results
free of index noise. The policy is explicit and reversible via env var.
"""
from dataclasses import dataclass
from pathlib import Path

from app.config import DATA_DIR, EXCLUDE_READMES
from app.errors import IngestionError
from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SourceFile:
    """A discovered Markdown file with its path-derived category and domain."""

    path: Path
    relative_path: str  # e.g. "evidence/backend/fastapi.md" (posix, from data/)

    @property
    def category(self) -> str:
        """Top-level directory under data/ (semantic class)."""
        parts = self.relative_path.split("/")
        return parts[0] if len(parts) > 1 else "root"

    @property
    def domain(self) -> str | None:
        """Second-level directory, only meaningful for evidence/ today."""
        parts = self.relative_path.split("/")
        if len(parts) > 2 and parts[0] == "evidence":
            return parts[1]
        return None

    def read_text(self) -> str:
        return self.path.read_text(encoding="utf-8")


def discover_markdown(data_dir: Path = DATA_DIR,
                      exclude_readmes: bool = EXCLUDE_READMES) -> list[SourceFile]:
    """Recursively find .md files under data_dir, sorted for determinism.

    Args:
        data_dir: knowledge base root.
        exclude_readmes: when True, skip category-index README.md files
            (any README.md inside data/). Their summaries duplicate the
            content files and add noise to retrieval results.
    """
    if not data_dir.is_dir():
        logger.warning("Data directory not found: %s", data_dir)
        return []

    files = []
    for path in sorted(data_dir.rglob("*.md")):
        if exclude_readmes and path.name.lower() == "readme.md":
            continue
        files.append(
            SourceFile(path=path, relative_path=path.relative_to(data_dir).as_posix())
        )
    logger.info("Discovered %d markdown files under %s", len(files), data_dir)
    return files


def load_all(files: list[SourceFile], *, strict: bool = False
             ) -> list[tuple[SourceFile, str]]:
    """Read every discovered file.

    Args:
        strict: when False (the default), an unreadable file is skipped with a
            warning — right for `data/`, a curated corpus where one damaged
            file should not stop the rest. When True, it raises instead, which
            is what the synchronization layer needs: a candidate set is a
            claim *about what changed*, and quietly indexing part of it would
            let a source's checkpoint advance past a file that never reached
            the index.
    """
    loaded = []
    for source in files:
        try:
            loaded.append((source, source.read_text()))
        except OSError as exc:
            if strict:
                raise IngestionError(
                    f"could not read {source.relative_path}: {exc}"
                ) from exc
            logger.warning("Could not read %s: %s", source.relative_path, exc)
    return loaded
