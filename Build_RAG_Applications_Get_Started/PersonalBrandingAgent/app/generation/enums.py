"""Controlled vocabularies of the generation layer (``PLAN.md`` Step 8).

Mirrors the layout of ``app/context/enums.py`` and ``app/notify/enums.py``: a
value is only useful downstream if it can be branched on, and it can only be
branched on if it is a closed set.

Three vocabularies, and each answers a question the layers above genuinely
have to ask:

``GenerationOutcome``
    Did this produce a post, or did it decline to? Both are *results*, not
    errors — ``PLAN.md`` Step 8 requires the chain to be able to decline
    rather than fabricate, and a decline has to land on ``DO_NOT_PUBLISH``,
    which Step 7 waives precisely because it is a normal outcome.

``DeclineReason``
    Why it declined. ``INSUFFICIENT_EVIDENCE`` is decided before any model
    call (the context said so); ``MODEL_DECLINED`` is the model reporting that
    the evidence it was given does not support a post. They are different
    facts about the world and a person reading an audit needs to tell them
    apart.

``GenerationFailureCategory``
    How it broke — which is deliberately **not** a fourth outcome. A failure
    is an exception (``GenerationError``), because there is no valid degraded
    post to return: unlike retrieval, generation cannot usefully fall back to
    a weaker result (``PLAN.md`` Step 8, Failure/recovery). The category
    exists so the workflow that catches it can record *why* without parsing a
    message.

Note what is deliberately **not** here: a quality or confidence score. Step 9
owns verification, and a number invented here would be a second, unverified
opinion about a draft that has not been checked against anything yet.
"""
from enum import Enum


class GenerationOutcome(str, Enum):
    """What one generation call produced.

    Two members, because a draft and a refusal are the only two things
    generation can return. Everything else — a model that cannot be reached,
    a response that is not the required JSON — is a failure and is raised.
    """

    #: A candidate post, grounded in the supplied evidence.
    GENERATED = "generated"
    #: No post, on purpose, with a reason. A normal outcome.
    DECLINED = "declined"


class DeclineReason(str, Enum):
    """Why generation produced no post.

    ``INSUFFICIENT_EVIDENCE``
        The context carried no evidence, or the caller selected none. Decided
        deterministically, **without calling the model**: paying for a request
        that the assembled context has already answered is not a judgement
        call, and a model asked to write anyway is being invited to invent.

    ``MODEL_DECLINED``
        The model was given evidence and reported that it does not support a
        post worth publishing. This is the behaviour ``PLAN.md`` Step 8
        requires of the chain, and it is recorded as a refusal rather than
        treated as an empty response.
    """

    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    MODEL_DECLINED = "model_declined"


class GenerationFailureCategory(str, Enum):
    """Why generation could not complete.

    The same shape as the integration's error classification: a category the
    caller can branch on and record, instead of a message it would have to
    match on. A failure is never converted into a result — see
    :class:`~app.generation.errors.GenerationError`.
    """

    #: No usable LLM credential. A configuration defect, not a transient one.
    CONFIGURATION = "configuration"
    #: The model could not be reached, or the call was rejected.
    LLM_UNAVAILABLE = "llm_unavailable"
    #: The model answered, but not in the required shape — so there is no post
    #: to check and no post to publish. Guessing at the text would be
    #: fabrication by another route.
    INVALID_RESPONSE = "invalid_response"
