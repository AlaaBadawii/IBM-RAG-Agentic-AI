"""Synchronizing registered sources into the knowledge base, one at a time.

The whole design is one sentence: **git says what changed, the operational
store says what was already processed, and the ingestion pipeline says what is
now indexed.** No two of them are allowed to answer each other's question.

    source registry  →  change detection  →  candidate files  →  relevance
                     →  ingestion pipeline  →  content hashes  →  Chroma

Per source, in order:

1. Resolve the revision the source is at now. For a git source that is a
   commit; for a filesystem source, or a repository with no commits, it is a
   digest of the source's admitted content.
2. Read the checkpoint — the revision the system last processed *successfully*.
   Equal to the current revision means a deterministic no-op: no pipeline
   call, no Chroma write, and no state write either, because there is nothing
   new to record.
3. Otherwise work out what changed. A git source with a known previous commit
   gets git's own path-level diff; anything else gets the source's whole
   admitted inventory, and the content hashes decide what genuinely differs.
4. Apply the relevance policy, which turns changed paths into candidates and
   purges (and refuses the rest, with reasons).
5. Hand the candidates to the existing pipeline.
6. Only then advance the checkpoint.

Failures are per source and never fatal to the run
    A source that cannot be read is recorded, its checkpoint is left exactly
    where it was, and the next source is attempted. There is no cross-source
    transaction and none is wanted: twenty-eight sources catching up must not
    be held hostage by one that moved. Because ingestion is idempotent and
    content-hash based, leaving a checkpoint behind is always safe — the next
    run re-processes the same range and reaches the same state.

What this module deliberately does not do
    It does not create workflow runs (Step 11 owns entry points), does not
    send notifications (Step 7), does not schedule itself (Step 12), and does
    not chunk, embed, hash, or write to Chroma — every one of those is the
    pipeline's, and it is called rather than reproduced.
"""
from dataclasses import dataclass
from typing import Callable

from app.errors import (
    GitError,
    IngestionError,
    RegistryError,
    SourceUnavailableError,
    StateStoreError,
    SyncError,
)
from app.ingestion.pipeline import run_ingestion
from app.logging_config import get_logger
from app.sources.enums import SyncDisposition, SyncPriority
from app.sources.guard import assert_path_admissible
from app.sources.lifecycle import SyncPlan, plan_for, review_signal_for
from app.sources.models import Registry, SourceDefinition
from app.state.enums import Workflow
from app.state.store import StateStore

from app.sync.candidates import candidate_files, purge_keys
from app.sync.enums import RevisionKind, SyncErrorCategory, SyncStatus
from app.sync.models import ChangedPath, SourceSyncResult, SyncRunResult
from app.sync.namespace import source_namespace
from app.sync.relevance import ChangePlan, annotate, full_resync_plan, plan_changes
from app.sync.revision import (
    CONTENT_REVISION_PREFIX,
    SourceRevision,
    changed_paths,
    read_revision,
)

__all__ = ["SyncContext", "pipeline_ingest", "sync_all", "sync_source"]

logger = get_logger(__name__)

SYNC_PHASE = "sync"
"""The ``operational_failures.phase`` every synchronization failure is filed
under, so a query can separate "the sync could not read a repository" from
every other phase's failures."""


def pipeline_ingest(*, candidates, purge, scope, embeddings=None, chroma=None) -> dict:
    """The default ingestion binding: the existing pipeline, called as-is.

    Kept as a module-level function so tests can prove the synchronizer hands
    the pipeline a candidate set, and so there is exactly one place that knows
    how the pipeline is invoked.
    """
    return run_ingestion(
        candidates=candidates,
        purge=purge,
        scope=scope,
        embeddings=embeddings,
        store=chroma,
    )


@dataclass(frozen=True)
class SyncContext:
    """Everything a synchronization needs that is not the source itself.

    Explicit rather than global: a test can point a run at a temporary state
    store, a temporary Chroma collection, and a recording stand-in for the
    pipeline, and then assert exactly what the run did — including that it
    called nothing at all.
    """

    store: StateStore
    embeddings: object | None = None
    chroma: object | None = None
    ingest: Callable[..., dict] = pipeline_ingest


#: Which failure an exception is, and what it obliges the operator to do.
#: Keyed by class and looked up through the MRO, so a subclass added later is
#: classified by its nearest known ancestor rather than falling to UNEXPECTED.
_FAILURE_POLICY: dict[type, tuple[SyncErrorCategory, bool, bool]] = {
    SourceUnavailableError: (SyncErrorCategory.SOURCE_UNAVAILABLE, False, True),
    RegistryError: (SyncErrorCategory.GUARD_REFUSED, False, True),
    GitError: (SyncErrorCategory.GIT_FAILURE, True, False),
    IngestionError: (SyncErrorCategory.INGESTION_FAILURE, True, False),
    StateStoreError: (SyncErrorCategory.STATE_FAILURE, True, True),
    SyncError: (SyncErrorCategory.CONTENT_UNREADABLE, True, False),
}


