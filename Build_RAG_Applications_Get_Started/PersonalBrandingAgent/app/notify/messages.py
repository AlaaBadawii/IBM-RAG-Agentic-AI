"""Composing a notification from what the system recorded.

The content is fixed by ``PLAN.md`` Step 7: *workflow, phase, timestamp, run
ID, error category, human-readable explanation, retryable-or-not,
human-intervention-required-or-not*. Every one of those is a field already
stored on the failure or the run, so nothing here derives a fact — it renders
one.

Two rules:

1. **The distinction is carried, not recomputed.** Whether a failure needs a
   person is read off ``requires_human_intervention``; the outcome vocabulary
   is the run-outcome vocabulary Step 1 constrains (§2, §11). The notification
   layer never decides severity, because a second decision point is a second
   way to get it wrong.
2. **No secret is rendered.** Subject and body both pass through the shared
   redaction list (:func:`~app.logging_config.redact`) plus any secret the
   transport's own configuration carries. The body is composed *from* a stored
   failure message, and a message is a string some earlier layer wrote — so it
   is treated as untrusted with respect to secrets.
"""
from typing import Iterable, Sequence

from app.logging_config import redact
from app.notify.models import NotificationMessage
from app.state.enums import RunOutcome
from app.state.models import OperationalFailure, WorkflowRun, utc_now_iso

#: Prefixes every subject, so a mailbox rule can find these without guessing.
SUBJECT_PREFIX = "[PersonalBrandingAgent]"

#: Width of the label column in a body. Chosen to fit the longest label
#: (``Requires human intervention``) with its colon and a visible gap, so
#: values line up in a plain-text mail client and in a terminal.
_LABEL = 32

_NO_FAILURE_RECORD = (
    "No failure record was written for this run. The run outcome is itself the "
    "record: a phase failed and did not report a structured failure."
)


def outcome_label(requires_human_intervention: bool) -> str:
    """The outcome this failure amounts to, in the run-outcome vocabulary.

    ``PLAN.md`` §11 partitions every unattended failure into exactly two
    notifiable kinds: ``REQUIRES_HUMAN_INTERVENTION`` (the six conditions
    nothing automatic can resolve) and ``WORKFLOW_FAILED`` (everything a later
    run may get past). ``requires_human_intervention`` on the failure record is
    which of the two this is — so it is read, never inferred.
    """
    if requires_human_intervention:
        return RunOutcome.REQUIRES_HUMAN_INTERVENTION.value
    return RunOutcome.WORKFLOW_FAILED.value


def _line(label: str, value: object) -> str:
    return f"{label + ':':<{_LABEL}}{value}"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _action(requires_human_intervention: bool) -> str:
    if requires_human_intervention:
        return ("Action required: this cannot be resolved automatically, and it "
                "will not be retried until a person resolves it.")
    return ("No action is required from you. This failure is recorded, and the "
            "next scheduled run will pick the work up again.")


def _failure_block(failure: OperationalFailure, *, heading: str | None,
                   secrets: Sequence[str]) -> list[str]:
    lines: list[str] = []
    if heading:
        lines += [heading, ""]
    lines += [
        _line("Phase", failure.phase),
        _line("Error category", failure.error_category),
        _line("Recorded", failure.first_seen_at),
        _line("Last seen", failure.last_seen_at),
        _line("Occurrences", failure.occurrence_count),
        _line("Retryable", _yes_no(failure.retryable)),
        _line("Requires human intervention",
              _yes_no(failure.requires_human_intervention)),
        "",
        "Explanation:",
        redact(failure.message, *secrets),
    ]
    return lines


def build_failure_message(failure: OperationalFailure, *,
                          secrets: Sequence[str] = ()) -> NotificationMessage:
    """One phase's failure, as an email.

    Used by the phase-facing entry point: a phase that fails records a
    structured failure and asks for it to be reported, without knowing
    anything about email, configuration or the store's notification table.
    """
    outcome = outcome_label(failure.requires_human_intervention)
    subject = (f"{SUBJECT_PREFIX} {outcome} — {failure.phase}"
               + (f" ({failure.workflow})" if failure.workflow else ""))
    body = "\n".join([
        "PersonalBrandingAgent — operational failure",
        "",
        _line("Outcome", outcome),
        _line("Workflow", failure.workflow or "(not recorded)"),
        _line("Run", failure.run_id or "(not recorded)"),
        _line("Notified", utc_now_iso()),
        "",
        *_failure_block(failure, heading=None, secrets=secrets),
        "",
        _action(failure.requires_human_intervention),
    ])
    return NotificationMessage(subject=redact(subject, *secrets),
                               body=redact(body, *secrets))


def build_run_message(run: WorkflowRun, failures: Iterable[OperationalFailure],
                      *, secrets: Sequence[str] = ()) -> NotificationMessage:
    """A finished run, as an email, with every failure recorded against it.

    This is the workflow-facing entry point, and the reason the notification
    layer exists: the workflow wrapper knows how the run terminated, which is
    the fact a person has to hear, and the failures say why.
    """
    recorded = list(failures)
    outcome = (run.outcome.value if run.outcome is not None
               else "(unfinished)")
    requires_human = run.outcome is RunOutcome.REQUIRES_HUMAN_INTERVENTION
    subject = (f"{SUBJECT_PREFIX} {outcome} — {run.workflow} run {run.run_id}")

    lines = [
        "PersonalBrandingAgent — unattended run notification",
        "",
        _line("Outcome", outcome),
        _line("Workflow", run.workflow),
        _line("Run", run.run_id),
        _line("Started", run.started_at),
        _line("Finished", run.finished_at or "(not finished)"),
        _line("Failed phase", run.failed_phase or "(not recorded)"),
        _line("Failures recorded", len(recorded)),
        _line("Notified", utc_now_iso()),
        "",
    ]
    if requires_human:
        lines += [
            "This run stopped and is waiting for a person. Nothing about it "
            "is retried automatically.",
            "",
        ]
    if not recorded:
        lines += [_NO_FAILURE_RECORD, ""]
    for index, failure in enumerate(recorded, start=1):
        lines += _failure_block(
            failure,
            heading=f"--- Failure {index} of {len(recorded)} ---",
            secrets=secrets,
        )
        lines.append("")
    lines.append(_action(requires_human))
    return NotificationMessage(subject=redact(subject, *secrets),
                               body=redact("\n".join(lines), *secrets))
