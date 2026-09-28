"""Learning achievement vs professional experience in opportunity reasoning.

Regression cover for run ``branding-20260928T210017Z-31fb20c8``, which
declined an IBM learning opportunity with ``NO_VALUE`` because its evidence
honestly states the course "does not prove professional expertise" and "must
not be claimed as professional experience". The reasoner converted an
honesty constraint on *framing* into a ban on *publishing*:

    learning -> not professional experience -> no LinkedIn value

The documented policy (``docs/evaluation/quality-gates.md`` §3,
``data/evidence/README.md``) says the opposite: ``LEARNING``/``ASPIRATIONAL``
evidence is legitimate when the claim makes the same admission ("I'm learning
X" is not an upgrade). The fix lives in the reasoning instructions
(``app/agent/prompt.py``): "not professional experience" does not mean "not
publishable", while every anti-overclaiming rule stays absolute.

Every test drives the Agent with plain fakes and a context built from literal
chunks. No API key, no network, no model, no LinkedIn.
"""
from app.agent import (
    AGENT_PROMPT_VERSION,
    AgentDecision,
    AgentProposal,
    BrandingAgent,
    NoPublishReason,
    ReasoningAnswer,
    ReasoningRequest,
    build_reasoning_prompt,
    evidence_options,
    topic_candidates,
)
from app.agent.models import HistoryDigest
from app.agent.prompt import INSTRUCTIONS
from app.context.builder import build_context
from app.generation import (
    EvidenceCitation,
    GeneratedPost,
    GenerationMetadata,
    GenerationOutcome,
    GenerationResult,
)
from app.retrieval.models import RetrievalResult, RetrievedDocument
from app.verification import EvidenceVerifier, JudgeVerdict, JudgementRequest

# ------------------------------------------------------------------ fixtures ---

#: Representative excerpt of the honesty caveat that previously triggered the
#: conflation (cf. ``data/in_progress_courses/ibm_rag_and_agentic_ai.md``:
#: "The course is learning; it does not prove professional expertise.").
COURSE_EVIDENCE = (
    "IBM Build Multimodal Generative AI Applications (Course 5 of the IBM "
    "RAG and Agentic AI Professional Certificate): completed Sep 2026. "
    "Multimodal foundations, image captioning, multimodal RAG and full-stack "
    "Flask/Gradio apps. This record is evidence of completed learning on "
    "multimodal generative AI only; it does not prove professional expertise."
)

#: Representative excerpt of the applied half (cf.
#: ``data/evidence/ai/multimodal_application.md``: application DOCUMENTED,
#: "I completed IBM's multimodal AI course and built three multimodal apps").
BUILDS_EVIDENCE = (
    "While completing the course I built three multimodal apps: Style Finder, "
    "a Gradio web app that retrieves outfits with ResNet50 embeddings and "
    "narrates with Llama 4 vision; AI Nutrition Coach, a Flask app estimating "
    "calories from food photos; and an Image Captioning CLI with provider "
    "abstraction, tests and Docker packaging."
)

#: Representative excerpt of the technical lesson (cf.
#: ``data/stories_lessons/vision_model_output_guarantees.md``).
LESSON_EVIDENCE = (
    "Vision-language models do not reliably return the sections the UI needs, "
    "so I treat the model output as unreliable input: refusal/truncation "
    "detection with deterministic re-attach of the retrieval result in "
    "Style Finder."
)

PROJECT_EVIDENCE = (
    "Built a shipment API with FastAPI and SQLAlchemy models and Alembic "
    "migrations; the API returns shipments to the tracking dashboard."
)


