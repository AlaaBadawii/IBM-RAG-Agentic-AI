"""Controlled vocabularies for the branding context layer (``PLAN.md`` Step 4).

Only two, and both exist because a *list* would be the wrong shape:

``EvidenceStatus``
    Whether the assembled context actually contains evidence. This is the
    single most important output of Step 4: without it a generator can only
    ask "is this list empty?", and an empty list is indistinguishable from a
    list that was never populated because retrieval itself went wrong.

``FreshnessState``
    What the operational store says about a source's synchronization. Derived
    from ``sync_checkpoints`` rather than invented — see
    :mod:`app.context.builder`.

Both are ``str`` enums for the same reason as :mod:`app.state.enums`: a member
compares and prints as the string it stands for.
"""
from enum import Enum


class EvidenceStatus(str, Enum):
    """Whether the context holds evidence a generator may ground a claim in.

    Deliberately two values, not a confidence score. The corpus's own rule is
    *"``EVIDENCE: insufficient`` is preferred over guessing"*
    (``data/evidence/README.md``), and the audit's rule is that the KB must
    never become *"more confident than the evidence supports"*
    (``data/audit/README.md``). A number in ``[0, 1]`` would be exactly such a
    claim: precise-looking, unverifiable, and impossible to test.

    ``SUFFICIENT`` means at least one **evidence** item was assembled. It is
    not a judgement about quality or relevance — the ordering inside every
    section is what carries that, and the generator is expected to read it.
    Positioning and writing-style material never produces ``SUFFICIENT``:
    it shapes how a supported fact is communicated and cannot support one.
    """

    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"


class FreshnessState(str, Enum):
    """How current a source's indexed evidence is, per the operational store.

    ``SYNCHRONIZED``
        A successful synchronization recorded a revision and a time. The
        evidence from this source is as current as the system knows how to
        make it.

    ``FAILED``
        The most recent attempt failed. The revision the last *successful*
        pass recorded is still exposed, because the content that was indexed
        then is still indexed — but nothing newer is, so the honest state is
        that freshness is not established.

    ``UNKNOWN``
        No checkpoint exists at all. Either the source has never been
        synchronized (Known Issue #7) or it is not a registered source and is
        therefore not synchronization's business.

    ``UNKNOWN`` is never a synonym for "stale" or for "fresh". It is the
    explicit absence of an authoritative answer, which is the only honest
    thing to report when the system genuinely does not know.
    """

    SYNCHRONIZED = "SYNCHRONIZED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
