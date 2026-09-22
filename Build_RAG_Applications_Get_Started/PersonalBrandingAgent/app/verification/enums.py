"""Controlled vocabularies for evidence verification (``PLAN.md`` Step 9).

Four enums, each with one job:

``VerificationOutcome``
    What the gate decided. Three values, because the caller has three things
    to do: publish, revise, or stop.

``Severity``
    Whether a finding can be repaired by rewriting the draft, or not. This is
    the *only* thing that separates a revision from a rejection, so it is
    data — declared once per kind in :mod:`app.verification.policy` — rather
    than a judgement made at each call site.

``ClaimVerdict``
    How one claim fared. Exists because ``PLAN.md`` Step 9 asks for
    claim-level results: "the post fails" is not a finding a revision loop can
    act on, and "these three claims are unsupported and why" is.

``ViolationKind``
    The specific thing that was found. A caller must be able to tell "this
    number is in no evidence I was given" from "this claim came from the
    positioning file" without parsing prose.

``RevisionDecision``
    What the caller does next. ``PLAN.md`` Step 9 requires the revision to be
    bounded and terminating; the decision and the bound live together in
    :mod:`app.verification.revision` so that no consumer of a failed
    verification has to invent its own stopping rule.

``VerificationFailureCategory``
    Why verification could not produce a verdict at all. Deliberately *not* a
    fourth outcome: a failure is not a result, and the difference matters for
    the same reason it did in Step 8 — a run that ends because verification
    crashed is not a run that decided the draft was unpublishable.

All five are ``str`` enums for the same reason as everywhere else in this
repository: a member compares and prints as the string it stands for, so it
survives a round trip through a record, a log line, or a JSON column.
"""
from enum import Enum

__all__ = [
    "ClaimVerdict",
    "RevisionDecision",
    "Severity",
    "VerificationFailureCategory",
    "VerificationOutcome",
    "ViolationKind",
]


class VerificationOutcome(str, Enum):
    """What the gate decided about one draft.

    ``PASS``
        Every claim is supported by the supplied evidence, its exact
        references are present in it, and the evidence state behind each
        claim is strong enough to carry it. This is the *only* value that
        permits a publish.

    ``REVISION_REQUIRED``
        The draft is not publishable as written, but the material beneath it
        is: a claim is unsupported, uncited, or rests on guidance rather than
        evidence. A revision of the same draft against the same evidence
        could pass. Step 10 owns the loop and its limit.

    ``REJECTED``
        The draft cannot pass from this evidence at all: a cited source the
        context does not hold, a reference the evidence does not contain, a
        claim the evidence state forbids, or no evidence to verify against.
        Revising the wording does not change any of these.

    ``PASS`` is unreachable from a violation — see
    :meth:`app.verification.models.VerificationResult.__post_init__`, which
    refuses to construct a passing result that carries a finding.
    """

    PASS = "PASS"
    REVISION_REQUIRED = "REVISION_REQUIRED"
    REJECTED = "REJECTED"


class Severity(str, Enum):
    """Whether a finding is about the *wording* or about the *evidence*.

    The line this draws is the one ``PLAN.md`` Step 9 needs and does not
    state: *can rewriting this draft against this same evidence make it
    publishable?*

    ``REVISABLE``
        Yes — the finding is about how the post is written. An uncited claim
        can be attributed; a claim that leans on the positioning file can be
        grounded or dropped; an advisory judgement that a sentence overstates
        its evidence can be softened.

    ``REJECT``
        No — the finding is about the evidence or the draft's provenance. A
        source the context does not hold cannot be cited into existence, a
        metric the evidence does not contain cannot be reworded into one it
        does, and material an evidence state declares undemonstrated does not
        become demonstrated by saying it differently.
    """

    REVISABLE = "REVISABLE"
    REJECT = "REJECT"


class ClaimVerdict(str, Enum):
    """How one claim fared, at the granularity a revision loop can act on.

    Derived from the severities of the violations attributed to that claim:
    ``REJECTED`` if any of them is
    :attr:`~app.verification.enums.Severity.REJECT`, ``UNSUPPORTED`` if any is
    revisable, ``SUPPORTED`` if none were found.

    ``SUPPORTED`` is not a claim of truth. It means *no deterministic check
    failed for this sentence, and the advisory judge did not object to it* —
    which is the strongest thing a gate made of string checks and an advisory
    model can honestly say.
    """

    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    REJECTED = "REJECTED"


