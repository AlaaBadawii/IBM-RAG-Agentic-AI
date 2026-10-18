"""The offline baseline evaluator.

Given a frozen :class:`~app.improvement.dataset.Dataset`, this runs the
deterministic parts of the real pipeline over each case — building the real
context, building the real :class:`GeneratedPost`, and calling the real
:func:`app.verification.verifier.verify` — and reports a set of metrics kept
deliberately separate.

It cannot publish, notify, or write production state. It never calls a model in
this stage. The candidate drafts come from a *provider*; the default provider
returns the drafts frozen in the dataset, and a later stage can substitute a
provider that generates drafts from a candidate prompt. The evaluator itself is
unchanged by that substitution, which is what makes a later baseline-vs-candidate
comparison meaningful.

Selection is deterministic and independent of the reviewed labels: the selected
candidate is the **first offered candidate that passes verification**. Offered
order is therefore part of the frozen input, and the selection-agreement metric
checks whether that choice lands on a reviewed preferred/acceptable candidate.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from app.improvement.artifacts import (
    ARTIFACT_SCHEMA_VERSION,
    CandidateArtifact,
    CaseArtifact,
    EvaluationArtifact,
    KnownLimitationFinding,
    MetricResult,
)
from app.improvement.dataset import Candidate, Case, Dataset
from app.improvement.rubric import (
    CITATION_RESOLUTION_RATE,
    DECISION_SCHEMA_VALID_RATE,
    FORBIDDEN_INFERENCE_RATE,
    INSUFFICIENT_EVIDENCE_HANDLING_RATE,
    MALFORMED_HANDLING_RATE,
    PUBLISH_DECISION_AGREEMENT_RATE,
    SELECTION_AGREEMENT_RATE,
    UNSUPPORTED_REFERENCE_RATE,
    VERIFICATION_PASS_RATE,
    EvaluationRubric,
    default_rubric,
)
from app.verification.enums import ViolationKind
from app.verification.errors import VerificationError
from app.verification.verifier import verify

#: Identifies the evaluator implementation that produced an artifact.
EVALUATOR_VERSION = "content-eval-v1"

_PREFERENCE_STATUSES = {"preferred", "acceptable"}


class CandidateProvider(Protocol):
    """Supplies the offered candidate drafts for one case.

    The frozen provider returns the dataset's drafts; a future provider may
    generate drafts from a candidate prompt. Implementations must be pure with
    respect to production: no publishing, no notifications, no state writes.
    """

    name: str

    def candidates_for(self, case: Case) -> tuple[Candidate, ...]:
        ...


@dataclass(frozen=True)
class FrozenCandidateProvider:
    """The default provider: the drafts frozen in the dataset itself."""

    name: str = "frozen"

    def candidates_for(self, case: Case) -> tuple[Candidate, ...]:
        return case.candidates


def evaluate_dataset(dataset: Dataset, *,
                     designation: str = "baseline",
                     rubric: EvaluationRubric | None = None,
                     provider: CandidateProvider | None = None,
                     generated_at: str | None = None,
                     git_commit: str | None = None,
                     model_id: str | None = None,
                     model_parameters: dict | None = None,
                     prompt_version: str | None = None,
                     policy_version: str | None = None,
                     split: str | None = None,
                     ) -> EvaluationArtifact:
    """Evaluate ``dataset`` and return a reproducible artifact.

    ``split`` limits evaluation to one split (e.g. reject the held-out split
    from candidate development). By default every case is evaluated.
    """
    rubric = rubric or default_rubric()
    provider = provider or FrozenCandidateProvider()

    cases = dataset.cases if split is None else dataset.split(split)

    case_artifacts: list[CaseArtifact] = []
    counters = _new_counters()
    gate_notes: list[str] = []
    unsafe_sample = {"selected_forbidden": 0, "selected_unsupported": 0}
    known_limitations: list[KnownLimitationFinding] = []
    unsafe_case_ids: list[str] = []

    excluded_case_ids: list[str] = []
    for case in cases:
        if case.known_limitation is not None:
            artifact, finding = _evaluate_probe(case, provider)
            case_artifacts.append(artifact)
            known_limitations.append(finding)
            excluded_case_ids.append(case.case_id)
            continue
        artifact, case_counters, case_gate_notes, case_unsafe_ids, selected = (
            _evaluate_case(case, provider, rubric))
        case_artifacts.append(artifact)
        _merge_counters(counters, case_counters)
        gate_notes.extend(case_gate_notes)
        unsafe_case_ids.extend(case_unsafe_ids)
        unsafe_sample["selected_forbidden"] += selected[0]
        unsafe_sample["selected_unsupported"] += selected[1]

    metrics = _build_metrics(counters, excluded_case_ids=excluded_case_ids)
    quality_gate_passed = not gate_notes

    return EvaluationArtifact(
        artifact_schema_version=ARTIFACT_SCHEMA_VERSION,
        evaluator_version=EVALUATOR_VERSION,
        rubric_version=rubric.version,
        dataset_version=dataset.dataset_version,
        dataset_hash=dataset.dataset_hash,
        designation=designation,
        generated_at=generated_at,
        model_id=model_id,
        model_parameters=model_parameters,
        prompt_version=prompt_version,
        policy_version=policy_version,
        git_commit=git_commit,
        metrics=tuple(metrics),
        baseline_quality_gate_passed=quality_gate_passed,
        baseline_quality_gate_notes=tuple(gate_notes),
        detected_forbidden_inference_findings=counters["candidates_forbidden"],
        detected_unsupported_reference_findings=(
            counters["candidates_unsupported"]),
        selected_forbidden_inference_findings=unsafe_sample["selected_forbidden"],
        selected_unsupported_reference_findings=(
            unsafe_sample["selected_unsupported"]),
        unsafe_selection_case_ids=tuple(sorted(set(unsafe_case_ids))),
        known_limitations=tuple(known_limitations),
        cases=tuple(case_artifacts),
        limitations=_limitations(gate_notes, known_limitations),
    )


# --------------------------------------------------------------- internals ---

def _new_counters() -> dict:
    return {
        "candidates_total": 0,
        "candidates_schema_valid": 0,
        "candidates_with_citations": 0,
        "candidates_resolved": 0,
        "candidates_pass": 0,
        "candidates_forbidden": 0,
        "candidates_unsupported": 0,
        "cases_total": 0,
        "cases_publish_expected": 0,
        "selection_agreement": 0,
        "cases_publish_match": 0,
        "insufficient_expected": 0,
        "insufficient_handled": 0,
        "malformed_expected": 0,
        "malformed_handled": 0,
        # Fixture ids contributing to each metric population, so a denominator
        # can be audited back to the exact cases that produced it.
        "ids_candidates": set(),
        "ids_citations": set(),
        "ids_publish_expected": set(),
        "ids_insufficient": set(),
        "ids_malformed": set(),
        "ids_scored_cases": set(),
    }


def _merge_counters(target: dict, addition: dict) -> None:
    for key, value in addition.items():
        if isinstance(value, set):
            target[key] |= value
        else:
            target[key] += value


def _evaluate_case(case: Case, provider: CandidateProvider,
                   rubric: EvaluationRubric):
    counters = _new_counters()
    counters["cases_total"] = 1
    counters["ids_scored_cases"].add(case.case_id)
    gate_notes: list[str] = []
    unsafe_ids: list[str] = []
    selected_flags = [0, 0]

    try:
        context = case.build_context()
    except Exception as exc:  # noqa: BLE001 - a broken fixture is a finding
        candidate_artifacts = ()
        missing = ("context",)
        notes = (f"context could not be built: {exc}",)
        return (
            CaseArtifact(
                case_id=case.case_id, split=case.split, category=case.category,
                expected_publish_appropriate=case.expected.publish_appropriate,
                publish_appropriate_observed=None, publish_match=None,
                selected_candidate_id=None, selected_status="none",
                candidates=(), missing=missing, notes=notes,
            ),
            counters, gate_notes, unsafe_ids, selected_flags,
        )

    offered = provider.candidates_for(case)
    candidate_artifacts: list[CandidateArtifact] = []
    selected_id: str | None = None
    selected_status = "none"
    candidate_forbidden = 0
    candidate_unsupported = 0

    for candidate in offered:
        counters["candidates_total"] += 1
        counters["ids_candidates"].add(case.case_id)
        candidate_artifact, publishable = _evaluate_candidate(candidate, context)
        candidate_artifacts.append(candidate_artifact)
        if publishable:
            counters["candidates_pass"] += 1
        if candidate_artifact.execution_status == "ok":
            counters["candidates_schema_valid"] += 1
        if candidate_artifact.forbidden_inference_count:
            counters["candidates_forbidden"] += 1
        if candidate_artifact.unsupported_reference_count:
            counters["candidates_unsupported"] += 1
        if candidate.cite or candidate.unresolved or candidate.foreign_citations:
            counters["candidates_with_citations"] += 1
            counters["ids_citations"].add(case.case_id)
            if candidate_artifact.citation_resolution == "resolved":
                counters["candidates_resolved"] += 1
        if selected_id is None and publishable:
            selected_id = candidate.candidate_id
            selected_status = candidate.status
            candidate_forbidden = candidate_artifact.forbidden_inference_count
            candidate_unsupported = (
                candidate_artifact.unsupported_reference_count)

    observed_publish = selected_id is not None
    case_counters = dict(counters)

    # Publish-appropriateness: did the pipeline's decision match the review?
    if observed_publish == case.expected.publish_appropriate:
        case_counters["cases_publish_match"] = 1

    # Selection agreement: only meaningful where a publish is appropriate.
    if case.expected.publish_appropriate:
        case_counters["cases_publish_expected"] = 1
        case_counters["ids_publish_expected"].add(case.case_id)
        if selected_id is not None and selected_status in _PREFERENCE_STATUSES:
            case_counters["selection_agreement"] = 1

    # Negative-case handling.
    if not case.expected.publish_appropriate and case.category == "insufficient_evidence":
        case_counters["insufficient_expected"] = 1
        case_counters["ids_insufficient"].add(case.case_id)
        if selected_id is None:
            case_counters["insufficient_handled"] = 1
    if case.category == "malformed_reasoner":
        case_counters["malformed_expected"] = 1
        case_counters["ids_malformed"].add(case.case_id)
        if selected_id is None:
            case_counters["malformed_handled"] = 1

    # The quality gate: an unacceptable candidate must never be selected, a
    # case that should not publish must never select anything, and a selected
    # candidate must carry no forbidden-inference or unsupported-reference
    # finding. A detected-and-blocked finding is *not* a gate failure.
    failed = False
    if selected_id is not None and selected_id in case.expected.unacceptable:
        gate_notes.append(
            f"{case.case_id}: selected candidate {selected_id} is marked "
            "unacceptable by the reviewed rubric"
        )
        failed = True
    if selected_id is not None and not case.expected.publish_appropriate:
        gate_notes.append(
            f"{case.case_id}: a candidate was selected but the case is marked "
            "not publish-appropriate"
        )
        failed = True
    if selected_id is not None and candidate_forbidden:
        gate_notes.append(
            f"{case.case_id}: selected candidate {selected_id} carries "
            "a forbidden-inference finding"
        )
        selected_flags[0] = candidate_forbidden
        failed = True
    if selected_id is not None and candidate_unsupported:
        gate_notes.append(
            f"{case.case_id}: selected candidate {selected_id} carries "
            "an unsupported-reference finding"
        )
        selected_flags[1] = candidate_unsupported
        failed = True
    if failed:
        unsafe_ids.append(case.case_id)

    # Label which candidate the pipeline selected.
    labelled = tuple(
        replace(ca, selection_status=(
            "selected" if ca.candidate_id == selected_id else "not_selected"))
        for ca in candidate_artifacts
    )

    missing = ()
    if not offered:
        missing = ("candidates",)

    artifact = CaseArtifact(
        case_id=case.case_id,
        split=case.split,
        category=case.category,
        expected_publish_appropriate=case.expected.publish_appropriate,
        publish_appropriate_observed=observed_publish,
        publish_match=(observed_publish == case.expected.publish_appropriate),
        selected_candidate_id=selected_id,
        selected_status=selected_status,
        candidates=labelled,
        missing=missing,
        notes=(case.expected.explanation,) if case.expected.explanation else (),
    )
    return artifact, case_counters, gate_notes, unsafe_ids, selected_flags


def _evaluate_probe(case: Case, provider: CandidateProvider):
    """Evaluate a known-limitation probe, recording whether the gate caught it.

    A probe is measured so the documented weakness is *observed* rather than
    merely asserted, but it is never scored and never gates: its reviewed
    expectation is exactly what the current gate is known not to deliver.
    """
    limitation = case.known_limitation or {}
    limitation_id = str(limitation.get("id", case.case_id))
    expectation = str(limitation.get("expectation", case.expected.explanation))
    target_id = limitation.get("candidate_id")

    try:
        context = case.build_context()
    except Exception as exc:  # noqa: BLE001 - a broken probe is still a finding
        artifact = CaseArtifact(
            case_id=case.case_id, split=case.split, category=case.category,
            expected_publish_appropriate=case.expected.publish_appropriate,
            publish_appropriate_observed=None, publish_match=None,
            selected_candidate_id=None, selected_status="none",
            candidates=(), missing=("context",),
            notes=(f"context could not be built: {exc}",),
        )
        return artifact, KnownLimitationFinding(
            limitation_id=limitation_id, case_id=case.case_id,
            candidate_id=target_id, description=case.description,
            expectation=expectation,
            observed="context could not be built; probe inconclusive",
            escaped_detection=False,
        )

    offered = provider.candidates_for(case)
    candidate_artifacts: list[CandidateArtifact] = []
    target = None
    escaped = False
    selected_id: str | None = None
    for candidate in offered:
        candidate_artifact, publishable = _evaluate_candidate(candidate, context)
        candidate_artifacts.append(candidate_artifact)
        if selected_id is None and publishable:
            selected_id = candidate.candidate_id
        is_target = (target_id is None or candidate.candidate_id == target_id)
        if is_target and target is None:
            target = candidate_artifact
            escaped = publishable

    labelled = tuple(
        replace(ca, selection_status=(
            "selected" if ca.candidate_id == selected_id else "not_selected"))
        for ca in candidate_artifacts
    )
    artifact = CaseArtifact(
        case_id=case.case_id, split=case.split, category=case.category,
        expected_publish_appropriate=case.expected.publish_appropriate,
        publish_appropriate_observed=selected_id is not None,
        publish_match=None,
        selected_candidate_id=selected_id, selected_status="probe",
        candidates=labelled, missing=(),
        notes=(f"known limitation probe: {limitation_id}",),
    )
    outcome = (target.verification_outcome if target is not None else "no target")
    observed = (
        f"deterministic gate returned {outcome} "
        f"(publishable={escaped}); the claim was "
        + ("NOT detected" if escaped else "detected")
    )
    return artifact, KnownLimitationFinding(
        limitation_id=limitation_id, case_id=case.case_id,
        candidate_id=(target.candidate_id if target is not None else target_id),
        description=case.description, expectation=expectation,
        observed=observed, escaped_detection=escaped,
    )


def _evaluate_candidate(candidate: Candidate, context):
    try:
        post = candidate.build_post(context)
    except Exception as exc:  # noqa: BLE001 - a malformed candidate is a finding
        return (
            CandidateArtifact(
                candidate_id=candidate.candidate_id, status=candidate.status,
                verification_outcome=None, publishable=None,
                citation_resolution="unavailable",
                execution_status="error", error=str(exc),
                rationale=candidate.rationale,
            ),
            False,
        )

    try:
        result = verify(post, context)
    except VerificationError as exc:
        return (
            CandidateArtifact(
                candidate_id=candidate.candidate_id, status=candidate.status,
                verification_outcome=None, publishable=None,
                citation_resolution="unavailable",
                execution_status="error", error=str(exc),
                rationale=candidate.rationale,
            ),
            False,
        )
    except Exception as exc:  # noqa: BLE001 - never let a case abort the run
        return (
            CandidateArtifact(
                candidate_id=candidate.candidate_id, status=candidate.status,
                verification_outcome=None, publishable=None,
                citation_resolution="unavailable",
                execution_status="error", error=repr(exc),
                rationale=candidate.rationale,
            ),
            False,
        )

    kinds = tuple(sorted({v.kind.value for v in result.all_violations}))
    forbidden = sum(1 for v in result.all_violations
                    if v.kind is ViolationKind.FORBIDDEN_INFERENCE)
    unsupported = sum(1 for v in result.all_violations
                      if v.kind is ViolationKind.UNSUPPORTED_REFERENCE)

    cited = bool(post.citations) or bool(post.unresolved_labels)
    if not cited:
        resolution = "unavailable"
    elif (ViolationKind.CITATION_NOT_IN_CONTEXT.value in kinds
          or post.unresolved_labels):
        resolution = "unresolved"
    else:
        resolution = "resolved"

    artifact = CandidateArtifact(
        candidate_id=candidate.candidate_id,
        status=candidate.status,
        verification_outcome=result.outcome.value,
        publishable=result.is_publishable,
        citation_resolution=resolution,
        violation_kinds=kinds,
        forbidden_inference_count=forbidden,
        unsupported_reference_count=unsupported,
        editorial_note_count=len(result.editorial_notes),
        execution_status="ok",
        rationale=candidate.rationale,
        verification_record=result.to_record(),
    )
    return artifact, result.is_publishable


def _rate(name: str, numerator: int, denominator: int, *, unit: str,
          population: str, population_case_ids: set[str],
          excluded_case_ids: tuple[str, ...], unavailable_reason: str,
          notes: str = "") -> MetricResult:
    ids = tuple(sorted(population_case_ids))
    if denominator <= 0:
        return MetricResult(
            name=name, value=None, numerator=None,
            denominator=0, sample_count=0,
            unit=unit, population=population, population_case_ids=ids,
            excluded_case_ids=excluded_case_ids,
            unavailable_reason=unavailable_reason, notes=notes,
        )
    return MetricResult(
        name=name, value=numerator / denominator, numerator=numerator,
        denominator=denominator, sample_count=denominator,
        unit=unit, population=population, population_case_ids=ids,
        excluded_case_ids=excluded_case_ids, notes=notes,
    )


def _build_metrics(c: dict, *, excluded_case_ids: list[str]
                   ) -> list[MetricResult]:
    excluded = tuple(sorted(excluded_case_ids))

    def candidate_ids():
        return c["ids_candidates"]

    return [
        _rate(
            DECISION_SCHEMA_VALID_RATE,
            c["candidates_schema_valid"], c["candidates_total"],
            unit="candidate", population="every offered candidate (scored cases)",
            population_case_ids=candidate_ids(), excluded_case_ids=excluded,
            unavailable_reason="no candidates were offered",
            notes="post + verification produced a structured result",
        ),
        _rate(
            CITATION_RESOLUTION_RATE,
            c["candidates_resolved"], c["candidates_with_citations"],
            unit="candidate that cited",
            population="offered candidates that cited any evidence",
            population_case_ids=c["ids_citations"], excluded_case_ids=excluded,
            unavailable_reason="no candidate cited evidence",
            notes="citations resolved against the offered context",
        ),
        _rate(
            VERIFICATION_PASS_RATE,
            c["candidates_pass"], c["candidates_total"],
            unit="candidate", population="every offered candidate (scored cases)",
            population_case_ids=candidate_ids(), excluded_case_ids=excluded,
            unavailable_reason="no candidates were offered",
            notes="deterministic gate PASS rate over all offered candidates",
        ),
        _rate(
            FORBIDDEN_INFERENCE_RATE,
            c["candidates_forbidden"], c["candidates_total"],
            unit="candidate", population="every offered candidate (scored cases)",
            population_case_ids=candidate_ids(), excluded_case_ids=excluded,
            unavailable_reason="no candidates were offered",
            notes="lower is better; detection, not escape",
        ),
        _rate(
            UNSUPPORTED_REFERENCE_RATE,
            c["candidates_unsupported"], c["candidates_total"],
            unit="candidate", population="every offered candidate (scored cases)",
            population_case_ids=candidate_ids(), excluded_case_ids=excluded,
            unavailable_reason="no candidates were offered",
            notes="lower is better; detection, not escape",
        ),
        _rate(
            INSUFFICIENT_EVIDENCE_HANDLING_RATE,
            c["insufficient_handled"], c["insufficient_expected"],
            unit="case",
            population=("scored insufficient_evidence cases expected not to "
                        "publish"),
            population_case_ids=c["ids_insufficient"],
            excluded_case_ids=excluded,
            unavailable_reason="no insufficient-evidence case in the split",
            notes="fraction of insufficient-evidence cases that published nothing",
        ),
        _rate(
            MALFORMED_HANDLING_RATE,
            c["malformed_handled"], c["malformed_expected"],
            unit="case", population="scored malformed_reasoner cases",
            population_case_ids=c["ids_malformed"], excluded_case_ids=excluded,
            unavailable_reason="no malformed-output case in the split",
            notes="fraction of malformed cases that published nothing",
        ),
        _rate(
            SELECTION_AGREEMENT_RATE,
            c["selection_agreement"], c["cases_publish_expected"],
            unit="case",
            population="scored cases the review marks publish-appropriate",
            population_case_ids=c["ids_publish_expected"],
            excluded_case_ids=excluded,
            unavailable_reason="no publish-appropriate case in the split",
            notes="selected candidate was preferred or acceptable",
        ),
        _rate(
            PUBLISH_DECISION_AGREEMENT_RATE,
            c["cases_publish_match"], c["cases_total"],
            unit="case", population="every scored case",
            population_case_ids=c["ids_scored_cases"],
            excluded_case_ids=excluded,
            unavailable_reason="no cases were evaluated",
            notes="pipeline publish/no-publish matched the reviewed expectation",
        ),
    ]


def _limitations(gate_notes: list[str],
                 known_limitations: list[KnownLimitationFinding]
                 ) -> tuple[str, ...]:
    limitations = [
        (
            "Offline and model-free: this stage evaluates frozen candidate "
            "drafts, not live model output. It measures the deterministic "
            "gate, not the generator."
        ),
        (
            "No engagement metric is available: the repository's metrics-import "
            "facility exists but no engagement data has been collected, and "
            "publication_metrics is decision-free by design."
        ),
        (
            "Per-case verification verdicts for historical production runs were "
            "never persisted, so historical cases are represented by "
            "constructed fixtures rather than replayed verdicts."
        ),
        (
            "The dataset is small and inspectable; it is not statistically "
            "representative of all future production cases."
        ),
        (
            "The deterministic gate uses exact-string matching; it does not "
            "detect a bare count with no unit (for example '5 IBM "
            "certificates'). See known_limitations for probes of this."
        ),
    ]
    if known_limitations:
        escaped = [k for k in known_limitations if k.escaped_detection]
        limitations.append(
            f"{len(known_limitations)} known-limitation probe(s) were run, "
            f"{len(escaped)} of which the gate failed to detect; probes are "
            "excluded from every scored metric and from the quality gate."
        )
    if gate_notes:
        limitations.append(
            f"BASELINE QUALITY GATE FAILED with {len(gate_notes)} finding(s); "
            "the run is invalid regardless of other metrics."
        )
    return tuple(limitations)