def _classify(exc: Exception) -> tuple[SyncErrorCategory, bool, bool]:
    """The category, retryability, and human-intervention flag for a failure."""
    for cls in type(exc).__mro__:
        policy = _FAILURE_POLICY.get(cls)
        if policy is not None:
            return policy
    return (SyncErrorCategory.UNEXPECTED, True, True)


def sync_source(source: SourceDefinition, context: SyncContext) -> SourceSyncResult:
    """Synchronize one registered source. Never raises.

    A synchronization attempt has to report its own failure, because the run
    around it continues — so the exception is the *implementation's* business
    and the result is the caller's. That includes unexpected exceptions: an
    unrecognised error is recorded as ``UNEXPECTED`` rather than allowed to
    abort a run over twenty-eight other sources.
    """
    try:
        return _synchronize(source, context)
    except Exception as exc:
        return _record_failure(source, context, exc)


def sync_all(registry: Registry, context: SyncContext) -> SyncRunResult:
    """Synchronize every registered source.

    Iterates the registry and nothing else. There is no directory walk and no
    discovery here, so an unregistered directory cannot become synchronization
    input — the registry is the complete statement of what is evidence, and
    the only source of it.

    Sources are visited in registry order, one at a time, each isolated: this
    is a deliberate 24-hour batch process, not a race, and a per-source
    failure is reported in the run's results rather than raised out of it.
    """
    results = [sync_source(source, context) for source in registry]
    failed = [r.source_name for r in results if r.failed]
    if failed:
        logger.warning(
            "Synchronization finished with %d failed source(s): %s",
            len(failed), ", ".join(failed),
        )
    return SyncRunResult(results=tuple(results))


def _synchronize(source: SourceDefinition, context: SyncContext) -> SourceSyncResult:
    """The happy path and the no-op path; anything raised is a failure."""
    assert_path_admissible(source.name, source.local_path)
    revision = read_revision(source)
    checkpoint = context.store.get_checkpoint(source.name)
    previous = checkpoint.last_revision if checkpoint else None

    if previous is not None and previous == revision.revision:
        # Already processed. No pipeline call, no Chroma read or write, and —
        # importantly — no state write: advancing a checkpoint that is already
        # at this revision would be an artificial change, and would make an
        # untouched source look busy.
        logger.info("Source %s unchanged at %s", source.name, revision.revision)
        return SourceSyncResult(
            source=source,
            status=SyncStatus.NO_CHANGE,
            plan=plan_for(source, has_changes=False),
            previous_revision=previous,
            current_revision=revision.revision,
            revision_kind=revision.kind,
            checkpoint=checkpoint,
        )

    changes, full_resync = _detect_changes(source, previous, revision)
    change_plan = (
        full_resync_plan(source) if full_resync
        else plan_changes(source, annotate(source, changes))
    )

    # Relevance is what the plan is for: a commit that touched only excluded
    # files yields no candidates, and this is the only place that decides so.
    relevant = change_plan.relevant_paths
    plan = plan_for(source, has_changes=bool(relevant))
    review_signal = review_signal_for(source, relevant)

    if not full_resync and change_plan.is_empty:
        return _advance_without_work(source, context, revision, previous, plan,
                                     change_plan, checkpoint)

    candidates = candidate_files(source, change_plan.candidates)
    ingestion = context.ingest(
        candidates=candidates,
        # The pipeline removes a key by looking it up in the collection, where
        # it is namespaced; a source-relative path would match nothing and
        # remove nothing, without error.
        purge=purge_keys(source, change_plan.purges),
        # The scoped sweep's keep-set is a source's entire inventory, so it is
        # enabled only for a plan built from that inventory. Passing it for a
        # diff would delete every file the revision did not happen to touch.
        scope=source_namespace(source.name) if full_resync else None,
        embeddings=context.embeddings,
        chroma=context.chroma,
    )
    advanced = context.store.record_sync_success(source.name, revision.revision)
    logger.info(
        "Source %s synchronized to %s (%d candidate(s), %d purge(s)%s)",
        source.name, revision.revision, len(change_plan.candidates),
        len(change_plan.purges), ", full resync" if full_resync else "",
    )
    return SourceSyncResult(
        source=source,
        status=SyncStatus.SYNCED,
        plan=plan,
        previous_revision=previous,
        current_revision=revision.revision,
        revision_kind=revision.kind,
        full_resync=full_resync,
        changed_paths=change_plan.changes,
        candidates=change_plan.candidates,
        purged=change_plan.purges,
        review_signal=review_signal,
        ingestion=ingestion,
        checkpoint=advanced,
    )


