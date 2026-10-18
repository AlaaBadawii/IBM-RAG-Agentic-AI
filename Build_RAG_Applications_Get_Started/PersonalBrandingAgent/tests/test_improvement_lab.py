"""Focused tests for the Improvement Lab (Stage 0 substrate, Stage 1 baseline).

The Lab is an offline evaluation loop that must be *deterministic*, *honest
about what it could not measure*, and *incapable of touching production*. Each
test below pins one of those properties:

1.  the dataset is frozen — its content hash changes when a fixture changes;
2.  provenance hashes are verified against the real corpus, and a mismatch
    refuses the load;
3.  the development/held-out split is explicit and selectable;
4.  the evaluator runs the real context builder and the real gate, model-free;
5.  evaluation is deterministic — two runs are byte-identical;
6.  metrics are reported separately and are never summed;
7.  an uncomputable metric is ``None`` with a reason, never ``0.0``;
8.  the hard safety gate fails a run whose selection is unacceptable;
9.  the CLI exits non-zero when the gate fails;
10. the candidate provider is a seam that changes inputs, not the evaluator;
11. artifacts are JSON-serializable and embed the real verification record;
12. baseline-vs-candidate manifests pre-register the hypothesis and criteria.
"""
import json
from pathlib import Path

import pytest

from app.improvement.artifacts import MetricResult
from app.improvement.dataset import DatasetError, load_dataset
from app.improvement.evaluator import evaluate_dataset
from app.improvement.manifest import build_experiment_manifest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "improvement" / "dataset" / "content_eval_v1.json"

#: A real corpus file, and its real SHA-256, for building tiny valid datasets.
REAL_SOURCE = "data/evidence/README.md"
REAL_SOURCE_HASH = (
    "6912568adcaabbe80a8c5d4dc2789b6ea2cfc949ea20501500ce66d716838778"
)


def _write_dataset(tmp_path: Path, cases: list[dict], *,
                   version: str = "test-v1") -> Path:
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps({
        "dataset_version": version,
        "rubric_version": "content-rubric-v1",
        "cases": cases,
    }), encoding="utf-8")
    return path


def _case(case_id: str, *, content: str, cite: list[int] | None = None,
          expected_publish: bool = True, status: str = "preferred",
          unacceptable: list[str] | None = None, split: str = "development",
          category: str = "strong_narrative") -> dict:
    return {
        "case_id": case_id,
        "split": split,
        "category": category,
        "description": "a focused fixture",
        "provenance": {
            "kind": "constructed",
            "sources": [{"path": REAL_SOURCE, "sha256": REAL_SOURCE_HASH}],
        },
        "context": {
            "query": "evidence",
            "documents": [{
                "source": REAL_SOURCE,
                "category": "evidence",
                "chunk_id": "abcd0001:0",
                "content": "Evidence is what the corpus records.",
            }],
        },
        "candidates": [{
            "candidate_id": f"{case_id}-c1",
            "content": content,
            "cite": cite or [],
            "status": status,
        }],
        "expected": {
            "publish_appropriate": expected_publish,
            "unacceptable": unacceptable or [],
        },
    }


# 1 ------------------------------------------------------------------------
def test_dataset_hash_changes_when_a_fixture_changes(tmp_path):
    first = load_dataset(_write_dataset(tmp_path, [_case("c1", content="A.")]))
    second = load_dataset(_write_dataset(tmp_path, [_case("c1", content="B.")]))
    assert first.dataset_hash != second.dataset_hash


def test_frozen_dataset_loads_with_a_stable_hash():
    dataset = load_dataset(DATASET_PATH)
    assert len(dataset.cases) == 23
    assert len(dataset.split("development")) == 16
    assert len(dataset.split("held_out")) == 6
    assert len(dataset.split("known_limitation")) == 1
    assert dataset.dataset_version == "content-eval-v1"
    assert load_dataset(DATASET_PATH).dataset_hash == dataset.dataset_hash


# 2 ------------------------------------------------------------------------
def test_provenance_hash_mismatch_refuses_the_load(tmp_path):
    case = _case("c1", content="A.")
    case["provenance"]["sources"][0]["sha256"] = "0" * 64
    with pytest.raises(DatasetError, match="provenance hash mismatch"):
        load_dataset(_write_dataset(tmp_path, [case]))


