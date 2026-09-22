"""Step 10: the Agent's contract.

What a caller can rely on, and what ``PLAN.md`` Step 10 asks to be provable:

``DO_NOT_PUBLISH`` is reachable and is respected; the Agent cannot publish
without passing Step 9's gate; it cannot exceed the post limit; evidence
selection is confined to what retrieval returned and an identifier that does
not resolve is refused rather than tolerated; publishing history is read
through Step 6's read service and nothing here writes; a reasoning failure is a
``DO_NOT_PUBLISH`` rather than a weaker post; and the whole decision is
reproducible under a fake reasoner, deterministically, with no network.

Every test drives the Agent with plain fakes and a context built from literal
chunks. No API key, no network, no model, no LinkedIn, and the milestone test
at the bottom runs the whole chain — context, decision, generation,
verification, outcome — twice, to prove it is deterministic rather than merely
observed once.
"""
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agent import (
    AGENT_PROMPT_VERSION,
    FAILURE_REASONS,
    AgentDecision,
    AgentFailureCategory,
    AgentProposal,
    AgentResult,
    BrandingAgent,
    LlmContentReasoner,
    NoPublishReason,
    PublicationHistoryReader,
    ReasoningAnswer,
    ReasoningRequest,
    ReasoningUnavailable,
    UnusableReasoningAnswer,
    build_reasoning_prompt,
    evidence_options,
    parse_reasoning_answer,
    topic_candidates,
)
from app.agent.history import read_publication_history
from app.context.builder import build_context
from app.context.enums import EvidenceStatus
from app.generation import (
    EvidenceCitation,
    GeneratedPost,
    GenerationMetadata,
    GenerationOutcome,
    GenerationResult,
    PostGenerator,
)
from app.publishing import PublishingHistory, UsageCount, evidence_ref
from app.publishing.models import PublicationSummary
from app.retrieval.models import RetrievalResult, RetrievedDocument
from app.state.models import to_iso, utc_now
from app.verification import (
    EvidenceVerifier,
    JudgeVerdict,
    JudgementRequest,
    VerificationOutcome,
    VerificationResult,
)

EVIDENCE_TEXT = (
    "Built a shipment API with FastAPI and SQLAlchemy models and Alembic "
    "migrations; the API returns shipments to the tracking dashboard."
)
OTHER_EVIDENCE_TEXT = (
    "Built the portfolio site with FastAPI and Jinja templates, deployed on a "
    "small VPS."
)
COURSE_TEXT = "Completed the IBM RAG applications course."
STYLE_TEXT = "Write directly, without marketing language."
POSITIONING_TEXT = "Positioned as a backend engineer who ships small services."

#: Passes Step 9 against ``EVIDENCE_TEXT`` — see
#: ``tests/test_verification_verifier.py``, which pins the same sentence.
PASSING_POST = "I built a shipment API with FastAPI and SQLAlchemy models."

#: Unsupported, and *revisable*: Step 9 says rewrite it, so this is the draft
#: the bounded loop spends its budget on.
REVISABLE_POST = "I led a team of nine engineers across three continents."

#: Cites a metric nothing in the fixture supports. Step 9 rejects this rather
#: than sending it back, because a metric the corpus does not contain cannot
#: be reworded into one it does.
FABRICATED_POST = "I cut API latency by 40% with a caching layer."


# ------------------------------------------------------------------ helpers ---

def doc(source: str, *, category: str, chunk_id: str, content: str,
        evidence_state: str | None = None,
        document_type: str | None = None) -> RetrievedDocument:
    metadata = {
        "source": source, "category": category,
        "document_type": document_type or "unknown",
        "content_hash": chunk_id.split(":")[0],
    }
    if evidence_state is not None:
        metadata["evidence_state"] = evidence_state
    return RetrievedDocument(
        content=content, score=0.5, source=source, metadata=metadata,
        strategy="vector", chunk_id=chunk_id, rank=1,
    )


def context(*documents: RetrievedDocument):
    return build_context(RetrievalResult(
        query="a topic", strategy="vector", documents=list(documents),
        diagnostics={},
    ))


def evidence_context():
    """Two evidence sections, so there is a real choice of topic to make."""
    return context(
        doc("evidence/backend/fastapi.md", category="evidence",
            chunk_id="a1b2c3:0", content=EVIDENCE_TEXT,
            evidence_state="VERIFIED"),
        doc("projects/portfolio.md", category="completed_projects",
            chunk_id="b2c3d4:0", content=OTHER_EVIDENCE_TEXT,
            evidence_state="DOCUMENTED"),
    )


def course_context():
    """One course, so the only opportunity is a weak one."""
    return context(doc(
        "courses/ibm_rag.md", category="in_progress_courses",
        chunk_id="ffff00:1", content=COURSE_TEXT, evidence_state="LEARNING",
    ))


def guidance_only_context():
    """The shape Step 4 produces when retrieval found no evidence at all."""
    return context(
        doc("data/writing_style/alaa_writing_style.md", category="writing_style",
            document_type="writing_style", chunk_id="d4e5f6:1",
            content=STYLE_TEXT),
        doc("data/public_positioning/portfolio.md",
            category="public_positioning", document_type="positioning",
            chunk_id="d4e5f6:0", content=POSITIONING_TEXT),
    )


