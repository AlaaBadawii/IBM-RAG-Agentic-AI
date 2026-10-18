"""Repair stale opportunity snapshots: the operational half of Phase 2.

``persist_discoveries`` repairs an opportunity when the same fingerprint is
re-discovered, because current selection then carries a better snapshot. But
an opportunity whose source no longer wins a retrieval slot is never
re-discovered, so its frozen snapshot would otherwise survive forever — which
is exactly the incident's shape. This module is the bounded, explicit repair
for those rows.

Two operations, both read-only unless asked otherwise:

    plan_repairs(store, chunk_source)      -> what would change, and why
    apply_repairs(store, chunk_source)     -> refresh the actionable rows

It is deliberately conservative:

* only **actionable** rows (queued/failed) are candidates — a claimed,
  published, rejected, or exhausted row is never touched;
* a rebuilt snapshot is only *proposed* per distinct document, and a document
  with no narrative chunk keeps its existing evidence rather than being
  silently stripped;
* ``apply_repairs`` defaults to a dry run, so the production store is changed
  only by an explicit ``dry_run=False`` (the CLI's ``--apply``);
* ``refresh_opportunity_snapshot`` itself never moves lifecycle state, so even
  an applied repair cannot reset attempts, steal a claim, or revive a row.

The rebuilder reads chunks out of the vector store by ``content_hash`` — no
model, no embedding, no network — so a document's full chunk set is available
even when retrieval would not surface it.
"""
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.context.evidence_roles import has_narrative, selection_priority
from app.logging_config import get_logger
from app.opportunities.backlog import EVIDENCE_SNAPSHOT_VERSION
from app.state.models import ContentOpportunity
from app.state.store import StateStore

__all__ = [
    "RepairCandidate",
    "apply_repairs",
    "chroma_chunk_source",
    "plan_repairs",
    "rebuild_snapshot",
]

logger = get_logger(__name__)

#: How many narrative chunks of one document a rebuilt snapshot keeps. The
#: same bound the tier uses (``app/retrieval/strata.py``), kept here as a
#: plain number so this module does not import the retrieval package.
CHUNKS_PER_DOCUMENT = 2


@dataclass(frozen=True)
class RepairCandidate:
    """One opportunity the repair pass would change, and the change itself."""

    opportunity: ContentOpportunity
    before_chunk_ids: tuple[str, ...]
    after_chunk_ids: tuple[str, ...]
    after_snapshots: tuple[dict, ...]
    after_strength: int

    @property
    def changed(self) -> bool:
        """True only when the rebuilt snapshot is materially different."""
        return self.before_chunk_ids != self.after_chunk_ids

    @property
    def before_is_narrative(self) -> bool:
        """Whether the stored snapshot already carries a narrative chunk.

        ``False`` is the incident's signature: a snapshot of pure catalogue
        (path lists, ``Story strength``), which no writer can ground a post
        in.
        """
        return any(has_narrative(snap.get("content", ""))
                   for snap in self.opportunity.evidence)

    def to_dict(self) -> dict[str, Any]:
        """A printable summary for the CLI and for logs."""
        return {
            "opportunity_id": self.opportunity.opportunity_id,
            "topic": self.opportunity.topic,
            "attempts": self.opportunity.attempts,
            "snapshot_version": self.opportunity.snapshot_version,
            "before": list(self.before_chunk_ids),
            "after": list(self.after_chunk_ids),
            "changed": self.changed,
            "before_had_narrative": self.before_is_narrative,
        }


#: A chunk source answers "every stored chunk with this content_hash", as
#: mappings with ``source``, ``chunk_id``, ``content`` and ``metadata`` keys.
ChunkSource = Callable[[str], Sequence[Mapping[str, Any]]]


def rebuild_snapshot(evidence: Sequence[Mapping[str, Any]],
                     chunk_source: ChunkSource) -> list[dict]:
    """Re-derive one opportunity's evidence from the live chunk store.

    For each stored evidence item, its document's current chunks are fetched
    by ``content_hash`` and re-ordered narrative-first, keeping up to
    :data:`CHUNKS_PER_DOCUMENT`. A document that yields no narrative chunk —
    or that the store no longer holds — keeps the original item, so repair
    never removes provenance it cannot replace. Order follows the stored
    evidence, so the result is deterministic.
    """
    rebuilt: list[dict] = []
    seen: set[str] = set()
    for snap in evidence:
        digest = str(snap.get("content_hash") or "").strip()
        chunks = list(chunk_source(digest)) if digest else []
        chosen = [chunk for chunk in
                  sorted(chunks, key=lambda c: selection_priority(
                      str(c.get("content") or "")))
                  if _is_narrative(chunk)][:CHUNKS_PER_DOCUMENT]
        if not chosen:
            _append(rebuilt, seen, dict(snap))
            continue
        for chunk in chosen:
            _append(rebuilt, seen, _snapshot_from_chunk(chunk))
    return rebuilt


def plan_repairs(store: StateStore, chunk_source: ChunkSource, *,
                 current_version: int = EVIDENCE_SNAPSHOT_VERSION,
                 limit: int = 100) -> list[RepairCandidate]:
    """Every actionable opportunity whose snapshot predates the policy.

    Read-only: nothing is written. Returns one candidate per stale row, in
    the store's stable backlog order. A candidate whose rebuilt snapshot is
    identical to the stored one (``changed`` is ``False``) is still returned,
    so a caller can see that a stale row was examined and found sound.
    """
    candidates: list[RepairCandidate] = []
    for opportunity in store.list_stale_snapshot_opportunities(
            current_version, limit=limit):
        after = rebuild_snapshot(opportunity.evidence, chunk_source)
        candidates.append(RepairCandidate(
            opportunity=opportunity,
            before_chunk_ids=_chunk_ids(opportunity.evidence),
            after_chunk_ids=_chunk_ids(after),
            after_snapshots=tuple(after),
            after_strength=_strength(after, opportunity.evidence_strength),
        ))
    return candidates


