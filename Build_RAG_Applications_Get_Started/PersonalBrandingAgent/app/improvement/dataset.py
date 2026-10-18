"""The frozen content-evaluation dataset.

A *case* is a frozen decision scenario: an assembled evidence context, one or
more offered candidate drafts, and the reviewed expectations about which
outcomes are acceptable. The dataset is the reference an evaluation compares a
candidate implementation against.

Two properties matter and are enforced here:

* **Frozen and hashed.** :func:`load_dataset` computes a SHA-256 over the
  canonical JSON of the case block. Any change to fixture content changes the
  hash, so an artifact can always name the exact dataset it measured.
* **Reviewed, not single-answer.** Expectations distinguish *preferred*,
  *acceptable* and *unacceptable* candidates, and a case may legitimately admit
  several valid outcomes. The evaluator must not impose one right answer where
  several are defensible.

Contexts are built through the real :func:`app.context.builder.build_context`,
and candidates become real :class:`app.generation.models.GeneratedPost`s, so the
frozen fixtures exercise the same structures production does. No model is
called and no store is opened: the builder is handed an offline checkpoint stub
so it never reaches the authoritative database.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from app import paths as app_paths
from app.context.builder import build_context
from app.context.models import PersonalBrandingContext
from app.generation.models import EvidenceCitation, GeneratedPost
from app.retrieval.models import RetrievalResult, RetrievedDocument


class DatasetError(RuntimeError):
    """The dataset could not be loaded, or a fixture is malformed."""


class _OfflineCheckpointStore:
    """A store stand-in that reports no checkpoints.

    ``build_context`` reads synchronization checkpoints to build its
    source-state report. The Lab must not open the authoritative store to get
    them, and the frozen dataset does not depend on live freshness, so the
    builder is handed a store that knows nothing. It is not a ``StateStore`` and
    therefore cannot migrate anything.
    """

    def list_checkpoints(self) -> list:
        return []


@dataclass(frozen=True)
class Candidate:
    """One offered draft and the reviewed label it carries."""

    candidate_id: str
    content: str
    status: str = "unlabeled"
    rationale: str = ""
    cite: tuple[int, ...] = ()
    unresolved: tuple[str, ...] = ()
    foreign_citations: tuple[dict, ...] = ()

    def build_post(self, context: PersonalBrandingContext) -> GeneratedPost:
        items = context.evidence_items()
        citations: list[EvidenceCitation] = []
        for index in self.cite:
            if index < 1 or index > len(items):
                raise DatasetError(
                    f"candidate {self.candidate_id!r} cites index {index} "
                    f"but the context holds {len(items)} evidence item(s)"
                )
            item = items[index - 1]
            citations.append(EvidenceCitation(
                label=f"E{index}", source=item.source, chunk_id=item.chunk_id,
                evidence_state=item.evidence_state,
            ))
        for foreign in self.foreign_citations:
            citations.append(EvidenceCitation(
                label=str(foreign["label"]),
                source=str(foreign["source"]),
                chunk_id=str(foreign["chunk_id"]),
                evidence_state=foreign.get("evidence_state"),
            ))
        return GeneratedPost(
            content=self.content,
            citations=tuple(citations),
            unresolved_labels=self.unresolved,
        )


@dataclass(frozen=True)
class Expected:
    """The reviewed expectations for one case.

    ``publish_appropriate`` is the headline: should *any* candidate here reach
    a publish? The three candidate-id sets encode the reviewed preference:
    preferred (best), acceptable (defensible), unacceptable (must never be
    selected).
    """

    publish_appropriate: bool
    valid_outcomes: tuple[str, ...] = ()
    preferred: tuple[str, ...] = ()
    acceptable: tuple[str, ...] = ()
    unacceptable: tuple[str, ...] = ()
    explanation: str = ""


@dataclass(frozen=True)
class Case:
    """One frozen scenario."""

    case_id: str
    split: str
    category: str
    description: str
    provenance: dict
    query: str
    documents: tuple[dict, ...]
    candidates: tuple[Candidate, ...]
    expected: Expected
    known_limitation: dict | None = None
    """When set, this case is a probe for a documented gate weakness.

    Probes are evaluated (so the weakness is *observed*, not asserted) but are
    excluded from every scored metric and from the quality gate.
    """

    def build_context(self) -> PersonalBrandingContext:
        retrieved = []
        for index, raw in enumerate(self.documents, start=1):
            metadata = {
                "source": raw["source"],
                "category": raw["category"],
                "document_type": raw.get("document_type", "unknown"),
                "content_hash": raw["chunk_id"].split(":")[0],
            }
            if raw.get("evidence_state") is not None:
                metadata["evidence_state"] = raw["evidence_state"]
            retrieved.append(RetrievedDocument(
                content=raw["content"],
                score=float(raw.get("score", 0.5)),
                source=raw["source"],
                metadata=metadata,
                strategy=raw.get("strategy", "vector"),
                chunk_id=raw["chunk_id"],
                rank=index,
            ))
        return build_context(
            RetrievalResult(query=self.query, strategy="vector",
                            documents=retrieved, diagnostics={}),
            store=_OfflineCheckpointStore(),
        )

    def candidate(self, candidate_id: str) -> Candidate | None:
        for candidate in self.candidates:
            if candidate.candidate_id == candidate_id:
                return candidate
        return None


@dataclass(frozen=True)
class Dataset:
    """The frozen reference set, with a content hash."""

    dataset_version: str
    rubric_version: str
    cases: tuple[Case, ...]
    dataset_hash: str
    path: str = ""

    def case_ids(self) -> tuple[str, ...]:
        return tuple(c.case_id for c in self.cases)

    def case(self, case_id: str) -> Case:
        for c in self.cases:
            if c.case_id == case_id:
                return c
        raise KeyError(case_id)

    def split(self, name: str) -> tuple[Case, ...]:
        return tuple(c for c in self.cases if c.split == name)

    def categories(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for c in self.cases:
            counts[c.category] = counts.get(c.category, 0) + 1
        return counts


def _require(mapping: dict, key: str, where: str) -> object:
    if key not in mapping:
        raise DatasetError(f"{where} is missing required key {key!r}")
    return mapping[key]


def _validate_provenance(case_id: str, provenance: dict,
                         project_root: Path) -> None:
    sources = provenance.get("sources")
    if not isinstance(sources, list) or not sources:
        raise DatasetError(f"case {case_id!r} has no provenance sources")
    for source in sources:
        rel = _require(source, "path", f"case {case_id!r} source")
        expected = _require(source, "sha256", f"case {case_id!r} source")
        target = project_root / rel
        if not target.is_file():
            raise DatasetError(
                f"case {case_id!r} references missing provenance file {rel!r}"
            )
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != expected:
            raise DatasetError(
                f"case {case_id!r} provenance hash mismatch for {rel!r}: "
                f"recorded {expected[:12]}…, file is {actual[:12]}… "
                "(bump the dataset version when a source changes)"
            )


def _case_from_raw(raw: dict, project_root: Path) -> Case:
    case_id = str(_require(raw, "case_id", "case"))
    provenance = dict(_require(raw, "provenance", f"case {case_id!r}"))
    _validate_provenance(case_id, provenance, project_root)

    context_raw = dict(_require(raw, "context", f"case {case_id!r}"))
    documents = tuple(dict(d) for d in context_raw.get("documents", []))

    candidates_raw = _require(raw, "candidates", f"case {case_id!r}")
    candidates = tuple(
        Candidate(
            candidate_id=str(_require(c, "candidate_id", f"case {case_id!r}")),
            content=str(_require(c, "content", f"case {case_id!r}")),
            status=str(c.get("status", "unlabeled")),
            rationale=str(c.get("rationale", "")),
            cite=tuple(int(i) for i in c.get("cite", ())),
            unresolved=tuple(str(u) for u in c.get("unresolved", ())),
            foreign_citations=tuple(dict(f) for f in c.get("foreign_citations", ())),
        )
        for c in candidates_raw
    )

    expected_raw = dict(_require(raw, "expected", f"case {case_id!r}"))
    expected = Expected(
        publish_appropriate=bool(
            _require(expected_raw, "publish_appropriate", f"case {case_id!r}")
        ),
        valid_outcomes=tuple(str(o) for o in expected_raw.get("valid_outcomes", ())),
        preferred=tuple(str(x) for x in expected_raw.get("preferred", ())),
        acceptable=tuple(str(x) for x in expected_raw.get("acceptable", ())),
        unacceptable=tuple(str(x) for x in expected_raw.get("unacceptable", ())),
        explanation=str(expected_raw.get("explanation", "")),
    )

    known_limitation = raw.get("known_limitation")
    if known_limitation is not None and not isinstance(known_limitation, dict):
        raise DatasetError(
            f"case {case_id!r} known_limitation must be an object"
        )

    return Case(
        case_id=case_id,
        split=str(raw.get("split", "development")),
        category=str(raw.get("category", "unclassified")),
        description=str(raw.get("description", "")),
        provenance=provenance,
        query=str(context_raw.get("query", "")),
        documents=documents,
        candidates=candidates,
        expected=expected,
        known_limitation=dict(known_limitation) if known_limitation else None,
    )


def compute_dataset_hash(cases_block: list[dict]) -> str:
    """SHA-256 over the canonical JSON of the case block."""
    canonical = json.dumps(cases_block, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_dataset(path: Path | str) -> Dataset:
    """Load and validate a frozen dataset file."""
    path = Path(path)
    if not path.is_file():
        raise DatasetError(f"dataset file not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DatasetError(f"dataset {path} is not valid JSON: {exc}") from exc

    cases_block = _require(raw, "cases", "dataset")
    if not isinstance(cases_block, list) or not cases_block:
        raise DatasetError("dataset has no cases")

    cases = tuple(
        _case_from_raw(entry, app_paths.PROJECT_ROOT) for entry in cases_block
    )
    seen: set[str] = set()
    for case in cases:
        if case.case_id in seen:
            raise DatasetError(f"duplicate case_id {case.case_id!r}")
        seen.add(case.case_id)

    return Dataset(
        dataset_version=str(raw.get("dataset_version", "unversioned")),
        rubric_version=str(raw.get("rubric_version", "unversioned")),
        cases=cases,
        dataset_hash=compute_dataset_hash(cases_block),
        path=str(path),
    )