def test_provenance_requires_the_source_to_exist(tmp_path):
    case = _case("c1", content="A.")
    case["provenance"]["sources"][0]["path"] = "data/does_not_exist.md"
    with pytest.raises(DatasetError, match="missing provenance file"):
        load_dataset(_write_dataset(tmp_path, [case]))


# 3 ------------------------------------------------------------------------
def test_splits_are_explicit_and_selectable(tmp_path):
    cases = [
        _case("dev-1", content="A.", split="development"),
        _case("dev-2", content="B.", split="development"),
        _case("held-1", content="C.", split="held_out"),
    ]
    dataset = load_dataset(_write_dataset(tmp_path, cases))
    assert len(dataset.split("development")) == 2
    assert len(dataset.split("held_out")) == 1

    artifact = evaluate_dataset(dataset, split="held_out")
    assert {c.case_id for c in artifact.cases} == {"held-1"}


def test_frozen_dataset_split_sizes():
    dataset = load_dataset(DATASET_PATH)
    assert len(dataset.split("development")) == 16
    assert len(dataset.split("held_out")) == 6

# 4 ------------------------------------------------------------------------
def test_evaluation_uses_the_real_gate_and_context(tmp_path):
    """A real ``GeneratedPost`` is verified and the verdict is embedded."""
    dataset = load_dataset(_write_dataset(
        tmp_path, [_case("c1", content="The takeaway matters more "
                                   "than the tool.")]))
    artifact = evaluate_dataset(dataset)
    candidate = artifact.cases[0].candidates[0]
    assert candidate.execution_status == "ok"
    record = candidate.verification_record
    assert record is not None
    # The embedded record is the real VerificationResult.to_record shape.
    assert set(record) >= {
        "outcome", "evidence_status", "editorial_notes", "violations",
        "evidence",
    }
    assert candidate.verification_outcome == record["outcome"]


def test_summary_claims_are_model_free():
    """No model identifier is recorded by this stage."""
    dataset = load_dataset(DATASET_PATH)
    artifact = evaluate_dataset(dataset)
    assert artifact.model_id is None
    assert artifact.prompt_version is None


# 5 ------------------------------------------------------------------------
def test_evaluation_is_deterministic():
    dataset = load_dataset(DATASET_PATH)
    first = evaluate_dataset(dataset)
    second = evaluate_dataset(dataset)
    assert first.to_json() == second.to_json()


def test_selection_ignores_reviewed_labels(tmp_path):
    """Selection is the first gate-passing candidate, not the labelled one."""
    passing = "The takeaway matters more than the tool."
    case = _case("c1", content=passing, status="unacceptable",
                 unacceptable=["c1-c1"], expected_publish=False)
    case["candidates"].append({
        "candidate_id": "c1-c2", "content": passing, "cite": [],
        "status": "preferred",
    })
    dataset = load_dataset(_write_dataset(tmp_path, [case]))
    artifact = evaluate_dataset(dataset)
    # The first offered candidate passes, so it is selected -- even though the
    # review marks it unacceptable. That is exactly what the gate must catch.
    assert artifact.cases[0].selected_candidate_id == "c1-c1"


# 6 ------------------------------------------------------------------------
def test_metrics_are_separate_and_never_summed():
    dataset = load_dataset(DATASET_PATH)
    artifact = evaluate_dataset(dataset)
    names = [m.name for m in artifact.metrics]
    assert len(names) == len(set(names)) == 9
    assert "total_score" not in names


# 7 ------------------------------------------------------------------------
def test_uncomputable_metric_is_none_not_zero(tmp_path):
    """No publish-appropriate case => selection_agreement is unavailable."""
    case = _case("c1", content="The takeaway matters more than the tool.",
                 expected_publish=False, category="catalog_only")
    dataset = load_dataset(_write_dataset(tmp_path, [case]))
    artifact = evaluate_dataset(dataset)
    metric = artifact.metric("selection_agreement_rate")
    assert metric.value is None
    assert metric.denominator == 0
    assert metric.unavailable_reason


def test_metric_result_factory_shape():
    measured = MetricResult(
        name="x", value=0.0, numerator=0, denominator=5, sample_count=5)
    unavailable = MetricResult(
        name="y", value=None, numerator=None, denominator=0, sample_count=0,
        unavailable_reason="nothing to measure")
    assert measured.available and measured.value == 0.0
    assert not unavailable.available and unavailable.value is None


