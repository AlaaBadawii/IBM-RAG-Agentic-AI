"""The two ways verification can fail, and the one it can be unavailable.

Same shape as every other layer's errors (``PLAN.md`` Step 9, Failure/recovery):
**fail closed, never default to ``PASS``.**

:class:`VerificationError`
    Verification could not produce a verdict. The caller must treat the draft
    as unpublished, and the workflow ends the run as ``WORKFLOW_FAILED``.
    Deliberately *not* ``DO_NOT_PUBLISH`` — that outcome is a decision, and
    "the verifier crashed" is not one. Deliberately not
    ``REQUIRES_HUMAN_INTERVENTION`` either: both categories are defects in this
    system or in a context handed to it, they are reported by the alert the
    failed run produces, and inventing a severity for them would make the one
    label that means "a person must decide" routine.

:class:`SupportJudgeUnavailable`
    The **advisory** judge could not be consulted — no client, no credential,
    no answer, or an answer that was not the required shape. This is a
    *domain* signal, not a failure: ``PLAN.md`` Step 9 says LLM-assist being
    unavailable leaves the deterministic gates running, and the degraded mode
    recorded. The verifier catches this one and reports
    ``VerificationResult.degraded``. Any *other* exception from a judge is a
    :class:`VerificationError`: a judge that crashed while judging might have
    had an objection, and reporting a pass in its absence is the one thing
    that must not happen.
"""
from app.errors import AppError
from app.verification.enums import VerificationFailureCategory

__all__ = ["SupportJudgeUnavailable", "VerificationError"]


class VerificationError(AppError):
    """Raised when verification cannot produce a verdict.

    A refusal, a revision requirement and a rejection are all *results*
    (:class:`~app.verification.models.VerificationResult`), not exceptions.
    What is left here is the case where there is no result to return.
    """

    def __init__(
        self,
        message: str,
        *,
        category: VerificationFailureCategory = (
            VerificationFailureCategory.CONTEXT_UNUSABLE
        ),
    ):
        super().__init__(message)
        self.category = category

    @property
    def is_publishable(self) -> bool:
        """Always ``False``, stated as a property so a caller can write the
        rule without special-casing the exception."""
        return False


class SupportJudgeUnavailable(AppError):
    """Raised by an advisory judge that cannot be consulted.

    Not a verification failure: ``PLAN.md`` Step 9 keeps the deterministic
    gates authoritative when LLM assistance is missing, and requires the
    degraded mode to be *recorded* rather than assumed away. Treated as a
    distinct type so a judge can say "I could not answer" without the verifier
    having to guess whether an exception meant that or something worse.
    """
