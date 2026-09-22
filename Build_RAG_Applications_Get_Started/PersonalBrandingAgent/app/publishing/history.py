"""The publishing-history read service (``PLAN.md`` Step 6, Decision 2).

Publishing history is **not** indexed into Chroma (``PLAN.md`` §6.1), so the
questions the Agent has about its own past are answered here, by deterministic
SQLite queries through ``StateStore`` — never by semantic retrieval:

    What have I published recently?          -> recent_publications()
    Which topics did I use?                  -> recent_topics()
    Which evidence did I use?                -> recent_evidence()
    Which projects have I talked about?      -> recent_projects()
    What may exist but is unconfirmed?       -> requires_review()

Three properties hold by construction, and they are the reason this service
exists rather than the Agent querying the store:

* **Read-only.** There is no method here that writes, and none that can be
  given a store it does not own.
* **Attributable.** Every row returned carries the ``publication_id`` it came
  from, and the store reads it from ``publications`` /
  ``publication_evidence``. Nothing is inferred, averaged or extrapolated.
* **Not evidence.** Nothing in this module imports the retrieval or ingestion
  layers, and nothing it returns is a corpus document. A generated post is a
  record of something the system *did*; the corpus is what is known about the
  user, and mixing them would let one generated post become the evidence for
  the next (§6.1). The published text is deliberately not returned at all —
  only its hash, and the references to the corpus it was grounded in.

An empty history is a normal answer, not an error: every method returns an
empty tuple when nothing has been published yet.
"""
from typing import Sequence

from app.state.models import PublicationRecord
from app.state.store import StateStore

from app.publishing.models import (
    EvidenceUsage,
    PublicationSummary,
    UsageCount,
)

__all__ = ["PublishingHistory"]

#: Default bound on how many rows a history query returns. Every method takes
#: an explicit ``limit``; this is what "recent" means when a caller does not say.
DEFAULT_HISTORY_LIMIT = 10

#: The most records one query will read before aggregating. Large enough that
#: a real history is never truncated in practice, bounded so that a store with
#: years of rows cannot turn a read into an unbounded scan.
MAX_HISTORY_SCAN = 500


class PublishingHistory:
    """Read-only queries over stored publication state."""

    def __init__(self, store: StateStore) -> None:
        self._store = store

    # -- what was published -------------------------------------------------

    def recent_publications(self, limit: int = DEFAULT_HISTORY_LIMIT
                            ) -> tuple[PublicationSummary, ...]:
        """Confirmed publications, newest first.

        "Confirmed" means LinkedIn returned a post id: a failed attempt is not
        history, and an ambiguous one is reported by :meth:`requires_review`
        instead, because it is a question rather than a fact.
        """
        return tuple(
            PublicationSummary.from_record(record)
            for record in self._published_records(limit=limit)
        )

    def requires_review(self, limit: int = DEFAULT_HISTORY_LIMIT
                        ) -> tuple[PublicationSummary, ...]:
        """Attempts whose outcome is unresolved, newest first.

        A post *may* exist for each of these. They are returned rather than
        hidden because the one thing the system must never do is forget an
        ambiguity and publish again on top of it.
        """
        return tuple(
            PublicationSummary.from_record(record)
            for record in self._store.list_publication_records(
                outcome="unknown_requires_review", limit=limit
            )
        )

    def unresolved_intents(self, run_id: str | None = None
                           ) -> tuple[str, ...]:
        """Ids of intents that never reached a terminal state.

        The durable half of ambiguity: an intent left at ``attempt_started``
        with no publication is exactly what recovery resolves.
        """
        return tuple(
            intent.intent_id
            for intent in self._store.list_unresolved_intents(run_id)
        )

    # -- what was used ------------------------------------------------------

    def recent_topics(self, limit: int = DEFAULT_HISTORY_LIMIT, *,
                      since: str | None = None) -> tuple[UsageCount, ...]:
        """Topics already published about, most used first.

        Counted from the topic recorded on each intent, not from the text —
        which is what makes the answer exact, and why a post that never had a
        topic recorded does not appear.
        """
        return _usage(
            self._published_records(since=since),
            lambda record: record.topic,
            limit=limit,
        )

    def recent_projects(self, limit: int = DEFAULT_HISTORY_LIMIT, *,
                        since: str | None = None) -> tuple[UsageCount, ...]:
        """Projects already published about, most used first."""
        return _usage(
            self._published_records(since=since),
            lambda record: record.project,
            limit=limit,
        )

    def recent_evidence(self, limit: int = DEFAULT_HISTORY_LIMIT, *,
                        since: str | None = None) -> tuple[EvidenceUsage, ...]:
        """Evidence already cited by published posts, most used first.

        Identified by ``(source_path, content_hash)`` rather than by path: the
        corpus is resynchronized every 24 hours, so the same path holding
        different content is different evidence, and counting the two together
        would misreport how much a source has actually been leaned on.
        """
        counts: dict[tuple[str, str], list[PublicationRecord]] = {}
        for record in self._published_records(since=since):
            for ref in record.evidence:
                counts.setdefault(
                    (ref.source_path, ref.content_hash), []
                ).append(record)

        rows = [
            EvidenceUsage(
                source_path=path,
                content_hash=digest,
                uses=len(records),
                last_used_at=records[0].recorded_at,
                publication_ids=tuple(r.publication_id for r in records),
            )
            for (path, digest), records in counts.items()
        ]
        rows.sort(key=lambda row: (-row.uses, row.source_path, row.content_hash))
        return tuple(rows[:limit])

    # -- internals ----------------------------------------------------------

    def _published_records(self, *, limit: int | None = None,
                           since: str | None = None
                           ) -> list[PublicationRecord]:
        """Stored records for confirmed publications, newest first."""
        return self._store.list_publication_records(
            since=since,
            outcome="published",
            limit=limit if limit is not None else MAX_HISTORY_SCAN,
        )


def _usage(records: Sequence[PublicationRecord],
           key,
           *,
           limit: int) -> tuple[UsageCount, ...]:
    """Group records by one optional field, deterministically ordered.

    Ties are broken by value so two runs over the same store return the same
    order — the same reason the store orders evidence references:
    reproducibility is what lets a caller compare two results at all.
    """
    counts: dict[str, list[PublicationRecord]] = {}
    for record in records:
        value = key(record)
        if value:
            counts.setdefault(value, []).append(record)

    rows = [
        UsageCount(
            value=value,
            uses=len(group),
            last_used_at=group[0].recorded_at,
            publication_ids=tuple(r.publication_id for r in group),
        )
        for value, group in counts.items()
    ]
    rows.sort(key=lambda row: (-row.uses, row.value))
    return tuple(rows[:limit])