# 8 ------------------------------------------------------------------------
def test_hard_gate_fails_when_an_unacceptable_candidate_is_selected(tmp_path):
    """A gate-passing draft the review forbids must fail the whole run."""
    case = _case(
        "gate-case",
        content="The takeaway matters more than the tool.",
        status="unacceptable", unacceptable=["gate-case-c1"],
        expected_publish=False)
    dataset = load_dataset(_write_dataset(tmp_path, [case]))
    artifact = evaluate_dataset(dataset)
    assert artifact.baseline_quality_gate_passed is False
    assert any("unacceptable" in note
               for note in artifact.baseline_quality_gate_notes)
    assert any("BASELINE QUALITY GATE FAILED" in lim
               for lim in artifact.limitations)
    assert artifact.unsafe_selection_case_ids == ("gate-case",)


# 9 ------------------------------------------------------------------------
def test_cli_exit_code_is_nonzero_on_gate_failure(tmp_path):
    from app.improvement.__main__ import main

    case = _case(
        "gate-case",
        content="The takeaway matters more than the tool.",
        status="unacceptable", unacceptable=["gate-case-c1"],
        expected_publish=False)
    dataset_path = _write_dataset(tmp_path, [case])
    code = main([
        "evaluate", "--dataset", str(dataset_path),
        "--out", str(tmp_path / "artifacts"), "--quiet",
    ])
    assert code == 2


def test_cli_exit_code_is_zero_on_a_clean_run(tmp_path):
    from app.improvement.__main__ import main

    dataset = load_dataset(DATASET_PATH)
    code = main([
        "evaluate", "--dataset", str(DATASET_PATH),
        "--out", str(tmp_path / "artifacts"), "--quiet",
    ])
    assert code == 0
    written = json.loads(
        (tmp_path / "artifacts" / "baseline.artifact.json").read_text())
    assert written["safety"]["baseline_quality_gate_passed"] is True
    assert len(written["cases"]) == len(dataset.cases)


# 10 -----------------------------------------------------------------------
def test_candidate_provider_is_a_substitutable_seam(tmp_path):
    class EmptyProvider:
        name = "empty"

        def candidates_for(self, case):
            return ()

    dataset = load_dataset(_write_dataset(
        tmp_path, [_case("c1", content="A.")]))
    artifact = evaluate_dataset(dataset, provider=EmptyProvider())
    case = artifact.cases[0]
    assert case.selected_candidate_id is None
    assert case.candidates == ()
    assert case.missing == ("candidates",)


# 11 -----------------------------------------------------------------------
def test_artifact_is_json_serializable_with_provenance():
    dataset = load_dataset(DATASET_PATH)
    artifact = evaluate_dataset(dataset, git_commit="deadbeef")
    payload = json.loads(artifact.to_json())
    assert payload["dataset_hash"] == dataset.dataset_hash
    assert payload["rubric_version"] == "content-rubric-v1"
    assert payload["evaluator_version"] == "content-eval-v1"
    assert payload["provenance"]["git_commit"] == "deadbeef"
    assert len(payload["metrics"]) == 9
    # A measured metric carries numerator/denominator, not just a float.
    measured = next(m for m in payload["metrics"] if m["value"] is not None)
    assert measured["numerator"] is not None
    assert measured["denominator"] is not None


# 12 -----------------------------------------------------------------------
def test_experiment_manifest_preregisters_and_flags_dataset_identity():
    dataset = load_dataset(DATASET_PATH)
    baseline = evaluate_dataset(dataset, designation="baseline")
    candidate = evaluate_dataset(dataset, designation="candidate")
    manifest = build_experiment_manifest(
        baseline, candidate,
        hypothesis="A tightening of the citation rule reduces false passes.",
        accept_criteria=("forbidden_inference_rate must not rise",),
        reject_criteria=("any hard gate fails",),
        split="development",
    )
    assert manifest["hypothesis"].startswith("A tightening")
    assert manifest["accept_criteria"] == [
        "forbidden_inference_rate must not rise"]
    assert manifest["dataset"]["same_dataset"] is True
    # Nothing about results is pre-baked: the manifest names the inputs only.
    assert manifest["baseline"]["dataset_hash"] == baseline.dataset_hash
    assert manifest["candidate"]["designation"] == "candidate"


def test_experiment_manifest_flags_a_changed_dataset(tmp_path):
    dataset = load_dataset(DATASET_PATH)
    baseline = evaluate_dataset(dataset, designation="baseline")
    other = load_dataset(_write_dataset(tmp_path, [_case("c1", content="A.")]))
    candidate = evaluate_dataset(other, designation="candidate")
    manifest = build_experiment_manifest(
        baseline, candidate, hypothesis="h")
    assert manifest["dataset"]["same_dataset"] is False


