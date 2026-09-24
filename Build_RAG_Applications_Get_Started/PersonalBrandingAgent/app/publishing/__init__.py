"""Publishing service: the layer that sends a post and remembers it.

``PLAN.md`` Step 6. This package sits between the Agent's decision and the
LinkedIn integration (Step 5), and between the Agent and the operational state
store (Step 1):

    Agent (Step 10)  ->  PublishingService  ->  publish_to_linkedin (Step 5)
                                |
                                +->  StateStore  (write-ahead intent, outcome)
                                +->  PublishingHistory  (read-only, SQLite)

    from app.publishing import PublishingService, PublishRequest

    service = PublishingService(store)
    report = service.publish(PublishRequest(content=post, topic="sync"), run.run_id)

The two halves are deliberately separate:

* :class:`~app.publishing.service.PublishingService` writes, and is the only
  thing allowed to send anything;
* :class:`~app.publishing.history.PublishingHistory` reads, and is what the
  Agent is given instead of the store.

Publishing history stays in SQLite and is **never** indexed into Chroma
(``PLAN.md`` §6.1). A generated post is a record of what the system did, not
knowledge about the user; indexing it would let one post become the evidence
for the next, which is the loop the corpus's audit policy exists to prevent.
Nothing in this package imports the retrieval or ingestion layers.
"""
from app.publishing.duplicates import (
    DEFAULT_MAX_EVIDENCE_USES,
    DEFAULT_MAX_PROJECT_USES,
    DEFAULT_MAX_TOPIC_USES,
    DEFAULT_NEAR_DUPLICATE_THRESHOLD,
    DEFAULT_OVERUSE_WINDOW_DAYS,
    DuplicateDetector,
    DuplicatePolicy,
    exact_duplicate,
    near_duplicates,
    overuse,
)
from app.publishing.enums import (
    DuplicateKind,
    InterruptionKind,
    PublishDecision,
)
from app.publishing.history import PublishingHistory
from app.publishing.models import (
    DuplicateFinding,
    DuplicateReport,
    EvidenceUsage,
    InterruptedAttempt,
    PublicationSummary,
    PublishPreview,
    PublishReport,
    PublishRequest,
    RecoveryReport,
    UsageCount,
    evidence_ref,
)
from app.publishing.service import (
    MAX_PUBLISHES_PER_RUN,
    PublishingService,
    state_for_result,
)
from app.publishing.vectors import cosine_similarity, pack_embedding, unpack_embedding

__all__ = [
    "DEFAULT_MAX_EVIDENCE_USES",
    "DEFAULT_MAX_PROJECT_USES",
    "DEFAULT_MAX_TOPIC_USES",
    "DEFAULT_NEAR_DUPLICATE_THRESHOLD",
    "DEFAULT_OVERUSE_WINDOW_DAYS",
    "DuplicateDetector",
    "DuplicateFinding",
    "DuplicateKind",
    "DuplicatePolicy",
    "DuplicateReport",
    "EvidenceUsage",
    "InterruptedAttempt",
    "InterruptionKind",
    "MAX_PUBLISHES_PER_RUN",
    "PublicationSummary",
    "PublishDecision",
    "PublishPreview",
    "PublishReport",
    "PublishRequest",
    "PublishingHistory",
    "PublishingService",
    "RecoveryReport",
    "UsageCount",
    "cosine_similarity",
    "evidence_ref",
    "exact_duplicate",
    "near_duplicates",
    "overuse",
    "pack_embedding",
    "state_for_result",
    "unpack_embedding",
]
