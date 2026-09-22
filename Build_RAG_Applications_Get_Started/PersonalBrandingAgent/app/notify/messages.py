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

Layout: every notification carries the same subject (:data:`SUBJECT`) and a
body that leads with the thing itself — the issue, or the published post — and
only then its metadata. The mailbox is where the user finds out what happened,
so the first line of the body has to answer "what?" rather than describe the
shape of the message that answers it. Which of the two a message is, is on the
message as a :class:`~app.notify.enums.NotificationKind`, not in the subject.
"""
from typing import Iterable, Sequence

from app.logging_config import redact
from app.notify.enums import NotificationKind
from app.notify.models import NotificationMessage, PublishedPost
from app.state.enums import RunOutcome
from app.state.models import OperationalFailure, WorkflowRun, utc_now_iso

#: The subject of *every* notification, whatever it is about. One mailbox
#: receives both the problems and the posts, so one predictable subject is what
#: lets a single mail rule collect them (``PLAN.md`` Step 7's notification
#: layer, extended so a successful publish is reportable too).
SUBJECT = "Branding Agent"

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


def _issue_lines(recorded: Sequence[OperationalFailure], *,
                 secrets: Sequence[str]) -> list[str]:
    """The issue itself, before any of its metadata.

    A phase writes a human-readable message when it records a failure, and that
    message is the description of the problem — so it is rendered first and
    verbatim (redacted, never summarised or paraphrased). One failure is quoted
    on its own; several are attributed to their phase, because a run that
    failed in two places has two descriptions and dropping either would hide
    half the problem. A run with no recorded failure still has an outcome worth
    reporting, so it says that rather than rendering an empty issue.
    """
    if not recorded:
        return [_NO_FAILURE_RECORD]
    if len(recorded) == 1:
        return [redact(recorded[0].message, *secrets)]
    return [
        f"[{index}/{len(recorded)}] {failure.phase}: "
        f"{redact(failure.message, *secrets)}"
        for index, failure in enumerate(recorded, start=1)
    ]


def _failure_block(failure: OperationalFailure, *, heading: str | None,
                   secrets: Sequence[str]) -> list[str]:
    """A failure's structured fields. The description is quoted separately."""
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
    body = "\n".join([
        "PersonalBrandingAgent — operational failure",
        "",
        *_issue_lines([failure], secrets=secrets),
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
    return NotificationMessage(kind=NotificationKind.ISSUE,
                               subject=redact(SUBJECT, *secrets),
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

    lines = [
        "PersonalBrandingAgent — unattended run notification",
        "",
        *_issue_lines(recorded, secrets=secrets),
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
    for index, failure in enumerate(recorded, start=1):
        lines += _failure_block(
            failure,
            heading=f"--- Failure {index} of {len(recorded)} ---",
            secrets=secrets,
        )
        lines.append("")
    lines.append(_action(requires_human))
    return NotificationMessage(kind=NotificationKind.ISSUE,
                               subject=redact(SUBJECT, *secrets),
                               body=redact("\n".join(lines), *secrets))


def build_post_message(post: PublishedPost, *,
                       secrets: Sequence[str] = ()) -> NotificationMessage:
    """A post that was published, as an email.

    The other half of what the mailbox is for, and the half the failure path
    can never cover: publishing succeeds, the run terminates ``DO_NOT_PUBLISH``
    and is waived as a normal outcome, so nothing else would ever tell the user
    what went out under their name.

    The body *is* the post — the supplied content, first and unaltered — with
    the identifiers that let a person find it underneath.
    """
    body = "\n".join([
        "PersonalBrandingAgent — published post",
        "",
        redact(post.content, *secrets),
        "",
        _line("Post", post.post_id or "(not recorded)"),
        _line("Link", post.url or "(not recorded)"),
        _line("Published", post.published_at or "(not recorded)"),
        _line("Notified", utc_now_iso()),
    ])
    return NotificationMessage(kind=NotificationKind.PUBLICATION,
                               subject=redact(SUBJECT, *secrets),
                               body=redact(body, *secrets))
