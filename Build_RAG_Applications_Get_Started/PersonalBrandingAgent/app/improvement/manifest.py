"""Baseline and experiment manifests.

A manifest is the small, human-readable header that travels with an artifact:
what was run, against which frozen inputs, under which versions, in which
environment. It is intentionally not a place for results — results live in the
artifact — only the facts needed to reproduce and to compare two runs.

Nothing here runs a model, opens a store, or touches the network.
"""
from __future__ import annotations

import json
import platform
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

from app.improvement.artifacts import EvaluationArtifact

#: Packages whose version materially affects reproducibility of the corpus and
#: the model calls. Recorded when installed; absence is recorded as unavailable.
TRACKED_PACKAGES = (
    "google-genai",
    "chromadb",
    "langchain",
    "langchain-chroma",
    "langchain-huggingface",
    "sentence-transformers",
)


def collect_environment() -> dict[str, Any]:
    """A minimal, offline environment snapshot."""
    packages: dict[str, str | None] = {}
    for name in TRACKED_PACKAGES:
        try:
            packages[name] = importlib_metadata.version(name)
        except importlib_metadata.PackageNotFoundError:
            packages[name] = None
    return {
        "python_version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "packages": packages,
    }


def build_baseline_manifest(artifact: EvaluationArtifact, *,
                            environment: dict | None = None) -> dict[str, Any]:
    """The manifest for one evaluated designation (baseline or candidate)."""
    return {
        "manifest_version": "1",
        "designation": artifact.designation,
        "git_commit": artifact.git_commit,
        "dataset_version": artifact.dataset_version,
        "dataset_hash": artifact.dataset_hash,
        "rubric_version": artifact.rubric_version,
        "evaluator_version": artifact.evaluator_version,
        "artifact_schema_version": artifact.artifact_schema_version,
        "prompt_version": artifact.prompt_version,
        "policy_version": artifact.policy_version,
        "model": {
            "model_id": artifact.model_id,
            "model_parameters": artifact.model_parameters,
        },
        "generated_at": artifact.generated_at,
        "case_count": artifact.case_count,
        "baseline_quality_gate_passed": artifact.baseline_quality_gate_passed,
        "detected_forbidden_inference_findings":
            artifact.detected_forbidden_inference_findings,
        "detected_unsupported_reference_findings":
            artifact.detected_unsupported_reference_findings,
        "selected_forbidden_inference_findings":
            artifact.selected_forbidden_inference_findings,
        "selected_unsupported_reference_findings":
            artifact.selected_unsupported_reference_findings,
        "known_limitation_count": len(artifact.known_limitations),
        "environment": environment if environment is not None
        else collect_environment(),
    }


def build_experiment_manifest(baseline: EvaluationArtifact,
                              candidate: EvaluationArtifact, *,
                              hypothesis: str,
                              accept_criteria: tuple[str, ...] = (),
                              reject_criteria: tuple[str, ...] = (),
                              split: str | None = None,
                              ) -> dict[str, Any]:
    """The manifest describing a baseline-versus-candidate comparison.

    It records the *pre-registered* hypothesis and the accept/reject criteria so
    a result cannot be reinterpreted after the fact. It does not run anything.
    """
    return {
        "manifest_version": "1",
        "kind": "baseline_vs_candidate",
        "hypothesis": hypothesis,
        "accept_criteria": list(accept_criteria),
        "reject_criteria": list(reject_criteria),
        "split": split,
        "dataset": {
            "version": baseline.dataset_version,
            "hash": baseline.dataset_hash,
            "same_dataset": baseline.dataset_hash == candidate.dataset_hash,
        },
        "rubric_version": baseline.rubric_version,
        "baseline": build_baseline_manifest(baseline),
        "candidate": build_baseline_manifest(candidate),
    }


def write_manifest(path: Path | str, manifest: dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=False),
                    encoding="utf-8")
    return path