class FakeReasoner:
    """A reasoner that answers from a list, and remembers being asked.

    Not a framework type, not a model, and not a subclass of anything: the
    boundary is structural, so this is what "injectable" has to mean.
    """

    name = "fake-reasoner"
    prompt_version = "fake-reasoner-v1"

    def __init__(self, answer: ReasoningAnswer | None = None, *,
                 error: Exception | None = None):
        self.answer = answer or ReasoningAnswer(
            publish=False, decline_reason="nothing here is worth publishing"
        )
        self.error = error
        self.requests: list[ReasoningRequest] = []

    def reason(self, request: ReasoningRequest) -> ReasoningAnswer:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.answer

    @property
    def calls(self) -> int:
        return len(self.requests)


class FakeHistory:
    """The Step 6 read service, as the Agent sees it: five read methods."""

    def __init__(self, *, publications=(), topics=(), projects=(), evidence=(),
                 requires_review=()):
        self._publications = tuple(publications)
        self._topics = tuple(topics)
        self._projects = tuple(projects)
        self._evidence = tuple(evidence)
        self._requires_review = tuple(requires_review)
        self.calls: list[tuple[str, int]] = []

    def recent_publications(self, limit=10):
        self.calls.append(("recent_publications", limit))
        return self._publications

    def requires_review(self, limit=10):
        self.calls.append(("requires_review", limit))
        return self._requires_review

    def recent_topics(self, limit=10, *, since=None):
        self.calls.append(("recent_topics", limit))
        return self._topics

    def recent_projects(self, limit=10, *, since=None):
        self.calls.append(("recent_projects", limit))
        return self._projects

    def recent_evidence(self, limit=10, *, since=None):
        self.calls.append(("recent_evidence", limit))
        return self._evidence


class FakeJudge:
    """A deterministic advisory judge — Step 9's boundary, not this step's."""

    name = "fake-judge"
    prompt_version = "fake-support-judge-v1"

    def __init__(self, unsupported=()):
        self.unsupported = set(unsupported)

    def judge(self, request: JudgementRequest) -> tuple[JudgeVerdict, ...]:
        return tuple(
            JudgeVerdict(
                claim_index=claim.index,
                supported=claim.index not in self.unsupported,
                reason="" if claim.index not in self.unsupported
                else "the evidence does not state this",
            )
            for claim in request.claims
        )


class FakeLLM:
    """A model that answers with whatever it was told to.

    ``replies`` is a sequence, so one test can drive a first attempt and a
    revision from the same generator.
    """

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls: list[tuple[dict, ...]] = []

    def invoke(self, messages):
        self.calls.append(messages)
        reply = self.replies[min(len(self.calls) - 1, len(self.replies) - 1)]
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(content=reply)

    @property
    def prompts(self) -> str:
        return "\n".join(
            message["content"] for call in self.calls for message in call
        )


class FakeGenerator:
    """A generator that answers from a list, one draft per attempt.

    Citations are built from the request's own evidence, so a fixture cannot
    accidentally cite something the proposal did not select.
    """

    def __init__(self, contents):
        self.contents = list(contents)
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        index = min(len(self.requests) - 1, len(self.contents) - 1)
        return GenerationResult(
            outcome=GenerationOutcome.GENERATED,
            metadata=GenerationMetadata(model_id="fake", prompt_version="fake"),
            post=GeneratedPost(content=self.contents[index], citations=tuple(
                EvidenceCitation(label=f"E{position}", source=item.source,
                                 chunk_id=item.chunk_id,
                                 evidence_state=item.evidence_state)
                for position, item in enumerate(request.evidence, start=1)
            )),
        )


def generation_reply(post=PASSING_POST, evidence_used=("E1",),
                     declined=False, reason=""):
    return json.dumps({
        "post": post,
        "evidence_used": list(evidence_used),
        "declined": declined,
        "reason": reason,
    })


def proposal_answer(topic="evidence", labels=("E1",), **overrides):
    payload = {
        "publish": True,
        "topic": topic,
        "angle": "What building this taught me about API design",
        "project": "shipment-api",
        "evidence": list(labels),
        "strategy": None,
        "rationale": "the work is recent and the evidence states it plainly",
        "decline_reason": "",
    }
    payload.update(overrides)
    return ReasoningAnswer(
        publish=payload["publish"],
        topic=payload["topic"],
        angle=payload["angle"],
        project=payload["project"],
        evidence_labels=tuple(payload["evidence"]),
        strategy=payload["strategy"],
        rationale=payload["rationale"],
        decline_reason=payload["decline_reason"],
    )


def agent(reasoner=None, generator=None, verifier=None, *, history=None,
          **kwargs) -> BrandingAgent:
    """A fully-wired Agent with Step 9's real verifier and a fake reasoner."""
    return BrandingAgent(
        reasoner=reasoner or FakeReasoner(),
        generator=generator or PostGenerator(llm=FakeLLM([generation_reply()])),
        verifier=verifier or EvidenceVerifier(judge=FakeJudge()),
        history=history,
        **kwargs,
    )


