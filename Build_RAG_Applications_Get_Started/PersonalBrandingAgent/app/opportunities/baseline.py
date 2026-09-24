"""Load and seed the tracked-work baseline (M1).

The configuration file declares *what* is tracked; this module validates it
against the source registry and writes it into the store's ledger tables.
Seeding is idempotent — ``ensure_*`` primitives never overwrite existing
rows — so running it twice, or after new entries are added, only adds what
is missing. It never writes to ``publications`` or ``publish_intents``:
a baseline is coverage semantics, not publication history.
"""
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "DEFAULT_CONFIG_PATH",
    "PRIORITIES",
    "ensure_baseline",
    "load_tracked_work_config",
]

#: Allowed branding priorities, highest first. Priority orders
#: opportunities; it never guarantees publication — a high-priority work
#: with no meaningful uncovered development is still not an opportunity.
PRIORITIES = ("high", "normal", "low")

#: The committed baseline, next to ``sources.yaml`` at the project root.
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "tracked_work.yaml"


def load_tracked_work_config(path: Path | str | None = None) -> list[dict]:
    """Parse and validate the tracked-work declarations.

    Validation is structural plus referential: every entry needs an id and
    display name, every development needs a key, and every named source must
    exist in the registry — a typo'd source is refused here rather than
    silently tracking nothing. Returns the raw entries; writing them is
    :func:`ensure_baseline`'s job.
    """
    from app.sources.registry import load_registry

    resolved = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    raw = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    entries = raw.get("tracked_work", [])
    if not isinstance(entries, list):
        raise ValueError(
            f"{resolved}: 'tracked_work' must be a list"
        )
    from app.sources.registry import load_registry

    return _validate(entries, set(load_registry().names), str(resolved))


def _validate(entries: list, known: set[str], where: str) -> list[dict]:
    from app.retrieval.scope import CURATED_CATEGORIES

    validated: list[dict] = []
    for entry in entries:
        work_id = (entry.get("id") or "").strip()
        if not work_id:
            raise ValueError(f"{where}: a tracked work entry has no id")
        if not (entry.get("display_name") or "").strip():
            raise ValueError(
                f"{where}: tracked work {work_id!r} has no display_name"
            )
        if entry.get("branding_priority", "normal") not in PRIORITIES:
            raise ValueError(
                f"{where}: tracked work {work_id!r} has an unknown "
                f"branding_priority"
            )
        sources = entry.get("sources", [])
        unknown = [name for name in sources if name not in known]
        if unknown:
            raise ValueError(
                f"{where}: tracked work {work_id!r} names unknown "
                f"source(s): {unknown}; registered: {sorted(known)}"
            )
        developments = entry.get("developments", [])
        for development in developments:
            if not (development.get("key") or "").strip():
                raise ValueError(
                    f"{where}: a development of {work_id!r} has no key"
                )
            if development.get("coverage_kind", "baseline") not in (
                "baseline", "published"
            ):
                raise ValueError(
                    f"{where}: development "
                    f"{development.get('key')!r} of {work_id!r} has an "
                    f"unknown coverage_kind"
                )
            categories = development.get("corpus_categories", [])
            unknown_cats = [c for c in categories if c not in CURATED_CATEGORIES]
            if unknown_cats:
                raise ValueError(
                    f"{where}: development "
                    f"{development.get('key')!r} of {work_id!r} names "
                    f"unknown corpus categories: {unknown_cats}"
                )
            evidence_sources = development.get("evidence_sources", [])
            if not isinstance(evidence_sources, list) or not all(
                    isinstance(s, str) and s.strip()
                    for s in evidence_sources):
                raise ValueError(
                    f"{where}: development "
                    f"{development.get('key')!r} of {work_id!r} has an "
                    f"invalid evidence_sources list"
                )
            editorial_intent = development.get("editorial_intent", "")
            if not isinstance(editorial_intent, str) or not (
                    editorial_intent == "" or editorial_intent.strip()):
                raise ValueError(
                    f"{where}: development "
                    f"{development.get('key')!r} of {work_id!r} has an "
                    f"invalid editorial_intent"
                )
        validated.append(entry)
    return validated


def ensure_baseline(store: Any, entries: list[dict] | None = None, *,
                    path: Path | str | None = None) -> dict[str, int]:
    """Seed tracked work and its developments. Returns what was ensured.

    ``entries`` overrides the file for tests; otherwise the committed
    configuration is loaded. Every write goes through the idempotent
    ``ensure_*`` primitives, and nothing here touches publication state.
    """
    if entries is None:
        entries = load_tracked_work_config(path)
    else:
        from app.sources.registry import load_registry

        entries = _validate(
            entries, set(load_registry().names), "provided entries")
    works = developments = 0
    for entry in entries:
        store.ensure_tracked_work(
            entry["id"],
            entry.get("display_name", entry["id"]),
            description=entry.get("description", ""),
            sources=tuple(entry.get("sources", [])),
            enabled=bool(entry.get("enabled", True)),
        )
        works += 1
        for development in entry.get("developments", []):
            store.ensure_development(
                entry["id"],
                development["key"],
                development.get("display_name", development["key"]),
                covered=bool(development.get("covered", False)),
                coverage_kind=development.get("coverage_kind", "baseline"),
                publication_id=development.get("publication_id"),
            )
            developments += 1
    return {"tracked_work": works, "developments": developments}
