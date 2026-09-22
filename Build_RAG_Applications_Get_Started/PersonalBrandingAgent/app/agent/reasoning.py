"""The reasoning boundary: an interface, and nothing else.

``PLAN.md`` Step 10 asks for *one* bounded Agent, and Step 9 established the
shape such a boundary should take — :class:`app.verification.support.SupportJudge`
is a small injectable protocol with a fake used in every test, and the Agent
mirrors it exactly: a request, an answer, and a protocol anything can
implement.

**Structural, not inherited.** The two attributes are recorded on the proposal
so an audit says which reasoner and which prompt produced a decision, and the
test suite injects a plain object — no framework, no base class, no graph.

**One call, not a conversation.** There is no tool use, no scratchpad, no
second turn and no memory between runs. ``reason`` is asked once and its answer
is final; the bounded part of the Agent is the *revision loop below it*, over
drafts, and that loop's bound belongs to
:func:`app.verification.revision.revision_decision`. A reasoner that could ask
again would be an open-ended loop by another name, which is what ``PLAN.md``
Step 10 explicitly forbids.

**A reasoner that cannot answer is not a reasoner that declined.** Declining is
an answer (``ReasoningAnswer.publish`` is ``False``) and is a normal outcome.
Being unreachable or unreadable is
:class:`~app.agent.errors.ReasoningUnavailable`, and it is *not* degraded into
a proposal — the Agent has no deterministic half to fall back on, so an
unconsultable reasoner means no post.
"""
from typing import Protocol, runtime_checkable

from app.agent.models import ReasoningAnswer, ReasoningRequest

__all__ = ["ContentReasoner"]


@runtime_checkable
class ContentReasoner(Protocol):
    """Anything that can be asked what is worth publishing, and from what."""

    name: str
    prompt_version: str

    def reason(self, request: ReasoningRequest) -> ReasoningAnswer:
        """Choose a topic, an angle and a selection of evidence, or decline.

        Raises:
            ReasoningUnavailable: the reasoner could not be consulted. The
                Agent turns this into ``DO_NOT_PUBLISH`` with the failure
                exposed for the workflow to notify — never into a weaker
                proposal.
        """
        ...