class ViolationKind(str, Enum):
    """The specific finding. Each one maps to a severity in
    :data:`app.verification.policy.VIOLATION_SEVERITY`, and to the check that
    produced it (``PLAN.md`` Step 9, deterministic checks first).
    """

    EMPTY_DRAFT = "EMPTY_DRAFT"
    """The post carries no text to verify. Nothing can pass on nothing."""

    NO_CITATION = "NO_CITATION"
    """A claim the draft makes is attributed to no supplied evidence at all."""

    CITATION_NOT_IN_CONTEXT = "CITATION_NOT_IN_CONTEXT"
    """The draft names evidence the supplied context does not hold.

    Generation resolves labels against the prompt it built, so this appears
    when verification is given a context that is not the one the draft was
    written from — which is exactly the case a gate has to catch rather than
    assume away.
    """

    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    """The supplied context holds no evidence. Distinct from a failure: the
    question was answered, and the answer is that there is nothing to verify
    against."""

    GUIDANCE_AS_EVIDENCE = "GUIDANCE_AS_EVIDENCE"
    """A claim rests on positioning, vision or writing-style material, which
    shapes how something is said and cannot support that it is true."""

    EVIDENCE_STATE_TOO_WEAK = "EVIDENCE_STATE_TOO_WEAK"
    """The evidence behind a claim declares itself undemonstrated —
    ``ASPIRATIONAL``, ``LEARNING``, ``UNVERIFIED`` or ``STALE``."""

    FORBIDDEN_INFERENCE = "FORBIDDEN_INFERENCE"
    """The claim makes one of the inferences ``data/audit/README.md`` §3
    forbids by name."""

    UNSUPPORTED_REFERENCE = "UNSUPPORTED_REFERENCE"
    """The draft states a number, percentage, date or version that appears in
    **none** of the supplied evidence. A metric the evidence does not contain
    cannot be reworded into one it does, so this rejects."""

    UNCITED_REFERENCE = "UNCITED_REFERENCE"
    """The draft states a number, percentage, date or version that *is* in the
    supplied evidence — but in evidence the draft did not cite.

    Split from :attr:`UNSUPPORTED_REFERENCE` because the two need different
    repairs and only one of them is repairable: this one is under-attribution,
    fixed by citing the evidence that carries the figure, and it routes to
    revision. The other is fabrication, and it does not."""

    ADVISORY_UNSUPPORTED = "ADVISORY_UNSUPPORTED"
    """The advisory judge read the claim against the evidence and judged it
    unsupported. Advisory findings never reject — see
    :mod:`app.verification.support`."""


class RevisionDecision(str, Enum):
    """What to do about a verification result, once the attempts are counted.

    Exists because "verification failed" is not one instruction. The four
    members are the four things a caller can actually do, and they are
    mutually exclusive by construction — see
    :func:`app.verification.revision.revision_decision`, which is total over
    the outcomes and never returns ``REVISE`` once the budget is spent. That
    function is small on purpose: a stopping rule that lives inside a loop is
    a stopping rule that can be edited by accident.
    """

    PUBLISH = "PUBLISH"
    """The verification passed. The only decision from which a publish may
    proceed."""

    REVISE = "REVISE"
    """Not publishable, and the material to fix it is there. Regenerate with
    the result's ``revision_notes()`` — Step 10 owns that loop."""

    REJECT = "REJECT"
    """Not publishable and not repairable: an unverifiable finding. Revising
    would burn attempts without changing the verdict."""

    EXHAUSTED = "EXHAUSTED"
    """Revisable, but the budget is spent. `PLAN.md` Step 9: "REJECT after the
    limit is a correct outcome." Reported distinctly from
    :attr:`REJECT` because "this could never pass" and "we stopped trying" are
    different facts about a run, and only one of them is worth investigating."""


class VerificationFailureCategory(str, Enum):
    """Why verification produced no verdict.

    Both members mean the same thing to a caller — **do not publish** — and
    neither is a decision about the draft. They exist apart because the two
    call for different investigations: one is a context this layer refused to
    reason over, the other is an advisory judge that did something the layer
    could not interpret.
    """

    CONTEXT_UNUSABLE = "CONTEXT_UNUSABLE"
    """The supplied context contradicts itself and cannot be verified
    against."""

    JUDGE_FAILURE = "JUDGE_FAILURE"
    """The advisory judge raised something this layer cannot interpret, or
    answered about a claim that does not exist. Fail closed: a judge that
    misbehaved may have had an objection, and the one thing that must never
    happen is a draft passing because the check that would have caught it
    crashed."""
