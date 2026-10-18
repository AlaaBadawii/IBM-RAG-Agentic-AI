"""Versioned, JSON-serializable artifacts for one evaluation run.

An artifact is the durable answer to *"what did this experiment measure, from
which inputs, under which evaluator and rubric?"* Every field that establishes
provenance is present; every field the run could not know is explicitly
``None`` with a reason, never a fabricated zero.

Three rules this module holds to:

* **Missing is not zero.** :class:`MetricResult` carries ``value=None`` and an
  ``unavailable_reason`` when a metric could not be computed. A metric that was
  genuinely measured as ``0.0`` is a different thing and serializes as ``0.0``.
* **No clock, no environment.** Nothing here reads ``time`` or the environment;
  a caller that wants a timestamp passes one in. This mirrors the serializers in
  :mod:`app.verification.models` and :mod:`app.agent.models`.
* **Reuse the real serializers.** Where a case produced a live verdict, the
  artifact embeds :meth:`app.verification.models.VerificationResult.to_record`
  rather than a parallel shape.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

#: Bumped whenever the *shape* of an artifact changes. Distinct from the
#: evaluator version (what computed it) and the dataset version (the inputs).
#: v2 introduced per-metric population provenance, the renamed quality gate,
#: explicit finding counts, and known-limitation findings.
ARTIFACT_SCHEMA_VERSION = "2"

#: The sentinel written where a field is genuinely part of the schema but the
#: run did not have the information. Used in human-readable summaries only; the
#: structured artifacts use ``None`` plus a reason so a reader cannot mistake an
#: absence for a value.
UNAVAILABLE = "unavailable"


def _jsonable(value: Any) -> Any:
    """Coerce tuples/sets/nested dataclasses into JSON-safe values."""
    if isinstance(value, tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_jsonable(v) for v in value)
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return value


@dataclass(frozen=True)
class MetricResult:
    """One measured quantity, with its own sample accounting and provenance.

    ``value`` is ``None`` exactly when the metric was not computable for this
    run; ``unavailable_reason`` then says why. When it *is* computable,
    ``numerator``, ``denominator`` and ``sample_count`` are all present so a
    reader can re-derive the ratio instead of trusting a rounded float.

    The population fields answer *"over what, exactly?"*: ``unit`` names the
    counted thing (candidate or case), ``population`` describes the eligible
    set in words, ``population_case_ids`` names the fixtures that contributed,
    and ``excluded_case_ids`` names fixtures deliberately left out (for
    example, known-limitation probes, which are never scored).
    """

    name: str
    value: float | None
    numerator: int | None
    denominator: int | None
    sample_count: int
    unit: str = ""
    population: str = ""
    population_case_ids: tuple[str, ...] = ()
    excluded_case_ids: tuple[str, ...] = ()
    unavailable_reason: str | None = None
    notes: str = ""

    @property
    def available(self) -> bool:
        return self.value is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "sample_count": self.sample_count,
            "unit": self.unit,
            "population": self.population,
            "population_case_ids": list(self.population_case_ids),
            "excluded_case_ids": list(self.excluded_case_ids),
            "unavailable_reason": self.unavailable_reason,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class KnownLimitationFinding:
    """A fixture that probes a *known* weakness of the deterministic gate.

    A known-limitation probe is deliberately **not scored** and **not part of
    the quality gate**: its expectation is that a correct gate would reject a
    claim, while the current gate's documented behavior is that it does not.
    Recording it here keeps the weakness visible and measured without either
    (a) pretending the gate catches it or (b) encoding the miss as a desired
    outcome. ``escaped_detection`` is ``True`` when the claim passed the gate.
    """

    limitation_id: str
    case_id: str
    candidate_id: str | None
    description: str
    expectation: str
    observed: str
    escaped_detection: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "limitation_id": self.limitation_id,
            "case_id": self.case_id,
            "candidate_id": self.candidate_id,
            "description": self.description,
            "expectation": self.expectation,
            "observed": self.observed,
            "escaped_detection": self.escaped_detection,
        }


@dataclass(frozen=True)
class CandidateArtifact:
    """The measured fate of one offered candidate draft in one case."""

    candidate_id: str
    status: str
    """The reviewed preference label: ``preferred``/``acceptable``/
    ``unacceptable``/``unlabeled``."""
    verification_outcome: str | None
    publishable: bool | None
    citation_resolution: str
    """``resolved`` / ``unresolved`` / ``unavailable``."""
    violation_kinds: tuple[str, ...] = ()
    forbidden_inference_count: int = 0
    unsupported_reference_count: int = 0
    editorial_note_count: int = 0
    execution_status: str = "ok"
    error: str | None = None
    selection_status: str = "not_selected"
    """``selected`` / ``not_selected`` — whether this candidate is the one the
    deterministic pipeline would carry forward."""
    rationale: str = ""
    verification_record: dict[str, Any] | None = None
    """The embedded :meth:`VerificationResult.to_record` when a live verdict was
    produced; ``None`` for a synthetic case where none was run."""
    latency_ms: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return _jsonable(
            {
                "candidate_id": self.candidate_id,
                "status": self.status,
                "verification_outcome": self.verification_outcome,
                "publishable": self.publishable,
                "citation_resolution": self.citation_resolution,
                "violation_kinds": self.violation_kinds,
                "forbidden_inference_count": self.forbidden_inference_count,
                "unsupported_reference_count": self.unsupported_reference_count,
                "editorial_note_count": self.editorial_note_count,
                "execution_status": self.execution_status,
                "error": self.error,
                "selection_status": self.selection_status,
                "rationale": self.rationale,
                "verification_record": self.verification_record,
                "latency_ms": self.latency_ms,
            }
        )


@dataclass(frozen=True)
class CaseArtifact:
    """One frozen case, its candidates, and how the run scored it."""

    case_id: str
    split: str
    category: str
    expected_publish_appropriate: bool
    publish_appropriate_observed: bool | None
    publish_match: bool | None
    selected_candidate_id: str | None
    selected_status: str
    candidates: tuple[CandidateArtifact, ...] = ()
    missing: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return _jsonable(
            {
                "case_id": self.case_id,
                "split": self.split,
                "category": self.category,
                "expected_publish_appropriate": self.expected_publish_appropriate,
                "publish_appropriate_observed": self.publish_appropriate_observed,
                "publish_match": self.publish_match,
                "selected_candidate_id": self.selected_candidate_id,
                "selected_status": self.selected_status,
                "candidates": [c.as_dict() for c in self.candidates],
                "missing": self.missing,
                "notes": self.notes,
            }
        )


@dataclass(frozen=True)
class EvaluationArtifact:
    """A complete, reproducible record of one evaluation run.

    The version fields together answer *"which input, implementation and
    evaluator produced this?"* — dataset hash/version, evaluator version, rubric
    version, the baseline/candidate designation, and (when a model was actually
    invoked) the model id and effective parameters.
    """

    artifact_schema_version: str
    evaluator_version: str
    rubric_version: str
    dataset_version: str
    dataset_hash: str
    designation: str
    """``baseline`` or ``candidate``."""
    generated_at: str | None = None
    model_id: str | None = None
    model_parameters: dict[str, Any] | None = None
    prompt_version: str | None = None
    policy_version: str | None = None
    git_commit: str | None = None
    metrics: tuple[MetricResult, ...] = ()

    baseline_quality_gate_passed: bool | None = None
    """Whether the *evaluated outputs* were safe, over the scored cases.

    ``True`` means: no candidate was selected for a case the review marked
    not publish-appropriate; no selected candidate was marked unacceptable or
    carried a forbidden-inference or unsupported-reference finding.

    It does **not** mean "no unsafe claim existed in the fixtures" — unsafe
    drafts are offered on purpose and may be detected and blocked (see
    ``detected_*`` below). It also says nothing about isolation, which is a
    structural property of the Lab proven by
    ``tests/test_improvement_isolation.py``, not by this Boolean.
    """

    baseline_quality_gate_notes: tuple[str, ...] = ()
    """One note per reason the quality gate failed; empty when it passed."""

    detected_forbidden_inference_findings: int = 0
    """Candidates (scored) the gate *detected* with a forbidden inference."""

    detected_unsupported_reference_findings: int = 0
    """Candidates (scored) the gate *detected* with an unsupported reference."""

    selected_forbidden_inference_findings: int = 0
    """Forbidden-inference findings on a *selected* candidate (gate failure)."""

    selected_unsupported_reference_findings: int = 0
    """Unsupported-reference findings on a *selected* candidate (gate failure)."""

    unsafe_selection_case_ids: tuple[str, ...] = ()
    """Case ids where a selection tripped the quality gate."""

    known_limitations: tuple[KnownLimitationFinding, ...] = ()
    """Probes for documented gate weaknesses; never scored, never gated."""

    cases: tuple[CaseArtifact, ...] = ()
    limitations: tuple[str, ...] = ()

    @property
    def case_count(self) -> int:
        return len(self.cases)

    def metric(self, name: str) -> MetricResult | None:
        for m in self.metrics:
            if m.name == name:
                return m
        return None

    def as_dict(self) -> dict[str, Any]:
        return _jsonable(
            {
                "artifact_schema_version": self.artifact_schema_version,
                "evaluator_version": self.evaluator_version,
                "rubric_version": self.rubric_version,
                "dataset_version": self.dataset_version,
                "dataset_hash": self.dataset_hash,
                "designation": self.designation,
                "generated_at": self.generated_at,
                "provenance": {
                    "git_commit": self.git_commit,
                    "model_id": self.model_id,
                    "model_parameters": self.model_parameters,
                    "prompt_version": self.prompt_version,
                    "policy_version": self.policy_version,
                },
                "metrics": [m.as_dict() for m in self.metrics],
                "safety": {
                    "baseline_quality_gate_passed":
                        self.baseline_quality_gate_passed,
                    "baseline_quality_gate_notes":
                        list(self.baseline_quality_gate_notes),
                    "detected_forbidden_inference_findings":
                        self.detected_forbidden_inference_findings,
                    "detected_unsupported_reference_findings":
                        self.detected_unsupported_reference_findings,
                    "selected_forbidden_inference_findings":
                        self.selected_forbidden_inference_findings,
                    "selected_unsupported_reference_findings":
                        self.selected_unsupported_reference_findings,
                    "unsafe_selection_case_ids":
                        list(self.unsafe_selection_case_ids),
                    "isolation_note": (
                        "Isolation (no reachable store, network or model) is "
                        "established by tests/test_improvement_isolation.py; "
                        "these fields concern evaluated-output quality only."
                    ),
                },
                "known_limitations": [k.as_dict()
                                      for k in self.known_limitations],
                "cases": [c.as_dict() for c in self.cases],
                "limitations": self.limitations,
            }
        )

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.as_dict(), indent=indent, sort_keys=False)


def write_jsonl(path, records: Iterable[dict[str, Any]]) -> int:
    """Write records as JSONL, one per line. Returns the number written."""
    count = 0
    with open(path, "w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(_jsonable(record), sort_keys=True))
            fh.write("\n")
            count += 1
    return count
