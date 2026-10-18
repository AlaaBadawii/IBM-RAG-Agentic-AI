"""The Abu Prompt Improvement Lab: an offline, evidence-driven evaluation loop.

This package is deliberately *beside* the production pipeline, never inside it.
It exists so a proposed change to Abu Prompt can be measured against a frozen
reference set before anyone applies it, without the measurement itself being
able to publish, notify, or mutate operational state.

The boundary is the point
-------------------------

Nothing in this package may:

* import the publishing service, the LinkedIn client/publisher, the
  notification service, or a production workflow entry point;
* open the authoritative operational database, or any ``StateStore`` that
  would migrate it;
* make an external network call, or invoke a live model;
* write to production state.

Evidence is read from an explicit, consistent **copy** of the database that the
caller supplies, opened read-only. Every artifact records what it *does* not
know as explicitly unavailable rather than as a zero. The isolation boundary is
pinned by ``tests/test_improvement_isolation.py``.

This module is Stage 0 (the substrate) and, together with
``improvement/dataset``, Stage 1 (the frozen content-evaluation baseline) of the
approved self-improvement roadmap. It does **not** implement autonomous prompt
editing, candidate promotion, configuration switching, or code
self-modification. Generating a proposal does not authorize applying it.
"""
from app.improvement.artifacts import (
    ARTIFACT_SCHEMA_VERSION,
    CandidateArtifact,
    CaseArtifact,
    EvaluationArtifact,
    KnownLimitationFinding,
    MetricResult,
)
from app.improvement.dataset import (
    Candidate,
    Case,
    Dataset,
    DatasetError,
    load_dataset,
)
from app.improvement.evaluator import evaluate_dataset
from app.improvement.evidence import (
    SUPPORTED_SCHEMA_VERSION,
    EvidenceBundle,
    EvidenceError,
    collect_evidence,
    open_read_only,
    recorded_schema_version,
    snapshot_database,
)
from app.improvement.rubric import (
    HARD_GATE_METRICS,
    RUBRIC_VERSION,
    EvaluationRubric,
    default_rubric,
)

__all__ = [
    "ARTIFACT_SCHEMA_VERSION",
    "HARD_GATE_METRICS",
    "RUBRIC_VERSION",
    "SUPPORTED_SCHEMA_VERSION",
    "Candidate",
    "CandidateArtifact",
    "Case",
    "CaseArtifact",
    "Dataset",
    "DatasetError",
    "EvaluationArtifact",
    "EvaluationRubric",
    "EvidenceBundle",
    "EvidenceError",
    "KnownLimitationFinding",
    "MetricResult",
    "collect_evidence",
    "default_rubric",
    "evaluate_dataset",
    "load_dataset",
    "open_read_only",
    "recorded_schema_version",
    "snapshot_database",
]