def _detect_changes(
    source: SourceDefinition, previous: str | None, revision: SourceRevision
) -> tuple[tuple[ChangedPath, ...], bool]:
    """What changed, and whether there was a baseline to compare against.

    Returns ``(changes, full_resync)``. ``full_resync`` is true whenever no
    per-path answer exists, and there are exactly three such cases: a source
    that has never been synchronized, a source with no history to diff
    (filesystem, or a git repository with no commits), and a previous revision
    the repository no longer knows because its history was rewritten. All
    three mean the same thing to the pipeline — submit the inventory, let the
    content hashes find what actually differs — so they are reported as one,
    rather than as three states a caller would have to handle separately.
    """
    if previous is None:
        return (), True
    if revision.kind is not RevisionKind.GIT or previous.startswith(CONTENT_REVISION_PREFIX):
        # A content digest is not a commit and cannot be handed to git. The
        # digest changed, so something did; only the content hashes can say
        # what, and that is the layer below.
        return (), True
    changes = changed_paths(source, previous, revision.revision)
    if changes is None:
        return (), True
    return changes, False


def _advance_without_work(
    source: SourceDefinition,
    context: SyncContext,
    revision: SourceRevision,
    previous: str | None,
    plan: SyncPlan,
    change_plan: ChangePlan,
    checkpoint,
) -> SourceSyncResult:
    """A new revision with nothing in it the registry cares about.

    The checkpoint advances anyway, and that is the point: the revision *was*
    processed, and its outcome was "nothing here is evidence". Leaving it
    behind would re-diff the same irrelevant commit on every future run, for
    ever, and the diff would never get shorter.

    No pipeline call, so no embedding work and no Chroma write — the changed
    paths are reported in full, with the rule that rejected each one, so the
    absence of work is explicable rather than mysterious.
    """
    advanced = context.store.record_sync_success(source.name, revision.revision)
    logger.info(
        "Source %s: revision %s changed %d path(s), none relevant; checkpoint advanced",
        source.name, revision.revision, len(change_plan.changes),
    )
    return SourceSyncResult(
        source=source,
        status=SyncStatus.SYNCED,
        plan=plan,
        previous_revision=previous,
        current_revision=revision.revision,
        revision_kind=revision.kind,
        full_resync=False,
        changed_paths=change_plan.changes,
        candidates=(),
        purged=(),
        review_signal=None,
        ingestion=None,
        checkpoint=advanced,
    )


def _record_failure(
    source: SourceDefinition, context: SyncContext, exc: Exception
) -> SourceSyncResult:
    """Record a source's failure and return it, without advancing anything.

    The checkpoint keeps the revision it had, so the next run retries exactly
    the range that failed. That is safe precisely because ingesting the same
    content twice reaches the same state — and it is why this must never be
    "helpfully" advanced to the current revision: a checkpoint that claims a
    revision was processed when it was not is the one failure mode that
    silently loses knowledge.
    """
    category, retryable, needs_human = _classify(exc)
    logger.error(
        "Source %s failed to synchronize (%s): %s", source.name, category.value, exc
    )
    checkpoint = None
    try:
        checkpoint = context.store.record_sync_failure(source.name)
        context.store.record_failure(
            phase=SYNC_PHASE,
            error_category=category.value,
            message=f"{source.name}: {exc}",
            retryable=retryable,
            requires_human_intervention=needs_human,
            workflow=Workflow.SYNC,
            # One row per source per kind of problem, counting occurrences,
            # rather than twenty-eight new rows every day a repository is
            # missing. The first occurrence always creates the row, so a new
            # problem can never be hidden by an old one.
            dedupe_key=f"{SYNC_PHASE}:{source.name}:{category.value}",
        )
    except StateStoreError as store_exc:
        # A store that cannot record the failure is a second, worse failure.
        # It is logged, and the source's own failure is still reported — the
        # one thing that must not happen is either failure being swallowed.
        logger.error(
            "Could not record the sync failure for %s: %s", source.name, store_exc
        )
    return SourceSyncResult(
        source=source,
        status=SyncStatus.FAILED,
        plan=_failure_plan(source),
        checkpoint=checkpoint,
        error=str(exc),
        error_category=category,
    )


def _failure_plan(source: SourceDefinition) -> SyncPlan:
    """The plan a failed source is reported under, without trusting the source.

    ``plan_for`` maps a declared lifecycle to a disposition, and a source whose
    lifecycle is not one of the four declared values has no mapping — through
    the registry that cannot happen, because the loader refuses the value at
    load time, but this is the failure path and a failure path that can itself
    raise would turn one broken source into an aborted run over all of them.
    An unrepresentable declaration is therefore reported as requiring review,
    which is the conservative reading: nothing about it is normal.
    """
    try:
        return plan_for(source, has_changes=False)
    except Exception:
        logger.warning(
            "Source %s declares an unrepresentable lifecycle (%r); reporting it "
            "as requiring review", source.name, getattr(source, "lifecycle", None),
        )
        return SyncPlan(
            source_name=source.name,
            lifecycle=getattr(source, "lifecycle", None),
            disposition=SyncDisposition.REVIEW_REQUIRED,
            priority=SyncPriority.LOW,
        )