# --- denominator reconciliation & population provenance --------------------
def test_metric_denominators_are_reconciled_and_provenanced():
    """Every denominator is explained by its declared population and ids."""
    dataset = load_dataset(DATASET_PATH)
    artifact = evaluate_dataset(dataset)

    expected = {
        # metric name: (unit, expected denominator)
        "decision_schema_valid_rate": ("candidate", 25),
        "citation_resolution_rate": ("candidate that cited", 23),
        "verification_pass_rate": ("candidate", 25),
        "forbidden_inference_rate": ("candidate", 25),
        "unsupported_reference_rate": ("candidate", 25),
        "insufficient_evidence_handling_rate": ("case", 2),
        "malformed_handling_rate": ("case", 3),
        "selection_agreement_rate": ("case", 11),
        "publish_decision_agreement_rate": ("case", 22),
    }
    for name, (unit, denominator) in expected.items():
        metric = artifact.metric(name)
        assert metric.unit == unit, name
        assert metric.denominator == denominator, name
        assert metric.sample_count == denominator, name
        # The declared population ids are exactly as many as the denominator,
        # except for candidate metrics where one case may offer >1 candidate.
        if unit == "case":
            assert len(metric.population_case_ids) == denominator, name
        else:
            assert metric.population_case_ids, name
        assert metric.population, name


def test_metric_case_ids_are_subsets_of_scored_cases():
    """No metric population reaches the known-limitation probe."""
    dataset = load_dataset(DATASET_PATH)
    scored = {c.case_id for c in dataset.cases if c.known_limitation is None}
    artifact = evaluate_dataset(dataset)
    for metric in artifact.metrics:
        assert set(metric.population_case_ids) <= scored, metric.name
        assert "probe-bare-count-undetected" in metric.excluded_case_ids \
            or metric.excluded_case_ids == ()


def test_each_candidate_is_counted_once_per_candidate_metric():
    """Candidate denominators equal the number of offered candidates."""
    dataset = load_dataset(DATASET_PATH)
    offered = sum(len(c.candidates) for c in dataset.cases
                  if c.known_limitation is None)
    artifact = evaluate_dataset(dataset)
    assert artifact.metric("verification_pass_rate").denominator == offered


def test_publish_decision_agreement_is_agreement_with_reviewed_decision(tmp_path):
    """The metric's contract: agreement with the reviewed publish/no-publish
    decision over every scored case -- not a judgement of a draft's quality and
    not selection agreement.

    With nothing selected, drafts that the review also said not to publish
    still *agree*; the metric tracks the decision, not the draft.
    """

    class EmptyProvider:
        name = "empty"

        def candidates_for(self, case):
            return ()

    cases = [
        _case("wants-publish", content="A.", expected_publish=True),
        _case("wants-silence", content="B.", expected_publish=False),
        _case("also-silent", content="C.", expected_publish=False),
    ]
    dataset = load_dataset(_write_dataset(tmp_path, cases))
    artifact = evaluate_dataset(dataset, provider=EmptyProvider())

    # Renamed: the old ambiguous name is gone, the contract name is present.
    assert artifact.metric("publish_appropriateness_rate") is None
    metric = artifact.metric("publish_decision_agreement_rate")
    assert metric is not None

    # Numerator is exactly the number of scored cases whose observed decision
    # equals the reviewed expected decision.
    matches = sum(
        1 for c in artifact.cases
        if c.publish_appropriate_observed == c.expected_publish_appropriate
    )
    assert metric.numerator == matches == 2  # 2 silent cases agree, 1 disagrees
    assert metric.denominator == 3
    assert metric.unit == "case"
    assert metric.population == "every scored case"


# --- safety Boolean disambiguation & finding counts ------------------------
def test_quality_gate_is_not_the_isolation_check():
    """The gate describes output quality; isolation is documented separately."""
    dataset = load_dataset(DATASET_PATH)
    artifact = evaluate_dataset(dataset)
    safety = artifact.as_dict()["safety"]
    assert "baseline_quality_gate_passed" in safety
    assert "safety_gate_passed" not in safety
    assert "isolation" in safety["isolation_note"].lower()


