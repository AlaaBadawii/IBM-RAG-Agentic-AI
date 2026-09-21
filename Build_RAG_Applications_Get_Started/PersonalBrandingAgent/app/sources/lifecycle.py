"""What lifecycle is allowed to change, and what it never may.

The tempting reading of ``COMPLETED`` is "stop looking" — and it is wrong.
``PLAN.md`` Step 2 is explicit that lifecycle governs *depth and priority,
never visibility*, and §5.5 explains why: the corpus already contains a
``## Status`` heading in 42 files of which only 32 resolve against any
vocabulary, so a lifecycle that silently suppressed synchronization would
reproduce, as a mechanism, exactly the drift the roadmap exists to fix. A
project marked finished that then receives commits is not noise to be
filtered; it is the single most informative event the synchronizer can see.

So this module has no "skip" outcome anywhere. It maps a declared lifecycle
plus an observed change onto a :class:`SyncPlan`, and a plan always ingests.
The only variable is whether the change also raises a signal for a human.
"""
from dataclasses import dataclass, field

from app.sources.enums import SyncDisposition, SyncPriority
from app.sources.models import SourceDefinition
from app.state.enums import LifecycleState

__all__ = ["StatusReviewSignal", "SyncPlan", "plan_for", "review_signal_for"]


@dataclass(frozen=True)
class SyncPlan:
    """How a source should be synchronized, given its lifecycle."""

    source_name: str
    lifecycle: LifecycleState
    disposition: SyncDisposition
    priority: SyncPriority
    ingest: bool = True
    """Always true. Present so the invariant is checkable in a test rather
    than only asserted in a docstring — see :mod:`app.sources.lifecycle`."""

    @property
    def needs_review(self) -> bool:
        return self.disposition is SyncDisposition.REVIEW_REQUIRED


@dataclass(frozen=True)
class StatusReviewSignal:
    """A lifecycle declaration that reality has moved past.

    Carries the paths that changed, because "your completed project has new
    commits" is only actionable alongside *what* changed: the user is being
    asked to decide whether the project is finished after all, or whether the
    lifecycle declaration is simply stale.
    """

    source_name: str
    lifecycle: LifecycleState
    changed_paths: tuple[str, ...] = field(default=())
    reason: str = ""

    def as_message(self) -> str:
        where = f"{len(self.changed_paths)} changed path(s)" if self.changed_paths else "new activity"
        return (
            f"source {self.source_name!r} is declared {self.lifecycle.value} "
            f"but shows {where}: {self.reason}"
        )


_LIFECYCLE_PLAN: dict[LifecycleState, tuple[SyncDisposition, SyncPriority]] = {
    # Active work is what a branding workflow is *for*: ingest quietly.
    LifecycleState.ACTIVE: (SyncDisposition.NORMAL, SyncPriority.HIGH),
    # A completed project that moved. `PLAN.md` names this case specifically:
    # the change is ingested and surfaced as REQUIRES_HUMAN_INTERVENTION.
    LifecycleState.COMPLETED: (SyncDisposition.REVIEW_REQUIRED, SyncPriority.LOW),
    # Activity in a project the user paused is a decision point, not noise:
    # either work resumed (the declaration is stale) or something else wrote
    # there, and both are worth a human look.
    LifecycleState.PAUSED: (SyncDisposition.REVIEW_REQUIRED, SyncPriority.LOW),
    # A project declared but not started, which nonetheless has content, is
    # the clearest signal of all: the declaration no longer describes reality.
    LifecycleState.PLANNED: (SyncDisposition.REVIEW_REQUIRED, SyncPriority.LOW),
}

_REVIEW_REASON: dict[LifecycleState, str] = {
    LifecycleState.COMPLETED: "a completed project still has its changes detected, never ignored",
    LifecycleState.PAUSED: "a paused project received activity",
    LifecycleState.PLANNED: "a planned project already has content",
}


def plan_for(
    source: SourceDefinition, *, has_changes: bool
) -> SyncPlan:
    """The plan for one source, given whether it has changed.

    A source with no changes always gets ``NORMAL``: there is nothing to
    review, and firing a signal for an unchanged repository would train the
    user to ignore signals — which is how a review gate stops being a gate.
    """
    disposition, priority = _LIFECYCLE_PLAN[source.lifecycle]
    if not has_changes:
        disposition = SyncDisposition.NORMAL
    return SyncPlan(
        source_name=source.name,
        lifecycle=source.lifecycle,
        disposition=disposition,
        priority=priority,
    )


def review_signal_for(
    source: SourceDefinition, changed_paths: tuple[str, ...] | list[str]
) -> StatusReviewSignal | None:
    """The signal to raise, or ``None`` when the change is unremarkable.

    Callers must *still* ingest the changed paths when this returns a signal.
    The signal is an addition to synchronization, never a substitute for it.
    """
    plan = plan_for(source, has_changes=bool(changed_paths))
    if not plan.needs_review:
        return None
    return StatusReviewSignal(
        source_name=source.name,
        lifecycle=source.lifecycle,
        changed_paths=tuple(changed_paths),
        reason=_REVIEW_REASON[source.lifecycle],
    )
