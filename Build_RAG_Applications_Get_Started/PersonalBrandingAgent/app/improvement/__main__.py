"""Command-line entry point for the Improvement Lab.

    python -m app.improvement collect  --source <db> --dest <dir>
    python -m app.improvement evaluate [--dataset <file>] [--split <name>]
                                       [--designation baseline|candidate]
                                       [--out <dir>] [--quiet]

``collect`` snapshots an explicitly provided database and exports the
allowlisted evidence fields. ``evaluate`` runs the offline baseline evaluator
over the frozen dataset and writes a JSON artifact, a JSONL case log, a manifest
and a short human-readable summary.

Neither command can publish, notify, or write production state.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app import paths as app_paths
from app.improvement.dataset import load_dataset
from app.improvement.evaluator import evaluate_dataset
from app.improvement.evidence import collect_evidence
from app.improvement.manifest import build_baseline_manifest, write_manifest

DEFAULT_DATASET = (app_paths.PROJECT_ROOT / "improvement" / "dataset"
                   / "content_eval_v1.json")
DEFAULT_ARTIFACTS_DIR = app_paths.PROJECT_ROOT / "improvement" / "artifacts"


def _cmd_collect(args: argparse.Namespace) -> int:
    bundle = collect_evidence(args.source, args.dest)
    print(f"snapshotted {bundle.source_path}")
    print(f"  copy:            {bundle.copy_path}")
    print(f"  schema version:  {bundle.schema_version}")
    for table in bundle.tables_available:
        print(f"  exported {table}: {bundle.counts.get(table, 0)} row(s)")
    for table in bundle.tables_unavailable:
        print(f"  unavailable {table}")
    return 0


def _cmd_evaluate(args: argparse.Namespace) -> int:
    dataset = load_dataset(args.dataset)
    artifact = evaluate_dataset(
        dataset,
        designation=args.designation,
        split=args.split,
        git_commit=args.git_commit,
        prompt_version=args.prompt_version,
        policy_version=args.policy_version,
        generated_at=args.generated_at,
    )

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = out_dir / f"{args.designation}.artifact.json"
    artifact_path.write_text(artifact.to_json(), encoding="utf-8")

    case_log = out_dir / f"{args.designation}.cases.jsonl"
    with open(case_log, "w", encoding="utf-8") as fh:
        for case in artifact.cases:
            fh.write(json.dumps(case.as_dict(), sort_keys=True))
            fh.write("\n")

    manifest_path = write_manifest(
        out_dir / f"{args.designation}.manifest.json",
        build_baseline_manifest(artifact),
    )

    if not args.quiet:
        _print_summary(artifact)
    print(f"\nwrote {artifact_path}")
    print(f"wrote {case_log}")
    print(f"wrote {manifest_path}")
    return 0 if artifact.baseline_quality_gate_passed else 2


def _print_summary(artifact) -> None:
    scored = artifact.metric("publish_decision_agreement_rate")
    scored_cases = len(scored.population_case_ids) if scored else 0
    probes = len(artifact.known_limitations)
    print("=" * 72)
    print(f"CONTENT EVALUATION  designation={artifact.designation}  "
          f"cases={scored_cases} scored"
          + (f" (+{probes} known-limitation probe(s))" if probes else ""))
    print(f"dataset={artifact.dataset_version}@{artifact.dataset_hash[:12]}  "
          f"rubric={artifact.rubric_version}")
    print("=" * 72)
    print(f"{'metric':<40} {'value':>8} {'n/d':>12}")
    print("-" * 72)
    for metric in artifact.metrics:
        if metric.available:
            value = f"{metric.value:.3f}"
            nd = f"{metric.numerator}/{metric.denominator}"
        else:
            value = "n/a"
            nd = f"-/{metric.denominator}"
        print(f"{metric.name:<40} {value:>8} {nd:>12}")
    print("-" * 72)
    gate = "PASS" if artifact.baseline_quality_gate_passed else "FAIL"
    print(f"baseline quality gate: {gate}")
    for note in artifact.baseline_quality_gate_notes:
        print(f"  - {note}")
    print(f"detected findings: forbidden_inference="
          f"{artifact.detected_forbidden_inference_findings}, "
          f"unsupported_reference="
          f"{artifact.detected_unsupported_reference_findings}")
    print(f"selected findings (gate failures): forbidden_inference="
          f"{artifact.selected_forbidden_inference_findings}, "
          f"unsupported_reference="
          f"{artifact.selected_unsupported_reference_findings}")
    print(f"known-limitation probes: {len(artifact.known_limitations)}")
    for probe in artifact.known_limitations:
        state = "ESCAPED" if probe.escaped_detection else "detected"
        print(f"  - {probe.limitation_id} [{state}]: {probe.observed}")
    print("limitations:")
    for limitation in artifact.limitations:
        print(f"  - {limitation}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.improvement")
    sub = parser.add_subparsers(dest="command", required=True)

    collect = sub.add_parser("collect", help="snapshot + export evidence")
    collect.add_argument("--source", required=True,
                         help="explicit operational database to snapshot")
    collect.add_argument("--dest", required=True,
                         help="private directory for the copy and exports")
    collect.set_defaults(func=_cmd_collect)

    evaluate = sub.add_parser("evaluate", help="run the offline baseline")
    evaluate.add_argument("--dataset", default=str(DEFAULT_DATASET))
    evaluate.add_argument("--split", default=None)
    evaluate.add_argument("--designation", default="baseline",
                          choices=("baseline", "candidate"))
    evaluate.add_argument("--out", default=str(DEFAULT_ARTIFACTS_DIR))
    evaluate.add_argument("--git-commit", default=None)
    evaluate.add_argument("--prompt-version", default=None)
    evaluate.add_argument("--policy-version", default=None)
    evaluate.add_argument("--generated-at", default=None)
    evaluate.add_argument("--quiet", action="store_true")
    evaluate.set_defaults(func=_cmd_evaluate)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
