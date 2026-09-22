"""Errors of the generation layer (``PLAN.md`` Step 8).

One error, and one deliberate absence.

**A failure is an exception, a decline is a result.** ``PLAN.md`` Step 8:
*"Generation failure is a distinct outcome from a low-quality draft."* A
decline is generation doing its job — it looked at the evidence, decided it
does not support a post, and said so — so it comes back as a
:class:`~app.generation.models.GenerationResult` with
``outcome=DECLINED``, and the workflow ends the run as ``DO_NOT_PUBLISH``,
which Step 7 waives as a normal outcome. A *failure* means no post exists and
none can be produced: the model was unreachable, or it answered with something
that is not the required structure. There is no valid degraded post
(``PLAN.md`` Step 8, Failure/recovery), so nothing is returned and the caller
records a ``WORKFLOW_FAILED`` phase, notifies through Step 7, and publishes
nothing.

Falling back would be the one behaviour this step must not have: a placeholder
or truncated post is unverified text about a real person, and it would reach
the publish path indistinguishable from a grounded draft.
"""
from app.errors import AppError
from app.generation.enums import GenerationFailureCategory

__all__ = ["GenerationError"]


class GenerationError(AppError):
    """Raised when a post could not be generated at all.

    Carries a :class:`~app.generation.enums.GenerationFailureCategory` so the
    workflow can record *why* — a missing credential is fixed by a person,
    an unreachable model is retried by the next scheduled run — without
    matching on message text.

    Never raised for a decline: that is a result. Never raised for a
    low-quality draft: generation has no opinion on quality, and Step 9 owns
    verification.
    """

    def __init__(self, message: str, *,
                 category: GenerationFailureCategory =
                 GenerationFailureCategory.LLM_UNAVAILABLE):
        super().__init__(message)
        self.category = category

    @property
    def requires_human_intervention(self) -> bool:
        """True for the one category a later run cannot fix by itself.

        ``REQUIRES_HUMAN_INTERVENTION`` is reserved for conditions a person
        must resolve (``PLAN.md`` §11), and a missing LLM credential is one:
        no number of retries configures a key. Everything else here is
        ordinary transient infrastructure and belongs to ``WORKFLOW_FAILED``.
        """
        return self.category is GenerationFailureCategory.CONFIGURATION