def apply_repairs(store: StateStore, chunk_source: ChunkSource, *,
                  current_version: int = EVIDENCE_SNAPSHOT_VERSION,
                  limit: int = 100,
                  dry_run: bool = True) -> list[RepairCandidate]:
    """Refresh the snapshots that changed, unless ``dry_run``.

    Returns the planned candidates either way, so ``dry_run=True`` (the
    default) is a faithful preview of ``dry_run=False`` over the same store
    and chunk source. A refresh only ever applies to an actionable row, and
    it is skipped for a candidate whose rebuilt snapshot is unchanged.
    """
    candidates = plan_repairs(store, chunk_source,
                              current_version=current_version, limit=limit)
    if dry_run:
        return candidates
    applied: list[RepairCandidate] = []
    for candidate in candidates:
        if not candidate.changed:
            continue
        refreshed = store.refresh_opportunity_snapshot(
            candidate.opportunity.opportunity_id,
            list(candidate.after_snapshots),
            evidence_strength=candidate.after_strength,
            snapshot_version=current_version,
            expected_snapshot_hash=candidate.opportunity.snapshot_hash,
        )
        logger.info(
            "Repaired opportunity %s (%s): %s -> %s",
            refreshed.opportunity_id, refreshed.topic,
            list(candidate.before_chunk_ids), list(candidate.after_chunk_ids),
        )
        applied.append(candidate)
    return candidates


def chroma_chunk_source(vector_store: Any) -> ChunkSource:
    """A :data:`ChunkSource` backed by a Chroma-style store.

    ``vector_store.get(where=..., include=[...])`` is exactly the read
    :meth:`app.retrieval.strata._sibling_chunks` uses; a store that cannot
    answer contributes an empty sequence rather than failing the repair.
    """

    def source(digest: str) -> list[dict]:
        if not digest:
            return []
        try:
            stored = vector_store.get(
                where={"content_hash": digest},
                include=["documents", "metadatas"],
            )
        except Exception:  # noqa: BLE001 — a store that cannot answer is not fatal
            return []
        rows: list[dict] = []
        ids = stored.get("ids") or []
        documents = stored.get("documents") or []
        metadatas = stored.get("metadatas") or []
        for chunk_id, content, metadata in zip(ids, documents, metadatas):
            meta = metadata or {}
            rows.append({
                "source": meta.get("source", ""),
                "chunk_id": chunk_id or "",
                "content": content or "",
                "metadata": meta,
            })
        return rows

    return source


# ------------------------------------------------------------- internals ---

def _is_narrative(chunk: Mapping[str, Any]) -> bool:
    return has_narrative(str(chunk.get("content") or ""))


def _snapshot_from_chunk(chunk: Mapping[str, Any]) -> dict:
    meta = dict(chunk.get("metadata") or {})
    chunk_id = str(chunk.get("chunk_id") or "")
    digest = str(meta.get("content_hash")
                 or chunk_id.partition(":")[0]).strip()
    return {
        "source": str(chunk.get("source") or meta.get("source") or ""),
        "chunk_id": chunk_id,
        "content_hash": digest,
        "evidence_state": meta.get("evidence_state"),
        "category": meta.get("category", ""),
        "document_type": meta.get("document_type"),
        "content": str(chunk.get("content") or ""),
    }


def _append(rebuilt: list[dict], seen: set[str], snapshot: dict) -> None:
    chunk_id = str(snapshot.get("chunk_id") or "")
    if chunk_id and chunk_id in seen:
        return
    if chunk_id:
        seen.add(chunk_id)
    rebuilt.append(snapshot)


def _chunk_ids(evidence: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    return tuple(str(snap.get("chunk_id") or "") for snap in evidence)


def _strength(rebuilt: Sequence[Mapping[str, Any]],
              fallback: int) -> int:
    """The rebuilt snapshot's evidence strength, or the stored value.

    Imported lazily through the backlog layer's own ranking so repair and
    discovery agree on what "strength" means.
    """
    from app.context.taxonomy import state_rank
    ranks = [state_rank(snap.get("evidence_state")) for snap in rebuilt]
    return min(ranks) if ranks else fallback


def main(argv: list[str] | None = None) -> int:
    """``python -m app.opportunities.repair [--apply] [--limit N]``."""
    import argparse

    from app.ingestion.pipeline import get_vector_store

    parser = argparse.ArgumentParser(
        description="Repair stale content-opportunity evidence snapshots.")
    parser.add_argument("--apply", action="store_true",
                        help="write the repairs (default: dry run)")
    parser.add_argument("--limit", type=int, default=100,
                        help="how many stale rows to examine")
    args = parser.parse_args(argv)

    store = StateStore()
    try:
        chunk_source = chroma_chunk_source(get_vector_store())
        candidates = apply_repairs(
            store, chunk_source, limit=args.limit, dry_run=not args.apply)
    finally:
        store.close()

    changed = [c for c in candidates if c.changed]
    header = "would repair" if not args.apply else "repaired"
    print(f"{len(candidates)} stale row(s); {len(changed)} {header}")
    for candidate in candidates:
        summary = candidate.to_dict()
        print(f"  {summary['opportunity_id']} [{summary['topic']}] "
              f"attempts={summary['attempts']} "
              f"v{summary['snapshot_version']} "
              f"narrative={summary['before_had_narrative']} "
              f"{'CHANGED' if summary['changed'] else 'unchanged'}")
        if summary["changed"]:
            print(f"      before: {summary['before']}")
            print(f"      after : {summary['after']}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
