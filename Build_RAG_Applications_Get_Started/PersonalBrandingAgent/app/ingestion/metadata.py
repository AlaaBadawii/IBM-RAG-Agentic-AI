"""Metadata extraction rules — deliberately conservative.

Only metadata that can be RELIABLY derived is included. Two sources are
trusted:

1. Path structure (loader.SourceFile.category / .domain):
       evidence/backend/fastapi.md -> category=evidence, domain=backend
2. Explicit document headings with a known vocabulary:
       "## Status"       -> COMPLETED | IN PROGRESS | ...
       "## Evidence state" -> VERIFIED | DOCUMENTED | IN_PROGRESS | ...
       "## Story strength"  -> STRONG | MEDIUM | ...

Everything else is left UNSET. The evidence-state vocabulary comes from
data/evidence/README.md; the status vocabulary from the corpus's own
"## Status" headings. Where a heading is ambiguous or missing, the field
stays None rather than being guessed.
"""
import re
from dataclasses import dataclass, field

from app.ingestion.loader import SourceFile

# --- Vocabularies (mirrors the real corpus; see data/evidence/README.md) ---
EVIDENCE_STATES = {
    "VERIFIED", "DOCUMENTED", "IN_PROGRESS", "LEARNING",
    "ASPIRATIONAL", "UNVERIFIED", "STALE",
}
STATUS_VALUES = {
    "COMPLETED", "IN PROGRESS", "IN-PROGRESS", "PLANNED", "LEARNING",
    "ASPIRATIONAL", "DOCUMENTED", "PAUSED",
}

# Heading -> (metadata field, allowed vocabulary) for single-line values.
_HEADING_RULES = {
    "evidence state": ("evidence_state", EVIDENCE_STATES),
    "status": ("status", STATUS_VALUES),
}


@dataclass
class DocumentMetadata:
    """Derived metadata for one source document.

    `document_type` is derived from the category path (reliable), never
    guessed from content. `status`/`evidence_state` come only from explicit
    headings. `project` is derived only for single-project files where the
    slug is unambiguous (e.g. stories_lessons/quizey_idempotency.md).
    """

    source: str
    category: str
    domain: str | None = None
    document_type: str | None = None
    status: str | None = None
    evidence_state: str | None = None
    project: str | None = None
    content_hash: str = ""
    extra: dict = field(default_factory=dict)

    def to_chroma_metadata(self) -> dict:
        """Chroma metadata cannot be None — drop unset fields."""
        meta = {
            "source": self.source,
            "category": self.category,
            "document_type": self.document_type or "unknown",
        }
        if self.domain:
            meta["domain"] = self.domain
        if self.status:
            meta["status"] = self.status
        if self.evidence_state:
            meta["evidence_state"] = self.evidence_state
        if self.project:
            meta["project"] = self.project
        meta["content_hash"] = self.content_hash
        return meta


# category -> document_type (from the directory semantics, per
# docs/architecture/rag-architecture.md).
_CATEGORY_DOCUMENT_TYPES = {
    "completed_projects": "project",
    "in_progress_projects": "project",
    "in_progress_courses": "course",
    "certificates": "certificate",
    "evidence": "evidence",
    "stories_lessons": "lesson",
    "vision_goals": "vision",
    "writing_style": "writing_style",
    "public_positioning": "positioning",
    "audit": "audit",
}


def _extract_heading_value(text: str, heading: str) -> str | None:
    """Return the first line after a '## <heading>' heading, if any.

    Only single-line, immediately-following values are trusted. Bulleted or
    paragraph 'status' sections are ignored (would be guessing).
    """
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*\n+\s*([^\n]+)", re.IGNORECASE | re.MULTILINE
    )
    match = pattern.search(text)
    if not match:
        return None
    value = match.group(1).strip().strip("*_`")
    return value or None


def _derive_project(source: SourceFile) -> str | None:
    """Derive a project slug only for clearly single-project file names.

    E.g. stories_lessons/quizey_idempotency.md -> "quizey";
    completed_projects/airbnb_clone.md -> "airbnb_clone". Multi-topic files
    (e.g. certificates) return None.
    """
    stem = source.path.stem
    if source.category in {"stories_lessons", "completed_projects", "in_progress_projects"}:
        # Only project-prefixed story files get a project slug.
        for prefix in ("quizey", "fastapi"):
            if stem.lower().startswith(prefix):
                return prefix
    return None


def extract_metadata(source: SourceFile, text: str, content_hash: str) -> DocumentMetadata:
    """Derive metadata for one document from path + explicit headings."""
    meta = DocumentMetadata(
        source=source.relative_path,
        category=source.category,
        domain=source.domain,
        document_type=_CATEGORY_DOCUMENT_TYPES.get(source.category),
        project=_derive_project(source),
        content_hash=content_hash,
    )
    for heading, (field_name, vocabulary) in _HEADING_RULES.items():
        raw = _extract_heading_value(text, heading)
        if raw is None:
            continue
        # Real corpus values come in three shapes:
        #   "VERIFIED (repo exists)"            — keyword + parenthetical
        #   "COMPLETED (implemented, locally)"  — keyword + parenthetical
        #   "IN PROGRESS. The re-architecture…" — keyword + sentence
        # Trust only the leading keyword if it is in the vocabulary.
        normalized = raw.upper().replace("-", " ").strip()
        leading = normalized.split("(")[0].split(".")[0].strip()
        if leading in vocabulary:
            setattr(meta, field_name, leading)
    return meta
