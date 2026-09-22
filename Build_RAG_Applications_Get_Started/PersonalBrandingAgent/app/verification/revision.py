"""The stopping rule. Small, total, and the only place the loop can end.

``PLAN.md`` Step 9 is explicit that **"an unbounded revise loop is a failure
mode, not a feature"**, and that ``REJECT`` after the limit is a correct
outcome. It is equally explicit that the loop itself is Step 10's. So the loop
is not here; what is here is the part a loop cannot be trusted to own — the
decision to stop — as a pure function of a result and a count.

Two properties make it worth being this small:

* **It is total.** Every verification outcome has a decision, for every count,
  and the mapping is written out rather than derived, so a reader can check it
  against ``PLAN.md`` in one pass.
* **It terminates.** ``REVISE`` is returned only while the count is below the
  limit; ``EXHAUSTED`` is terminal and is never ``REVISE``. A caller that
  obeys this function cannot loop forever, whatever it passes in — including a
  negative count, which is refused rather than treated as "no attempts yet".
"""
from app.verification.enums import RevisionDecision, VerificationOutcome
from app.verification.models import VerificationResult

__all__ = [
    "MAX_REVISION_ATTEMPTS",
    "revision_decision",
]

MAX_REVISION_ATTEMPTS = 2
"""How many times a draft may be regenerated before the attempt ends.

Two, declared here rather than configured, for the same reason
``app.publishing.service.MAX_PUBLISHES_PER_RUN`` is declared in its own layer:
the bound belongs to the thing it bounds. A revision is a second model call
against the same evidence; if the first revision did not fix a finding about
wording, the finding is not about the wording, and a third call is a way of
spending money to avoid concluding that.
"""


def revision_decision(result: VerificationResult, attempts_made: int, *,
                      limit: int = MAX_REVISION_ATTEMPTS) -> RevisionDecision:
    """What to do about ``result``, given how many revisions have happened.

    Args:
        result: the verification that just ran.
        attempts_made: revisions already attempted for this draft. Counts
            revisions, not verification calls, and is not clamped: an
            over-count is a spent budget, which is the safe direction.
        limit: the bound to apply. Injectable so a caller with a different
            budget does not have to reimplement the rule to change it.

    Returns:
        :attr:`~app.verification.enums.RevisionDecision.PUBLISH` only for a
        passing verification — the only decision from which a publish may
        proceed. ``REVISE`` only when the result requires revision *and* the
        budget is unspent. ``REJECT`` for an unrepairable result regardless of
        the count, because spending attempts on it cannot change the verdict.
        ``EXHAUSTED`` when a revisable result has run out of attempts.

    Raises:
        ValueError: ``attempts_made`` or ``limit`` is negative. A negative
            count is a caller defect, and guessing what it meant — "start
            over"? "spent"? — is how a stopping rule stops being one.
    """
    if attempts_made < 0:
        raise ValueError(
            f"attempts_made must not be negative, got {attempts_made}"
        )
    if limit < 0:
        raise ValueError(f"limit must not be negative, got {limit}")

    if result.is_publishable:
        return RevisionDecision.PUBLISH
    if result.outcome is VerificationOutcome.REJECTED:
        return RevisionDecision.REJECT
    if attempts_made < limit:
        return RevisionDecision.REVISE
    return RevisionDecision.EXHAUSTED