def identity(result: AgentResult):
    """Everything a decision is, without the objects behind it."""
    return (result.decision, result.reason, result.failure, result.attempts_made)


# ------------------------------------------------------ DO_NOT_PUBLISH is real ---

def test_do_not_publish_is_reachable():
    """The answer Step 10 exists to make possible: a normal, successful no."""
    reasoner = FakeReasoner(ReasoningAnswer(
        publish=False, decline_reason="the course is not finished yet"
    ))

    result = agent(reasoner).run(evidence_context())

    assert result.decision is AgentDecision.DO_NOT_PUBLISH
    assert result.reason is NoPublishReason.NO_VALUE
    assert result.is_publishable is False


def test_do_not_publish_is_respected():
    """A declined run writes nothing, publishes nothing and verifies nothing."""
    reasoner = FakeReasoner(ReasoningAnswer(publish=False, decline_reason="no"))
    generator = FakeGenerator([PASSING_POST])

    result = agent(reasoner, generator=generator).run(evidence_context())

    assert result.decision is AgentDecision.DO_NOT_PUBLISH
    assert result.proposal is None
    assert result.draft is None
    assert result.verification is None
    assert generator.requests == [], "a declined run must not write a draft"


def test_a_declined_run_is_a_success_and_not_a_failure():
    """The distinction the workflow's notification decision rests on."""
    reasoner = FakeReasoner(ReasoningAnswer(publish=False, decline_reason="no"))

    result = agent(reasoner).run(evidence_context())

    assert result.failed is False
    assert result.failure is None
    assert result.reason not in FAILURE_REASONS


def test_a_context_with_no_evidence_is_decided_without_calling_the_reasoner():
    """Paying for a request the context has already answered is not a
    judgement call, and a model asked to write anyway is being invited to
    invent."""
    reasoner = FakeReasoner(proposal_answer())

    result = agent(reasoner).run(guidance_only_context())

    assert result.decision is AgentDecision.DO_NOT_PUBLISH
    assert result.reason is NoPublishReason.NO_EVIDENCE
    assert reasoner.calls == 0
    assert guidance_only_context().evidence_status is EvidenceStatus.INSUFFICIENT


def test_generation_declining_is_a_result_and_not_a_failure():
    """A writer given evidence that refuses to write one lands on
    DO_NOT_PUBLISH, which is a success."""
    from app.generation import DeclineReason, GenerationMetadata, GenerationOutcome, GenerationResult

    class DecliningGenerator:
        def __init__(self):
            self.requests = []

        def generate(self, request):
            self.requests.append(request)
            return GenerationResult(
                outcome=GenerationOutcome.DECLINED,
                metadata=GenerationMetadata(model_id="fake",
                                            prompt_version="fake"),
                decline_reason=DeclineReason.MODEL_DECLINED,
                decline_message="the evidence does not support a post",
            )

    result = agent(FakeReasoner(proposal_answer()),
                   generator=DecliningGenerator()).run(evidence_context())

    assert result.decision is AgentDecision.DO_NOT_PUBLISH
    assert result.reason is NoPublishReason.GENERATION_DECLINED
    assert result.failed is False
    assert result.proposal is not None, "the proposal is kept for the audit"


# ------------------------------------------------------------ exactly one agent ---

