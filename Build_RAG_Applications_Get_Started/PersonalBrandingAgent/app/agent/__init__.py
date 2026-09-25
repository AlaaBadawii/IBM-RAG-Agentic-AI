"""The autonomous branding agent — the one place the system reasons.

``PLAN.md`` Step 10. Steps 1–9 build deterministic capability; this adds the
*single* bounded Agent that sits above generation and verification and below
the workflows, and it is bounded by everything already built.

    PersonalBrandingContext
        |
        +-- propose  --------------------------> AgentProposal | DO_NOT_PUBLISH
        |       (one model call, resolved against the context)
        |
        +-- generate -> verify -> revision_decision
        |       (the bounded loop; every gate is Step 8's and Step 9's)
        |
        +-- AgentResult          PUBLISH (only with a passing verification)
                                 DO_NOT_PUBLISH (a normal success, with a reason)

    from app.agent import BrandingAgent
    from app.publishing import PublishingHistory
    from app.generation import PostGenerator
    from app.verification import EvidenceVerifier

    agent = BrandingAgent(
        reasoner=LlmContentReasoner(),
        generator=PostGenerator(),
        verifier=EvidenceVerifier(judge=LlmSupportJudge()),
        history=PublishingHistory(store),
    )
    result = agent.run(context)

Five things ``PLAN.md`` Step 10 requires, and where each is enforced:

**One agent.** :class:`BrandingAgent` is the only agent, and there is no
multi-agent decomposition, no planner/critic pair, no graph framework and no
second turn anywhere in the package. The reasoner is asked once per run.

**``DO_NOT_PUBLISH`` is a normal outcome.** It is
:attr:`~app.agent.enums.AgentDecision.DO_NOT_PUBLISH`, it always carries a
:class:`~app.agent.enums.NoPublishReason`, and the reasons that are failures
are a separate, explicitly enumerated set
(:data:`~app.agent.enums.FAILURE_REASONS`) — so "we decided not to" and
"reasoning broke" can never be confused for one another.

**Evidence selection is confined to what retrieval returned.**
:func:`~app.agent.prompt.evidence_options` builds labels from the context's
own items, and :meth:`~app.agent.agent.BrandingAgent._proposal_from` resolves
the answer against exactly that list. An identifier that does not resolve is
:class:`~app.agent.errors.EvidenceSelectionError` and the run ends as
``DO_NOT_PUBLISH``; it is refused, never dropped.

**No state writes, and no direct publishing.** There is no store handle, no
publisher, no transport and no clock in this package, and no import path to
any of them. The Agent reads publishing history through the Step 6 read
service (:class:`~app.agent.history.PublicationHistoryReader`, which
:class:`app.publishing.history.PublishingHistory` satisfies) and produces
:class:`~app.agent.models.AgentProposal` / :class:`~app.agent.models.AgentResult`
values. Recording the publication is Step 11's, because *"the system could
forget to record"* otherwise.

**The gates stay authoritative.** A ``PUBLISH`` is unconstructible without a
passing :class:`~app.verification.models.VerificationResult`, Step 8's
generator and Step 9's verifier are called as-is, and the revision loop's
bound belongs to :func:`app.verification.revision.revision_decision` rather
than being reimplemented here.

Public surface, and deliberately nothing more:

    BrandingAgent            the one entry point
    AgentProposal            what to write about, and from which evidence
    AgentResult              the outcome, with its reason or its failure
    AgentDecision            publish, or do not
    NoPublishReason          why there is no post
    AgentFailure             the reasoning failure, for the workflow to notify
    ContentReasoner          the injectable reasoning boundary
    LlmContentReasoner       the OpenRouter-backed implementation
    PublicationHistoryReader the read-only history boundary
"""
from app.agent.agent import BrandingAgent
from app.agent.enums import (
    FAILURE_REASONS,
    AgentDecision,
    AgentFailureCategory,
    NoPublishReason,
)
from app.agent.errors import (
    AgentError,
    EvidenceSelectionError,
    ReasoningUnavailable,
    UnusableReasoningAnswer,
)
from app.agent.history import (
    DEFAULT_DIGEST_LIMIT,
    PublicationHistoryReader,
    read_publication_history,
)
from app.agent.llm import AGENT_PARAMETERS, LlmContentReasoner
from app.agent.models import (
    AgentFailure,
    AgentProposal,
    AgentResult,
    EvidenceOption,
    HistoryDigest,
    ReasoningAnswer,
    ReasoningRequest,
    TopicCandidate,
    WithdrawnPublication,
    publishing_constraints,
)
from app.agent.prompt import (
    AGENT_PROMPT_VERSION,
    ReasoningPrompt,
    build_reasoning_prompt,
    evidence_options,
    parse_reasoning_answer,
    topic_candidates,
)
from app.agent.reasoning import ContentReasoner

__all__ = [
    "AGENT_PARAMETERS",
    "AGENT_PROMPT_VERSION",
    "DEFAULT_DIGEST_LIMIT",
    "FAILURE_REASONS",
    "AgentDecision",
    "AgentError",
    "AgentFailure",
    "AgentFailureCategory",
    "AgentProposal",
    "AgentResult",
    "BrandingAgent",
    "ContentReasoner",
    "EvidenceOption",
    "EvidenceSelectionError",
    "HistoryDigest",
    "LlmContentReasoner",
    "NoPublishReason",
    "PublicationHistoryReader",
    "ReasoningAnswer",
    "ReasoningPrompt",
    "ReasoningRequest",
    "ReasoningUnavailable",
    "TopicCandidate",
    "UnusableReasoningAnswer",
    "WithdrawnPublication",
    "build_reasoning_prompt",
    "evidence_options",
    "parse_reasoning_answer",
    "publishing_constraints",
    "read_publication_history",
    "topic_candidates",
]