def test_detected_findings_are_distinguished_from_selected_findings():
    """Detected-and-blocked findings do not fail the gate; selected do."""
    dataset = load_dataset(DATASET_PATH)
    artifact = evaluate_dataset(dataset)
    assert artifact.detected_forbidden_inference_findings >= 1
    assert artifact.baseline_quality_gate_passed is True
    assert artifact.selected_forbidden_inference_findings == 0
    assert artifact.selected_unsupported_reference_findings == 0
    assert artifact.unsafe_selection_case_ids == ()


def test_editorial_metrics_cannot_offset_a_gate_failure(tmp_path):
    """A gate failure leaves the run invalid whatever the other metrics say."""
    case = _case(
        "gate-case",
        content="The takeaway matters more than the tool.",
        status="unacceptable", unacceptable=["gate-case-c1"],
        expected_publish=False)
    dataset = load_dataset(_write_dataset(tmp_path, [case]))
    artifact = evaluate_dataset(dataset)
    # Selection agreement is trivially 1.0 here (or unavailable), yet the run
    # is still invalid because the quality gate failed.
    assert artifact.baseline_quality_gate_passed is False


# --- known-limitation probe ------------------------------------------------
def test_known_limitation_probe_is_reported_and_not_scored():
    dataset = load_dataset(DATASET_PATH)
    probe = next(c for c in dataset.cases if c.known_limitation is not None)
    artifact = evaluate_dataset(dataset)
    finding = next(k for k in artifact.known_limitations
                   if k.case_id == probe.case_id)
    assert finding.limitation_id == "bare-count-undetected"
    assert finding.escaped_detection is True
    # The probe is excluded from every metric and from the gate.
    assert "probe-bare-count-undetected" not in {
        cid for m in artifact.metrics for cid in m.population_case_ids}
    assert artifact.baseline_quality_gate_passed is True
    assert any("known-limitation" in lim for lim in artifact.limitations)


def test_known_limitation_probe_is_a_single_candidate_escape():
    dataset = load_dataset(DATASET_PATH)
    artifact = evaluate_dataset(dataset)
    assert len(artifact.known_limitations) == 1
    assert artifact.known_limitations[0].escaped_detection is True


# --- acceptance criterion 7: fixtures and rubric are not writable ----------
def test_evaluation_does_not_modify_fixtures_or_rubric():
    before = DATASET_PATH.read_bytes()
    dataset = load_dataset(DATASET_PATH)
    dataset_hash_before = dataset.dataset_hash
    evaluate_dataset(dataset)
    assert DATASET_PATH.read_bytes() == before
    assert dataset.dataset_hash == dataset_hash_before

    # The rubric and the frozen case/candidate types are immutable.
    from dataclasses import FrozenInstanceError

    from app.improvement.dataset import Candidate, Case
    from app.improvement.rubric import EvaluationRubric, default_rubric

    rubric = default_rubric()
    assert isinstance(rubric, EvaluationRubric)
    with pytest.raises(FrozenInstanceError):
        rubric.version = "tampered"
    assert Case.__dataclass_params__.frozen
    assert Candidate.__dataclass_params__.frozen


# --- acceptance criterion 10: held-out split is selectable/excluded --------
def test_probe_and_held_out_are_excluded_by_split_selection():
    dataset = load_dataset(DATASET_PATH)
    dev = evaluate_dataset(dataset, split="development")
    ids = {c.case_id for c in dev.cases}
    probe = next(c.case_id for c in dataset.cases
                 if c.known_limitation is not None)
    assert probe not in ids
    assert not (ids & {c.case_id for c in dataset.split("held_out")})


# --- acceptance criterion 11: private outputs are not tracked by Git -------
def test_lab_outputs_are_git_ignored():
    import subprocess

    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "improvement/artifacts/*" in gitignore
    assert "!improvement/artifacts/.gitkeep" in gitignore
    assert "improvement/evidence/" in gitignore

    repo_root = PROJECT_ROOT.parent.parent  # monorepo root
    artifact = (
        "Build_RAG_Applications_Get_Started/PersonalBrandingAgent/"
        "improvement/artifacts/baseline.artifact.json")
    done = subprocess.run(
        ["git", "check-ignore", artifact], cwd=str(repo_root),
        capture_output=True, text=True, check=False)
    if done.returncode in (0, 1):
        assert done.returncode == 0, "artifact path must be git-ignored"
    else:  # pragma: no cover - git always available in this repo
        pytest.skip("git not available to confirm ignore rules")
