"""Import post engagement metrics from a platform export, safely.

The system makes no live external calls, so metrics arrive as a CSV a person
exports and hands over. This module is that handover, and it is built to make
a mistake harmless:

* **Parse, validate, then write.** A bad row fails the whole parse, so a file
  with one mistyped number imports *nothing* rather than importing the rest
  and leaving a half-applied reading.
* **Every publication must exist.** A ``publication_id`` the store does not
  hold is an error, checked before any write, so a metric cannot point at
  nothing.
* **Dry run by default.** ``apply_plan`` writes only when asked; the CLI's
  ``--apply`` is the explicit ask. Without it, ``python -m
  app.metrics.import_metrics FILE`` prints exactly what it *would* record.

CSV shape — header row required; ``publication_id`` and ``age_hours`` are
required, the rest default to zero::

    publication_id,age_hours,impressions,reactions,comments,reposts,source
    pub_abc123,6,1840,22,5,2,manual
    pub_abc123,168,5210,61,14,7,manual

Each row is one reading at one age. The same post appearing at several ages is
expected: that is what makes an age-comparable baseline possible.
"""
import argparse
import csv
import io
import sys
from dataclasses import dataclass
from pathlib import Path

from app.state.store import StateStore

__all__ = [
    "ImportPlan",
    "MetricRow",
    "apply_plan",
    "main",
    "parse_metrics_csv",
]

#: Columns the CSV must carry. Everything else is an error, so a renamed or
#: misspelled column is caught rather than silently read as a default.
REQUIRED_COLUMNS = ("publication_id", "age_hours")
OPTIONAL_COLUMNS = ("impressions", "reactions", "comments", "reposts", "source")
KNOWN_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


@dataclass(frozen=True)
class MetricRow:
    """One validated reading, ready to record."""

    publication_id: str
    age_hours: float
    impressions: int = 0
    reactions: int = 0
    comments: int = 0
    reposts: int = 0
    source: str = "manual"


@dataclass(frozen=True)
class ImportPlan:
    """What a file would import, or why it cannot import anything."""

    rows: tuple[MetricRow, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


def _number(raw: str | None, field: str) -> float:
    text = (raw or "").strip()
    if not text:
        raise ValueError(f"{field} is empty")
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"{field} {text!r} is not a number") from exc


def _count(raw: str | None, field: str) -> int:
    value = _number(raw if (raw or "").strip() else "0", field)
    if value != int(value):
        raise ValueError(f"{field} {value!r} is not a whole number")
    if value < 0:
        raise ValueError(f"{field} must be non-negative, got {value!r}")
    return int(value)


def _row_from(raw: dict[str, str]) -> MetricRow:
    publication_id = (raw.get("publication_id") or "").strip()
    if not publication_id:
        raise ValueError("publication_id is empty")
    age_hours = _number(raw.get("age_hours"), "age_hours")
    if age_hours < 0:
        raise ValueError(f"age_hours must be non-negative, got {age_hours!r}")
    return MetricRow(
        publication_id=publication_id,
        age_hours=age_hours,
        impressions=_count(raw.get("impressions"), "impressions"),
        reactions=_count(raw.get("reactions"), "reactions"),
        comments=_count(raw.get("comments"), "comments"),
        reposts=_count(raw.get("reposts"), "reposts"),
        source=(raw.get("source") or "manual").strip() or "manual",
    )


def parse_metrics_csv(text: str) -> ImportPlan:
    """Parse and validate a metrics CSV. Never raises; errors travel in the plan.

    All-or-nothing: any bad row yields no rows and a list of errors, so a
    caller can refuse to write rather than write a partial reading.
    """
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return ImportPlan(errors=("the CSV has no header row",))
    missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
    if missing:
        return ImportPlan(
            errors=(
                f"the CSV is missing required column(s): {', '.join(missing)}",
            )
        )
    unknown = [c for c in reader.fieldnames if c not in KNOWN_COLUMNS]
    if unknown:
        return ImportPlan(
            errors=(
                (f"the CSV has unknown column(s): {', '.join(unknown)}. "
                 f"Known: {', '.join(KNOWN_COLUMNS)}"),
            )
        )

    rows: list[MetricRow] = []
    errors: list[str] = []
    for line, raw in enumerate(reader, start=2):
        if None in raw:
            errors.append(f"line {line}: too many columns for the header")
            continue
        try:
            rows.append(_row_from(raw))
        except ValueError as exc:
            errors.append(f"line {line}: {exc}")
    if errors:
        return ImportPlan(errors=tuple(errors))
    if not rows:
        return ImportPlan(errors=("the CSV has no data rows",))
    return ImportPlan(rows=tuple(rows))


def apply_plan(store: StateStore, plan: ImportPlan, *,
               source: str | None = None) -> int:
    """Record every row of a validated plan. Returns how many were recorded.

    Refuses a plan with errors, and refuses to write a metric whose
    publication the store does not hold — checked before the first write, so
    an unknown id imports nothing rather than everything up to it.
    """
    if not plan.ok:
        raise ValueError(
            f"refusing to import a plan with {len(plan.errors)} error(s): "
            f"{plan.errors[0]}"
        )
    unknown = [
        row.publication_id for row in plan.rows
        if store.get_publication(row.publication_id) is None
    ]
    if unknown:
        raise ValueError(
            "refusing to import metrics for unknown publication(s): "
            f"{', '.join(sorted(set(unknown)))}"
        )
    for row in plan.rows:
        store.record_publication_metric(
            row.publication_id,
            age_hours=row.age_hours,
            impressions=row.impressions,
            reactions=row.reactions,
            comments=row.comments,
            reposts=row.reposts,
            source=source or row.source,
        )
    return len(plan.rows)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.metrics.import_metrics",
        description=(
            "Import post engagement metrics from a CSV. Dry run unless "
            "--apply is given."
        ),
    )
    parser.add_argument("path", help="path to the metrics CSV")
    parser.add_argument(
        "--apply", action="store_true",
        help="actually write the metrics (default: print what would be written)",
    )
    parser.add_argument(
        "--database", default=None,
        help="state database to write to (default: the configured store)",
    )
    parser.add_argument(
        "--source", default=None,
        help="override the source recorded on every row",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    text = Path(args.path).read_text(encoding="utf-8")

    plan = parse_metrics_csv(text)
    if not plan.ok:
        print("cannot import — the file has errors:", file=sys.stderr)
        for error in plan.errors:
            print(f"  {error}", file=sys.stderr)
        return 2

    if not args.apply:
        print(f"dry run — {len(plan.rows)} metric(s) would be recorded. "
              f"Re-run with --apply to record them.")
        for row in plan.rows:
            print(f"  {row.publication_id} @ {row.age_hours:g}h: "
                  f"{row.impressions} impressions, {row.reactions} reactions, "
                  f"{row.comments} comments, {row.reposts} reposts "
                  f"({row.source})")
        return 0

    with StateStore(args.database) as store:
        try:
            recorded = apply_plan(store, plan, source=args.source)
        except ValueError as exc:
            print(f"cannot import: {exc}", file=sys.stderr)
            return 2
    print(f"recorded {recorded} metric(s)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