def test_exactly_one_agent_exists_in_the_repository():
    """No multi-agent decomposition, no planner/critic pair, no framework.

    Asserted over the whole package tree rather than over this package, so a
    second agent introduced anywhere is a failure here.
    """
    import ast

    root = Path(__file__).resolve().parents[1] / "app"
    found: dict[str, str] = {}
    for module in sorted(root.rglob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.endswith("Agent"):
                found[node.name] = str(module.relative_to(root))

    assert found == {"BrandingAgent": "agent/agent.py"}


def test_the_reasoner_is_asked_exactly_once_per_run():
    """One call, not a conversation: there is no second turn to take."""
    reasoner = FakeReasoner(proposal_answer())

    agent(reasoner).run(evidence_context())

    assert reasoner.calls == 1


# --------------------------------------------------------------- the gate holds ---

def test_a_publish_decision_cannot_be_built_without_a_passing_verification():
    """The one lie an agent could tell, made unconstructible."""
    ctx = evidence_context()
    proposal = AgentProposal(topic="evidence", context=ctx,
                             evidence=ctx.evidence_items())

    with pytest.raises(ValueError, match="needs the verification"):
        AgentResult(decision=AgentDecision.PUBLISH, proposal=proposal)

    failing = VerificationResult(outcome=VerificationOutcome.REJECTED, violations=(
        _violation(),))
    with pytest.raises(ValueError, match="did not pass"):
        AgentResult(decision=AgentDecision.PUBLISH, proposal=proposal,
                    verification=failing)


def test_a_publish_decision_cannot_also_carry_a_failure():
    ctx = evidence_context()
    proposal = AgentProposal(topic="evidence", context=ctx,
                             evidence=ctx.evidence_items())
    passed = VerificationResult(outcome=VerificationOutcome.PASS)

    with pytest.raises(ValueError, match="reasoning failure"):
        AgentResult(
            decision=AgentDecision.PUBLISH, proposal=proposal,
            verification=passed,
            failure=_failure(),
        )


def test_a_do_not_publish_decision_must_say_why():
    with pytest.raises(ValueError, match="must say why"):
        AgentResult(decision=AgentDecision.DO_NOT_PUBLISH)


def test_a_failure_is_present_exactly_when_the_reason_is_one():
    with pytest.raises(ValueError, match="exactly when"):
        AgentResult(decision=AgentDecision.DO_NOT_PUBLISH,
                    reason=NoPublishReason.REASONING_FAILED)
    with pytest.raises(ValueError, match="exactly when"):
        AgentResult(decision=AgentDecision.DO_NOT_PUBLISH,
                    reason=NoPublishReason.NO_VALUE, failure=_failure())


def _violation():
    from app.verification import Severity, Violation, ViolationKind

    return Violation(kind=ViolationKind.UNSUPPORTED_REFERENCE,
                     severity=Severity.REJECT, detail="nothing supports this")


def _failure():
    from app.agent import AgentFailure

    return AgentFailure(category=AgentFailureCategory.REASONING_UNAVAILABLE,
                        detail="unreachable")


def test_the_real_gate_refuses_a_fabricated_draft_and_the_agent_obeys():
    """Step 9 stays authoritative inside the Agent: a draft that cites a
    metric nothing supports is rejected, and the Agent reports the rejection
    rather than routing around it."""
    generator = PostGenerator(llm=FakeLLM([generation_reply(post=FABRICATED_POST)]))
    reasoner = FakeReasoner(proposal_answer())

    result = agent(reasoner, generator=generator).run(evidence_context())

    assert result.decision is AgentDecision.DO_NOT_PUBLISH
    assert result.reason is NoPublishReason.GATE_REJECTED
    assert result.verification is not None
    assert result.verification.outcome is VerificationOutcome.REJECTED
    assert result.verification.is_publishable is False
    assert result.is_publishable is False
    assert result.draft is not None, "the refused draft is kept for the audit"
    assert result.proposal is not None


def test_the_gate_passing_is_the_only_way_to_a_publication():
    reasoner = FakeReasoner(proposal_answer())
    generator = PostGenerator(llm=FakeLLM([generation_reply()]))

    result = agent(reasoner, generator=generator).run(evidence_context())

    assert result.decision is AgentDecision.PUBLISH
    assert result.is_publishable is True
    assert result.verification is not None
    assert result.verification.outcome is VerificationOutcome.PASS
    assert result.draft is not None
    assert result.text == PASSING_POST
    assert result.reason is None
    assert result.failed is False


def test_a_published_proposal_records_the_reasoner_and_the_prompt():
    result = agent(FakeReasoner(proposal_answer())).run(evidence_context())

    assert result.proposal.reasoner == "fake-reasoner"
    assert result.proposal.prompt_version == "fake-reasoner-v1"


# ----------------------------------------------------- evidence selection only ---

def test_evidence_selection_is_limited_to_retrieved_evidence():
    """Whatever the reasoner selects, the proposal's evidence is a subset of
    the context's own items — by identity, not by resemblance."""
    ctx = evidence_context()
    known = {(item.source, item.chunk_id) for item in ctx.evidence_items()}

    result = agent(FakeReasoner(proposal_answer(labels=("E2",)))).propose(ctx)

    assert isinstance(result, AgentProposal)
    assert result.evidence_keys
    assert set(result.evidence_keys) <= known
    assert len(result.evidence) == 1


def test_selected_evidence_survives_generations_own_check():
    """Step 8 independently refuses evidence the context does not hold, so a
    proposal that reached it with foreign material would fail loudly rather
    than be written from."""
    ctx = evidence_context()
    known = {(item.source, item.chunk_id) for item in ctx.evidence_items()}
    proposal = agent(FakeReasoner(proposal_answer(labels=("E1", "E2")))
                     ).propose(ctx)

    request = proposal.generation_request()

    assert request.evidence == proposal.evidence
    assert set(proposal.evidence_keys) <= known
    assert len(proposal.evidence) == 2, "both offered items were selected"


def test_unsupported_evidence_identifiers_are_rejected():
    """Refused, not dropped: a model naming a source retrieval never returned
    is a fact about the run, and silently discarding it is how an invented
    citation becomes a published one."""
    reasoner = FakeReasoner(proposal_answer(labels=("E1", "E99")))
    generator = FakeGenerator([PASSING_POST])

    result = agent(reasoner, generator=generator).run(evidence_context())

    assert result.decision is AgentDecision.DO_NOT_PUBLISH
    assert result.reason is NoPublishReason.INVALID_PROPOSAL
    assert result.failure is not None
    assert result.failure.category is AgentFailureCategory.EVIDENCE_SELECTION
    assert "E99" in result.failure.detail
    assert generator.requests == [], "nothing may be written from a bad selection"


def test_a_label_resolves_to_the_contexts_item_and_not_to_the_models_words():
    """The answer names a label; the proposal carries the corpus's own
    provenance for it. There is no step at which a model's words become a
    source."""
    ctx = evidence_context()

    proposal = agent(FakeReasoner(proposal_answer(
        topic="completed_projects", labels=("E2",),
    ))).propose(ctx)

    assert isinstance(proposal, AgentProposal)
    assert proposal.evidence_keys == (("projects/portfolio.md", "b2c3d4:0"),)
    assert proposal.evidence[0].content == OTHER_EVIDENCE_TEXT


def test_the_answer_has_nowhere_to_put_an_invented_source():
    """A reasoner cannot name a source, a chunk id or a citation at all: the
    only field that can carry evidence is a list of labels, and a label
    resolves against the run's own options or does not exist."""
    from dataclasses import fields

    assert {field.name for field in fields(ReasoningAnswer)} == {
        "publish", "topic", "angle", "project", "evidence_labels", "strategy",
        "rationale", "decline_reason",
    }


def test_a_topic_that_is_not_an_opportunity_is_refused():
    reasoner = FakeReasoner(proposal_answer(topic="kubernetes-migrations"))

    result = agent(reasoner).run(evidence_context())

    assert result.decision is AgentDecision.DO_NOT_PUBLISH
    assert result.reason is NoPublishReason.INVALID_PROPOSAL
    assert result.failure.category is AgentFailureCategory.UNUSABLE_ANSWER


def test_publishing_with_no_evidence_selected_is_refused():
    """A post with nothing behind it is not a proposal, however confidently
    the reasoner asserts one."""
    reasoner = FakeReasoner(proposal_answer(labels=()))

    result = agent(reasoner).run(evidence_context())

    assert result.reason is NoPublishReason.INVALID_PROPOSAL
    assert result.failure.category is AgentFailureCategory.UNUSABLE_ANSWER


def test_a_strategy_outside_the_allowed_vocabulary_is_refused():
    from app.retrieval.models import STRATEGIES

    ctx = evidence_context()
    allowed = agent(FakeReasoner(proposal_answer(strategy="bm25")),
                    strategies=STRATEGIES).propose(ctx)
    assert isinstance(allowed, AgentProposal)
    assert allowed.strategy == "bm25"

    refused = agent(FakeReasoner(proposal_answer(strategy="psychic")),
                    strategies=STRATEGIES).run(ctx)
    assert refused.reason is NoPublishReason.INVALID_PROPOSAL
    assert refused.failure.category is AgentFailureCategory.UNUSABLE_ANSWER


def test_without_a_strategy_vocabulary_the_contexts_own_strategy_is_kept():
    """Nothing to choose from means no choice to make — and the strategy kept
    is a real one that really found this evidence, not one invented here."""
    ctx = evidence_context()

    result = agent(FakeReasoner(proposal_answer())).propose(ctx)

    assert result.strategy == ctx.strategy == "vector"


def test_topics_are_the_contexts_own_non_empty_evidence_sections():
    ctx = evidence_context()

    topics = topic_candidates(ctx)

    assert [topic.name for topic in topics] == ["evidence", "completed_projects"]
    assert all(topic.item_count for topic in topics)
    assert "writing_style" not in {topic.name for topic in topics}


def test_the_agent_cannot_propose_a_topic_it_was_not_offered():
    """The offered set is derived from the context, so a topic the evidence
    does not support has no way to become a proposal."""
    ctx = evidence_context()
    offered = {topic.name for topic in topic_candidates(ctx)}

    assert offered == {"evidence", "completed_projects"}
    assert "audit" not in offered


# -------------------------------------------------------------- history access ---

def test_publishing_history_is_read_through_the_read_service_only():
    history = FakeHistory(topics=(UsageCount(
        value="completed_projects", uses=3, last_used_at="2026-01-01T00:00:00Z",
        publication_ids=("pub-1",),
    ),))

    result = agent(FakeReasoner(proposal_answer()), history=history
                   ).run(evidence_context())

    assert result.decision is AgentDecision.PUBLISH
    assert history.calls, "the read service was never consulted"
    assert {name for name, _ in history.calls} == {
        "recent_publications", "requires_review", "recent_topics",
        "recent_projects", "recent_evidence",
    }, "only the read half of Step 6 may be called"


def test_the_real_read_service_satisfies_the_protocol():
    """Step 6's ``PublishingHistory`` is what a workflow passes, without it
    knowing this protocol exists."""
    assert isinstance(FakeHistory(), PublicationHistoryReader)


def test_history_reaches_the_writer_as_constraints_and_never_as_evidence():
    """What the audience has seen shapes the writing; it is not a fact about
    the person, and it never enters the evidence block."""
    history = FakeHistory(topics=(UsageCount(
        value="audit", uses=3, last_used_at="2026-01-01T00:00:00Z",
        publication_ids=("pub-1",),
    ),))
    generator = FakeGenerator([PASSING_POST])

    agent(FakeReasoner(proposal_answer()), generator=generator,
          history=history).run(evidence_context())

    constraints = generator.requests[0].constraints
    assert constraints.recent_topics == ("audit",)

    ctx = evidence_context()
    prompt = build_reasoning_prompt(ReasoningRequest(
        context=ctx, topics=topic_candidates(ctx),
        evidence=evidence_options(ctx),
        history=read_publication_history(history),
    ))
    assert "audit" in prompt.history_block
    assert "audit" not in prompt.evidence_block
    assert "audit" not in prompt.opportunities_block


def test_a_history_with_an_unresolved_attempt_is_reported_to_the_reasoner():
    history = FakeHistory(requires_review=(PublicationSummary(
        publication_id="pub-9", run_id="run-9",
        published_at="2026-01-01T00:00:00Z", content_hash="abc",
    ),))

    reasoner = FakeReasoner(proposal_answer())
    agent(reasoner, history=history).run(evidence_context())

    digest = reasoner.requests[0].history
    assert digest.unresolved_ambiguity is True
    assert digest.requires_review[0].publication_id == "pub-9"


def test_the_real_history_service_over_a_real_store_is_accepted(state_store):
    """The wiring a workflow will use, exercised once: a real store, a real
    read service, and an empty history — which is what a first run has."""
    history = PublishingHistory(state_store)

    result = agent(FakeReasoner(proposal_answer()), history=history
                   ).run(evidence_context())

    assert result.decision is AgentDecision.PUBLISH
    assert result.verification.is_publishable is True


def test_a_real_publication_is_visible_to_the_next_run(state_store):
    """History reaches the Agent through the store, not through a memory of
    the previous run — so a process restart changes nothing."""
    from app.integrations.linkedin.enums import PublicationOutcome
    from app.integrations.linkedin.models import PublicationResult
    from app.publishing import PublishingService, PublishRequest

    run = state_store.start_run("branding")
    PublishingService(state_store, transport=lambda _: PublicationResult(
        outcome=PublicationOutcome.PUBLISHED, message="ok", api_version="202601",
        attempted_at=to_iso(utc_now()), post_id="urn:li:share:1",
    )).publish(
        PublishRequest(content="an earlier post", topic="evidence",
                       evidence=(evidence_ref("evidence/backend/fastapi.md",
                                              "a1b2c3:0"),)),
        run.run_id,
    )

    history = PublishingHistory(state_store)
    reasoner = FakeReasoner(proposal_answer())
    agent(reasoner, history=history).run(evidence_context())

    digest = reasoner.requests[0].history
    assert [row.value for row in digest.topics] == ["evidence"]
    assert digest.evidence[0].source_path == "evidence/backend/fastapi.md"
    assert digest.publications[0].publication_id


def test_no_history_is_a_normal_answer_and_not_an_error():
    result = agent(FakeReasoner(proposal_answer()), history=None
                   ).run(evidence_context())

    assert result.decision is AgentDecision.PUBLISH


# ------------------------------------------------------- reasoning failure only ---

def test_reasoning_failure_becomes_do_not_publish():
    reasoner = FakeReasoner(error=ReasoningUnavailable("no credential"))
    generator = FakeGenerator([PASSING_POST])

    result = agent(reasoner, generator=generator).run(evidence_context())

    assert result.decision is AgentDecision.DO_NOT_PUBLISH
    assert result.reason is NoPublishReason.REASONING_FAILED
    assert result.failure is not None
    assert result.failure.category is AgentFailureCategory.REASONING_UNAVAILABLE
    assert "no credential" in result.failure.detail
    assert generator.requests == [], "there is no fallback that publishes"


def test_a_failure_is_exposed_for_the_workflow_to_notify():
    """The Agent does not notify; it hands over everything a notification
    needs and stops."""
    reasoner = FakeReasoner(error=ReasoningUnavailable("endpoint unreachable"))

    result = agent(reasoner).run(evidence_context())

    record = result.to_record()
    assert record["failure"]["category"] == "reasoning_unavailable"
    assert record["failure"]["detail"] == "endpoint unreachable"
    assert record["decision"] == "do_not_publish"


def test_an_unreadable_model_answer_is_a_reasoning_failure():
    """Driven through the real reasoner class, with a fake client: a reply
    nobody can parse is an answer nobody can act on, and it declines."""
    for reply in ("not json at all", json.dumps({"topic": "evidence"}),
                  json.dumps({"publish": "yes"})):
        reasoner = LlmContentReasoner(llm=FakeLLM([reply]))
        result = agent(reasoner).run(evidence_context())

        assert result.decision is AgentDecision.DO_NOT_PUBLISH
        assert result.reason is NoPublishReason.REASONING_FAILED


def test_the_real_reasoner_reads_a_well_formed_answer():
    reply = json.dumps({
        "publish": True, "topic": "evidence", "angle": "one angle",
        "project": "shipment-api", "evidence": ["E1"], "strategy": None,
        "rationale": "worth saying", "decline_reason": "",
    })
    reasoner = LlmContentReasoner(llm=FakeLLM([reply]))

    result = agent(reasoner).run(evidence_context())

    assert result.decision is AgentDecision.PUBLISH
    assert result.proposal.topic == "evidence"
    assert result.proposal.reasoner == "llm-content-reasoner"


def test_the_reasoner_being_unavailable_is_not_reported_as_a_decline():
    """``DO_NOT_PUBLISH`` and a failed run are different facts, and only one
    of them is something to notify about."""
    declined = agent(FakeReasoner(ReasoningAnswer(
        publish=False, decline_reason="nothing worth saying"))).run(
            evidence_context())
    broken = agent(FakeReasoner(error=ReasoningUnavailable("boom"))).run(
        evidence_context())

    assert identity(declined)[:2] == (AgentDecision.DO_NOT_PUBLISH,
                                      NoPublishReason.NO_VALUE)
    assert identity(broken)[:2] == (AgentDecision.DO_NOT_PUBLISH,
                                    NoPublishReason.REASONING_FAILED)
    assert declined.failed is False and broken.failed is True


# ------------------------------------------------------------ bounded reasoning ---

def test_the_revision_loop_terminates_within_its_bound():
    """``PLAN.md``: an unbounded revise loop is a failure mode, not a feature.
    The writer here never produces anything that passes, and the loop still
    ends — after exactly the budget plus the first attempt."""
    from app.verification import MAX_REVISION_ATTEMPTS

    generator = FakeGenerator([REVISABLE_POST])
    result = agent(FakeReasoner(proposal_answer()), generator=generator,
                   revision_limit=MAX_REVISION_ATTEMPTS).run(evidence_context())

    assert len(generator.requests) == MAX_REVISION_ATTEMPTS + 1
    assert result.attempts_made == MAX_REVISION_ATTEMPTS
    assert result.decision is AgentDecision.DO_NOT_PUBLISH
    assert result.reason is NoPublishReason.REVISION_EXHAUSTED
    assert result.failed is False, "running out of budget is a decision"


def test_a_zero_budget_ends_after_one_attempt():
    generator = FakeGenerator([REVISABLE_POST])

    result = agent(FakeReasoner(proposal_answer()), generator=generator,
                   revision_limit=0).run(evidence_context())

    assert len(generator.requests) == 1
    assert result.attempts_made == 0
    assert result.reason is NoPublishReason.REVISION_EXHAUSTED


def test_the_loop_is_bounded_however_long_the_writer_keeps_failing():
    """The bound is a function of the budget, not of the model's behaviour:
    a writer that never improves cannot make the loop run longer."""
    for limit in (0, 1, 3):
        generator = FakeGenerator([REVISABLE_POST])
        agent(FakeReasoner(proposal_answer()), generator=generator,
              revision_limit=limit).run(evidence_context())

        assert len(generator.requests) == limit + 1


def test_every_revision_is_driven_by_step_9s_own_notes():
    """The loop's input is the verdict it just received, which is what makes
    a second attempt a bounded operation rather than a guess."""
    ctx = evidence_context()
    verifier = EvidenceVerifier(judge=FakeJudge())

    first_pass = agent(FakeReasoner(proposal_answer()),
                       generator=FakeGenerator([REVISABLE_POST]),
                       verifier=verifier, revision_limit=0).run(ctx)
    expected = first_pass.verification.revision_notes()
    assert expected, "a revisable verdict must say what to change"

    generator = FakeGenerator([REVISABLE_POST, REVISABLE_POST])
    agent(FakeReasoner(proposal_answer()), generator=generator,
          verifier=EvidenceVerifier(judge=FakeJudge()),
          revision_limit=1).run(ctx)

    assert generator.requests[0].constraints.notes == ()
    assert generator.requests[1].constraints.notes == expected


def test_a_revision_can_rescue_a_draft():
    """The loop is worth having: a second attempt that fixes the finding is
    published, which is the difference between REVISE and REJECT."""
    generator = PostGenerator(llm=FakeLLM([
        generation_reply(post=REVISABLE_POST),
        generation_reply(),
    ]))

    result = agent(FakeReasoner(proposal_answer()), generator=generator,
                   revision_limit=1).run(evidence_context())

    assert result.decision is AgentDecision.PUBLISH
    assert result.attempts_made == 1
    assert result.text == PASSING_POST


def test_a_negative_budget_is_refused():
    with pytest.raises(ValueError, match="must not be negative"):
        agent(FakeReasoner(), revision_limit=-1)


def test_a_run_returns_one_outcome_and_never_a_second_proposal():
    """A run produces a single result, whatever happens inside it — there is
    no shape in which it could publish twice."""
    llm = FakeLLM([generation_reply()])

    result = agent(FakeReasoner(proposal_answer()),
                   generator=PostGenerator(llm=llm)).run(evidence_context())

    assert isinstance(result, AgentResult)
    assert result.decision is AgentDecision.PUBLISH
    assert len(llm.calls) == 1, "one post per run, which is the limit"


# --------------------------------------------------------------- reproducibility ---

def test_the_decision_is_reproducible_under_a_fake_reasoner():
    def once():
        return agent(
            FakeReasoner(proposal_answer()),
            generator=PostGenerator(llm=FakeLLM([generation_reply()])),
            history=FakeHistory(topics=(UsageCount(
                value="evidence", uses=1,
                last_used_at="2026-01-01T00:00:00Z",
                publication_ids=("pub-1",),
            ),)),
        ).run(evidence_context()).to_record()

    assert once() == once()


def test_the_offered_options_are_a_property_of_the_context_and_not_of_a_run():
    ctx = evidence_context()

    first = evidence_options(ctx)
    second = evidence_options(ctx)

    assert first == second
    assert [option.label for option in first] == ["E1", "E2"]


def test_the_prompt_renders_the_same_bytes_twice():
    ctx = evidence_context()
    request = ReasoningRequest(
        context=ctx, topics=topic_candidates(ctx),
        evidence=evidence_options(ctx), history=read_publication_history(None),
        strategies=("vector", "bm25"),
    )

    assert (build_reasoning_prompt(request).render()
            == build_reasoning_prompt(request).render())


def test_the_prompt_separates_the_opportunities_from_the_evidence():
    """``PLAN.md`` Step 8's rule, applied to the reasoning call: a model told
    *here is what you may write about* and *here is what you may cite* in one
    undifferentiated block cannot tell the two apart."""
    ctx = evidence_context()
    prompt = build_reasoning_prompt(ReasoningRequest(
        context=ctx, topics=topic_candidates(ctx),
        evidence=evidence_options(ctx), history=read_publication_history(None),
    ))

    assert prompt.topic_names == ("evidence", "completed_projects")
    assert prompt.labels == ("E1", "E2")
    assert prompt.version == AGENT_PROMPT_VERSION
    assert "OPPORTUNITIES" in prompt.body()
    assert "EVIDENCE" in prompt.body()
    assert prompt.messages()[0]["role"] == "system"


def test_the_answer_parser_is_strict_about_the_shape_and_forgiving_about_fences():
    fenced = "```json\n" + json.dumps({"publish": False}) + "\n```"

    assert parse_reasoning_answer(fenced).publish is False
    for bad in ("", "no json here", json.dumps([1, 2]),
                json.dumps({"publish": "true"}),
                json.dumps({"publish": True, "evidence": "E1"})):
        with pytest.raises(ReasoningUnavailable):
            parse_reasoning_answer(bad)


def test_empty_labels_and_blank_text_are_read_as_absent():
    answer = parse_reasoning_answer(json.dumps({
        "publish": True, "topic": "evidence", "angle": "   ",
        "project": "", "evidence": ["  ", "E1"],
    }))

    assert answer.angle is None
    assert answer.project is None
    assert answer.evidence_labels == ("E1",)


# -------------------------------------------------------------------- milestone ---

def test_a_full_simulated_run_is_deterministic():
    """The milestone: context -> Agent decision -> generation proposal ->
    verification -> final outcome, run twice, with fakes throughout.

    Nothing here reaches the network, a model, a store or LinkedIn; the
    assertion that matters is that the same inputs produce the same bytes
    twice, which is what makes this a simulated run rather than one
    observation of one process.
    """
    def once():
        reasoner = FakeReasoner(proposal_answer(topic="evidence", labels=("E1",)))
        generator = PostGenerator(llm=FakeLLM([generation_reply()]))
        verifier = EvidenceVerifier(judge=FakeJudge())
        history = FakeHistory(topics=(UsageCount(
            value="completed_projects", uses=2,
            last_used_at="2026-01-01T00:00:00Z", publication_ids=("pub-1",),
        ),))

        run = agent(reasoner, generator=generator, verifier=verifier,
                    history=history)
        ctx = evidence_context()
        proposal = run.propose(ctx)
        result = run.run(ctx)

        assert isinstance(proposal, AgentProposal)
        assert proposal.topic == "evidence"
        assert proposal.evidence_keys == (("evidence/backend/fastapi.md",
                                           "a1b2c3:0"),)
        assert reasoner.requests[0].history.topics[0].value == (
            "completed_projects"
        )
        assert result.decision is AgentDecision.PUBLISH
        assert result.is_publishable is True
        assert result.verification.fully_verified is True
        assert result.proposal.topic == "evidence"
        return result.to_record()

    first, second = once(), once()

    assert first == second
    assert first["decision"] == "publish"
    assert first["verification"]["outcome"] == VerificationOutcome.PASS.value
    assert first["proposal"]["evidence"] == [{
        "source": "evidence/backend/fastapi.md", "chunk_id": "a1b2c3:0",
        "evidence_state": "VERIFIED",
    }]


def test_the_record_is_provenance_and_carries_no_secret():
    """What a run hands to a workflow is references and a decision — the text
    of a post lives with the draft, not in the agent's record."""
    result = agent(FakeReasoner(proposal_answer())).run(evidence_context())

    record = result.to_record()
    assert set(record) == {
        "decision", "reason", "attempts_made", "rationale", "failure",
        "proposal", "verification",
    }
    assert set(record["proposal"]) == {
        "topic", "angle", "project", "strategy", "prompt_version", "reasoner",
        "evidence",
    }
    assert not re.search(r"sk-[a-z0-9-]{8,}", repr(record))
