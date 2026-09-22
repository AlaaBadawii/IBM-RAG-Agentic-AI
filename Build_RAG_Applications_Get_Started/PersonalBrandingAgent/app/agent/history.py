"""What the Agent is allowed to know about its own past.

``PLAN.md`` Step 10 is explicit: the Agent *"Reads context (Step 4) and
publishing history **through the Step 6 read service** — never by querying the
store directly."* This module is where that is enforced rather than promised.

Two types, and the split between them is the point:

:class:`PublicationHistoryReader`
    A structural protocol declaring the four read methods the Agent uses.
    Nothing in this package constructs a :class:`~app.state.store.StateStore`,
    and nothing here could: there is no import path from ``app.agent`` to
    ``app.state``, and the test suite asserts it by parsing the modules.
    :class:`app.publishing.history.PublishingHistory` already satisfies this
    protocol without knowing it exists — the same structural arrangement
    :class:`app.verification.support.SupportJudge` uses — so the workflow
    passes the real read service and a test passes a fake.

:class:`~app.agent.models.HistoryDigest`
    The *value* the Agent then reasons over. The reader is called once per run
    and its answers become a frozen digest, so the reasoning layer holds no
    live handle on the store: nothing it does can read more than it was given,
    and nothing it does can write at all.

Read-only by construction. There is no method here that writes, none that
takes a store it does not own, and nothing that can be given one. Every row
that crosses keeps its ``publication_ids``, so a count the Agent reasons about
is still traceable to stored publications afterwards — and the published
*text* never crosses at all, because a generated post is a record of something
the system did, not knowledge about the user (``PLAN.md`` §6.1).
"""
from typing import Protocol, runtime_checkable

from app.agent.models import HistoryDigest
from app.publishing.models import (
    EvidenceUsage,
    PublicationSummary,
    UsageCount,
)

__all__ = [
    "DEFAULT_DIGEST_LIMIT",
    "PublicationHistoryReader",
    "read_publication_history",
]

#: How many rows of each kind one digest carries. Small on purpose: this is
#: what a reasoner is told so it can avoid repeating itself, not an archive
#: query. Passing a limit explicitly is what keeps a store with years of rows
#: from turning a run into an unbounded read.
DEFAULT_DIGEST_LIMIT = 10


@runtime_checkable
class PublicationHistoryReader(Protocol):
    """The read half of Step 6, as the Agent sees it.

    Four methods, no writes, and no way to ask for anything else.
    :class:`app.publishing.history.PublishingHistory` satisfies this
    structurally; so does anything a test cares to pass.
    """

    def recent_publications(self, limit: int = ...
                            ) -> tuple[PublicationSummary, ...]:
        """Confirmed publications, newest first."""
        ...

    def requires_review(self, limit: int = ...
                        ) -> tuple[PublicationSummary, ...]:
        """Attempts whose outcome is unresolved. Nothing may be forgotten
        about these, which is why they travel with the rest."""
        ...

    def recent_topics(self, limit: int = ..., *, since: str | None = None
                      ) -> tuple[UsageCount, ...]:
        """Topics already published about, most used first."""
        ...

    def recent_projects(self, limit: int = ..., *, since: str | None = None
                        ) -> tuple[UsageCount, ...]:
        """Projects already published about, most used first."""
        ...

    def recent_evidence(self, limit: int = ..., *, since: str | None = None
                        ) -> tuple[EvidenceUsage, ...]:
        """Evidence already cited by published posts, most used first."""
        ...


def read_publication_history(
        reader: PublicationHistoryReader | None, *,
        limit: int = DEFAULT_DIGEST_LIMIT) -> HistoryDigest:
    """One digest of the stored history, read through the Step 6 service.

    Called once per run, before the reasoner is asked anything, so the
    reasoning layer never holds a live handle: what it reasons about is a
    frozen value, and re-reading it is not something a decision can do.

    ``None`` means *nothing is known* — which is exactly what a first run has,
    and what a caller with no store to hand would have. It is an empty digest
    rather than an error: an empty history is a normal answer (the read
    service's own contract), and a system that refused to publish its first
    post because there was no history would never publish one.
    """
    if reader is None:
        return HistoryDigest.empty()

    return HistoryDigest(
        publications=tuple(reader.recent_publications(limit=limit)),
        requires_review=tuple(reader.requires_review(limit=limit)),
        topics=tuple(reader.recent_topics(limit=limit)),
        projects=tuple(reader.recent_projects(limit=limit)),
        evidence=tuple(reader.recent_evidence(limit=limit)),
    )