def doc(source: str, *, category: str, chunk_id: str, content: str,
        evidence_state: str | None = None) -> RetrievedDocument:
    metadata = {
        "source": source, "category": category,
        "document_type": "unknown",
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


def learning_only_context():
    """A completed course with meaningful detail — and an honesty caveat."""
    return context(doc(
        "data/in_progress_courses/ibm_rag_and_agentic_ai.md",
        category="in_progress_courses", chunk_id="c0ffee:4",
        content=COURSE_EVIDENCE, evidence_state="LEARNING",
    ))


def multimodal_evidence_context():
    """The post-sync shape of the aggregation file: one ``evidence`` section
    whose items carry both the learning record (LEARNING) and the applied
    builds plus lesson (DOCUMENTED). This is the existing
    architecture-consistent bridge — ``data/evidence/ai/``
    ``multimodal_application.md`` combines both halves with cross-source
    provenance, so the reasoner sees related work without any KB dump."""
    return context(
        doc("data/evidence/ai/multimodal_application.md",
            category="evidence", chunk_id="aa0001:0",
            content=COURSE_EVIDENCE, evidence_state="LEARNING"),
        doc("data/evidence/ai/multimodal_application.md",
            category="evidence", chunk_id="aa0001:1",
            content=BUILDS_EVIDENCE, evidence_state="DOCUMENTED"),
        doc("data/evidence/ai/multimodal_application.md",
            category="evidence", chunk_id="aa0001:2",
            content=LESSON_EVIDENCE, evidence_state="DOCUMENTED"),
    )


def project_context():
    return context(doc(
        "evidence/backend/fastapi.md", category="evidence",
        chunk_id="a1b2c3:0", content=PROJECT_EVIDENCE,
        evidence_state="VERIFIED",
    ))


# ------------------------------------------------------------------ fakes ---


class FakeReasoner:
    name = "fake-reasoner"
    prompt_version = "fake-reasoner-v1"

    def __init__(self, answer: ReasoningAnswer):
        self.answer = answer

    def reason(self, request: ReasoningRequest) -> ReasoningAnswer:
        return self.answer


class FakeGenerator:
    """Citations come from the request's own evidence, so a fixture cannot
    cite something the proposal did not select."""

    def __init__(self, contents):
        self.contents = list(contents)

    def generate(self, request):
        index = 0
        return GenerationResult(
            outcome=GenerationOutcome.GENERATED,
            metadata=GenerationMetadata(
                model_id="fake", prompt_version="fake"),
            post=GeneratedPost(content=self.contents[index], citations=tuple(
                EvidenceCitation(label=f"E{position}", source=item.source,
                                 chunk_id=item.chunk_id,
                                 evidence_state=item.evidence_state)
                for position, item in enumerate(request.evidence, start=1)
            )),
        )


class FakeJudge:
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


def publish_answer(topic, labels, angle="Completed the course and built three apps while learning"):
    return ReasoningAnswer(
        publish=True, topic=topic, angle=angle, project=None,
        evidence_labels=tuple(labels), strategy=None,
        rationale="substantive hands-on learning achievement",
        decline_reason="",
    )


def run_agent(ctx, answer: ReasoningAnswer, draft: str):
    agent = BrandingAgent(
        reasoner=FakeReasoner(answer),
        generator=FakeGenerator([draft]),
        verifier=EvidenceVerifier(judge=FakeJudge()),
        history=None,
    )
    return agent.run(ctx)


# ------------------------------------------------------------------ tests ---


def test_prompt_states_learning_is_not_unpublishable():
    """The semantic distinction itself, pinned as text: framing vs eligibility."""
    assert AGENT_PROMPT_VERSION == "branding-agent-v3"
    assert '"Not professional experience" does not mean "not publishable"' \
        in INSTRUCTIONS
    assert "merely because the evidence states it\ndoes not prove professional expertise" \
        .replace("\n", " ") in INSTRUCTIONS.replace("\n", " ")
    # The honesty prohibitions stay absolute.
    assert "Never frame such\nmaterial as professional experience" \
        .replace("\n", " ") in INSTRUCTIONS.replace("\n", " ")
    # Declining thin content stays a normal, correct answer.
    assert "Declining is a normal, correct answer" in INSTRUCTIONS


def test_learning_topic_is_offered_and_resolvable():
    """A. A LEARNING-state course section is offered as a topic, and an
    honest publish answer over it resolves to a proposal — nothing in the
    deterministic path refuses learning evidence."""
    ctx = learning_only_context()
    names = tuple(topic.name for topic in topic_candidates(ctx))
    assert "in_progress_courses" in names
    agent = BrandingAgent(
        reasoner=FakeReasoner(publish_answer("in_progress_courses", ("E1",))),
        generator=FakeGenerator(["unused"]),
        verifier=EvidenceVerifier(judge=FakeJudge()),
        history=None,
    )
    proposal = agent.propose(ctx)
    # propose returns a proposal (not a DO_NOT_PUBLISH result) for publish:true.
    assert isinstance(proposal, AgentProposal)
    assert proposal.topic == "in_progress_courses"


def test_multimodal_certificate_plus_builds_can_publish():
    """B + multimodal case. Certificate + hands-on builds + lesson, honestly
    framed as learning/achievement, reaches PUBLISH through the real gates."""
    ctx = multimodal_evidence_context()
    assert tuple(topic.name for topic in topic_candidates(ctx)) == ("evidence",)
    draft = (
        "I completed IBM's Build Multimodal Generative AI Applications course "
        "and built three multimodal apps while learning: a fashion-style "
        "finder, a nutrition coach, and an image captioning service."
    )
    result = run_agent(
        ctx, publish_answer("evidence", ("E1", "E2", "E3")), draft)
    assert result.decision is AgentDecision.PUBLISH
    assert result.is_publishable


def test_course_must_not_be_framed_as_professional_experience():
    """C. The prohibitions hold: a draft claiming professional experience /
    production work from course evidence is refused by the gates."""
    ctx = learning_only_context()
    draft = (
        "Completing this course proves I am a professional multimodal AI "
        "engineer with production experience."
    )
    result = run_agent(
        ctx, publish_answer("in_progress_courses", ("E1",)), draft)
    assert not result.is_publishable
    assert result.reason is NoPublishReason.GATE_REJECTED


def test_certificate_must_not_imply_expertise():
    """D. Course completion alone must not become a mastery claim."""
    ctx = learning_only_context()
    draft = (
        "I completed the IBM multimodal course, which makes me an expert in "
        "multimodal AI."
    )
    result = run_agent(
        ctx, publish_answer("in_progress_courses", ("E1",)), draft)
    assert not result.is_publishable
    assert result.reason is NoPublishReason.GATE_REJECTED


def test_thin_certificate_content_can_still_be_declined():
    """E. The fix is not 'publish every certificate': a decline stays a valid,
    first-class outcome with NO_VALUE."""
    ctx = learning_only_context()
    agent = BrandingAgent(
        reasoner=FakeReasoner(ReasoningAnswer(
            publish=False,
            decline_reason="a bare completion line with no labs, builds or "
                           "lesson is too thin to publish")),
        generator=FakeGenerator(["unused"]),
        verifier=EvidenceVerifier(judge=FakeJudge()),
        history=None,
    )
    result = agent.run(ctx)
    assert result.decision is AgentDecision.DO_NOT_PUBLISH
    assert result.reason is NoPublishReason.NO_VALUE


def test_project_evidence_flow_unchanged():
    """F. Ordinary strong project evidence still flows to PUBLISH."""
    ctx = project_context()
    draft = "I built a shipment API with FastAPI and SQLAlchemy models."
    result = run_agent(ctx, publish_answer("evidence", ("E1",)), draft)
    assert result.decision is AgentDecision.PUBLISH
    assert result.is_publishable


def test_reasoning_prompt_renders_learning_guidance():
    """The assembled prompt a model actually reads carries the distinction."""
    ctx = multimodal_evidence_context()
    request = ReasoningRequest(
        context=ctx,
        topics=topic_candidates(ctx),
        evidence=evidence_options(ctx),
        history=HistoryDigest.empty(),
        strategies=("vector",),
        prompt_version=AGENT_PROMPT_VERSION,
    )
    prompt = build_reasoning_prompt(request)
    rendered = prompt.render()
    assert "does not mean" in rendered and "not publishable" in rendered
    assert "Prefer substance over announcements" in rendered
