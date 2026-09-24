"""Step 9: the gate's contract.

What a caller can rely on: a draft is verified against the context it was
handed and nothing else; every claim is judged on its own and keeps the
provenance of what supports it; guidance never counts as evidence; a failure to
verify is never a pass; and the four ways a verification can end — passed,
needs revision, rejected, and could-not-be-verified — are distinguishable
without reading prose.

Every test drives the verifier with a fake judge and a context built from
literal chunks. No API key, no network, no model, no LinkedIn, and one test
proves the offline claim by removing the credential the real judge would need.
"""
import ast
import json
from pathlib import Path

import pytest

from app import config
from app.context.builder import build_context
from app.context.enums import EvidenceStatus
from app.generation.models import EvidenceCitation, GeneratedPost
from app.retrieval.models import RetrievalResult, RetrievedDocument
from app.verification import (
    EvidenceVerifier,
    JUDGE_PROMPT_VERSION,
    JudgeVerdict,
    JudgementRequest,
    LlmSupportJudge,
    MAX_REVISION_ATTEMPTS,
    RevisionDecision,
    Severity,
    SupportJudgeUnavailable,
    VerificationError,
    VerificationFailureCategory,
    VerificationOutcome,
    VerificationRequest,
    ViolationKind,
    revision_decision,
    verify,
)
from app.verification.judge import build_judgement_messages, parse_judgement

VERIFICATION_PACKAGE = (
    Path(__file__).resolve().parents[1] / "app" / "verification"
)

EVIDENCE_TEXT = (
    "Built a shipment API with FastAPI and SQLAlchemy models and Alembic "
    "migrations; the API returns shipments to the tracking dashboard."
)
COURSE_TEXT = "Completed the IBM RAG applications course."
POSITIONING_TEXT = "Positioned as a backend engineer who ships small services."
STYLE_TEXT = "Write directly, without marketing language."
UNSUPPORTED_CLAIM = "I led a team of nine engineers across three continents."
FABRICATED_REFERENCE = "I cut API latency by 40% with a caching layer."

#: A string that exists nowhere in any context fixture. If it turns up in a
#: verification record, something was written down that should not have been.
SENTINEL = "ZZ-SENTINEL-EVIDENCE-TEXT-ZZ"


# ------------------------------------------------------------------ helpers ---

class FakeJudge:
    """An advisory judge that answers from a list, and remembers being asked.

    Not a framework type, not a model, and not a subclass of anything: the
    boundary is structural, so this is what "injectable" has to mean.
    """

    name = "fake-judge"
    prompt_version = "fake-support-judge-v1"

    def __init__(self, unsupported=(), *, error=None, extra=(), reason=""):
        self.unsupported = set(unsupported)
        self.error = error
        self.extra = tuple(extra)
        self.reason = reason or "the evidence does not state this"
        self.requests: list[JudgementRequest] = []

    def judge(self, request: JudgementRequest) -> tuple[JudgeVerdict, ...]:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return tuple(
            JudgeVerdict(
                claim_index=claim.index,
                supported=claim.index not in self.unsupported,
                reason="" if claim.index not in self.unsupported else self.reason,
            )
            for claim in request.claims
        ) + self.extra


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


def verified_context():
    """One piece of VERIFIED evidence."""
    return context(doc(
        "evidence/backend/fastapi.md", category="evidence", chunk_id="a1b2c3:0",
        content=EVIDENCE_TEXT, evidence_state="VERIFIED",
    ))


def no_evidence_context():
    """Guidance only — the shape Step 4 produces when nothing relevant was
    found, and the shape the verifier has to answer explicitly rather than
    mistake for an empty draft."""
    return context(doc(
        "data/writing_style/alaa_writing_style.md", category="writing_style",
        document_type="writing_style", chunk_id="d4e5f6:1", content=STYLE_TEXT,
    ))


def mixed_context():
    """Evidence, a course, and two pieces of guidance."""
    return context(
        doc("evidence/backend/fastapi.md", category="evidence",
            chunk_id="a1b2c3:0", content=EVIDENCE_TEXT,
            evidence_state="VERIFIED"),
        doc("courses/ibm_rag.md", category="in_progress_courses",
            chunk_id="ffff00:1", content=COURSE_TEXT, evidence_state="LEARNING"),
        doc("data/public_positioning/portfolio.md",
            category="public_positioning", document_type="positioning",
            chunk_id="d4e5f6:0", content=POSITIONING_TEXT),
        doc("data/writing_style/alaa_writing_style.md", category="writing_style",
            document_type="writing_style", chunk_id="d4e5f6:1",
            content=STYLE_TEXT),
    )


def post(content: str, ctx, *, cite=(1,), unresolved=()) -> GeneratedPost:
    """A draft citing the numbered evidence items of ``ctx`` (1-based).

    Citations are built from the context's own items rather than from literal
    source strings, so a fixture cannot accidentally cite something the context
    does not hold — except where a test says so on purpose.
    """
    items = ctx.evidence_items()
    citations = tuple(
        EvidenceCitation(label=f"E{index}", source=items[index - 1].source,
                         chunk_id=items[index - 1].chunk_id,
                         evidence_state=items[index - 1].evidence_state)
        for index in cite
    )
    return GeneratedPost(content=content, citations=citations,
                         unresolved_labels=tuple(unresolved))


def run(content: str, ctx=None, *, judge=None, cite=(1,), unresolved=()):
    """Verify one draft against one context, with a judge when asked."""
    return verify(post(content, ctx or verified_context(), cite=cite,
                       unresolved=unresolved),
                  ctx or verified_context(), judge=judge)


def kinds(result) -> set[ViolationKind]:
    return {v.kind for v in result.all_violations}


# ------------------------------------------------------------- the good case ---

def test_a_supported_claim_passes():
    judge = FakeJudge()
    result = run(
        "I built a shipment API with FastAPI and SQLAlchemy models.", judge=judge
    )

    assert result.outcome is VerificationOutcome.PASS
    assert result.is_publishable is True
    assert result.fully_verified is True
    assert result.all_violations == ()
    assert result.claims[0].verdict.value == "SUPPORTED"
    assert judge.requests, "the advisory judge was never consulted"


def test_a_pass_records_the_judge_that_produced_the_advisory_half():
    result = run("I built a shipment API with FastAPI and SQLAlchemy models.",
                 judge=FakeJudge())

    assert result.judge == "fake-judge"
    assert result.judge_prompt_version == "fake-support-judge-v1"
    assert result.degraded is False


def test_an_unverifiable_draft_never_reaches_a_publishing_service():
    """The one property that must hold for every failing outcome."""
    drafts = [
        ("I led a team of nine engineers across three continents.", 1),
        ("I built a shipment API with FastAPI and SQLAlchemy models.", 1),
    ]
    for content, cite in drafts:
        result = run(content, cite=(cite,), judge=FakeJudge(unsupported=[1]))
        assert result.is_publishable is (
            result.outcome is VerificationOutcome.PASS
        )
        if result.outcome is not VerificationOutcome.PASS:
            assert result.is_publishable is False


# ------------------------------------------------------- claim-level results ---

def test_multiple_claims_are_evaluated_independently():
    result = run(
        "I built a shipment API with FastAPI and SQLAlchemy models. "
        + UNSUPPORTED_CLAIM,
        judge=FakeJudge(),
    )

    first, second = result.claims
    assert first.claim.index == 1 and first.is_supported
    assert second.claim.index == 2 and not second.is_supported
    assert [v.kind for v in second.violations] == [ViolationKind.NO_CITATION]
    assert first.violations == ()


def test_the_verdict_is_not_a_single_opaque_boolean():
    result = run(
        "I built a shipment API with FastAPI and SQLAlchemy models. "
        + UNSUPPORTED_CLAIM,
        judge=FakeJudge(),
    )

    assert result.outcome is VerificationOutcome.REVISION_REQUIRED
    assert result.revision_notes(), "a revision requirement must say what to fix"
    assert "claim 2" in " ".join(result.revision_notes())


def test_a_rejected_claim_is_told_apart_from_an_unsupported_one():
    result = run(
        "I built a shipment API with FastAPI and SQLAlchemy models. "
        + FABRICATED_REFERENCE,
        judge=FakeJudge(),
    )

    verdicts = {c.claim.index: c.verdict.value for c in result.claims}
    assert verdicts == {1: "SUPPORTED", 2: "REJECTED"}
    assert result.outcome is VerificationOutcome.REJECTED


# ------------------------------------------------------------- provenance ---

def test_a_supported_claim_keeps_the_provenance_of_its_evidence():
    ctx = verified_context()
    item = ctx.evidence_items()[0]
    result = verify(
        post("I built a shipment API with FastAPI and SQLAlchemy models.", ctx),
        ctx, judge=FakeJudge(),
    )

    claim = result.claims[0]
    assert len(claim.supporting) == 1
    reference = claim.supporting[0]
    assert reference.source == item.source
    assert reference.chunk_id == item.chunk_id
    assert reference.evidence_state == item.evidence_state
    assert reference.section == "evidence"
    assert reference.label == "E1"


def test_the_record_keeps_provenance_for_every_claim_and_the_draft():
    ctx = verified_context()
    result = verify(
        post("I built a shipment API with FastAPI and SQLAlchemy models.", ctx),
        ctx, judge=FakeJudge(),
    )

    record = result.to_record()
    assert record["claims"][0]["supporting"] == [{
        "source": ctx.evidence_items()[0].source,
        "chunk_id": ctx.evidence_items()[0].chunk_id,
        "evidence_state": "VERIFIED",
        "section": "evidence",
    }]
    assert record["evidence"][0]["chunk_id"] == ctx.evidence_items()[0].chunk_id


def test_a_draft_cannot_cite_evidence_the_context_does_not_hold():
    ctx = verified_context()
    forged = GeneratedPost(
        content="I built a shipment API with FastAPI and SQLAlchemy models.",
        citations=(EvidenceCitation(label="E1",
                                    source="evidence/invented.md",
                                    chunk_id="deadbeef:0",
                                    evidence_state="VERIFIED"),),
    )

    result = verify(forged, ctx, judge=FakeJudge())

    assert result.outcome is VerificationOutcome.REJECTED
    assert ViolationKind.CITATION_NOT_IN_CONTEXT in kinds(result)
    assert result.evidence == ()


def test_a_label_the_evidence_never_offered_is_a_finding():
    result = run("I built a shipment API with FastAPI and SQLAlchemy models.",
                 unresolved=["E7"], judge=FakeJudge())

    assert result.outcome is VerificationOutcome.REJECTED
    assert result.unresolved == ("E7",)
    assert ViolationKind.CITATION_NOT_IN_CONTEXT in kinds(result)


def test_evidence_that_declares_itself_weak_cannot_carry_a_claim():
    """The auditor's rule, through the gate: evidence of learning is not
    evidence of having done the thing."""
    ctx = mixed_context()
    result = verify(
        post("I completed the IBM RAG applications course and now build RAG "
             "applications.", ctx, cite=(2,)),
        ctx, judge=FakeJudge(),
    )

    assert ViolationKind.EVIDENCE_STATE_TOO_WEAK in kinds(result)
    assert result.outcome is VerificationOutcome.REJECTED
    assert result.claims[0].verdict.value == "REJECTED"


def test_a_draft_that_admits_learning_passes_on_learning_evidence():
    ctx = mixed_context()
    result = verify(
        post("I am learning RAG applications through the IBM course.", ctx,
             cite=(2,)),
        ctx, judge=FakeJudge(),
    )

    assert result.outcome is VerificationOutcome.PASS


# ------------------------------------------------- guidance is not evidence ---

def test_positioning_and_style_cannot_satisfy_evidence():
    ctx = mixed_context()
    result = verify(
        post("I am positioned as a backend engineer who ships small services.",
             ctx),
        ctx, judge=FakeJudge(),
    )

    assert ViolationKind.GUIDANCE_AS_EVIDENCE in kinds(result)
    assert result.outcome is VerificationOutcome.REVISION_REQUIRED
    assert result.is_publishable is False


def test_a_draft_grounded_in_guidance_alone_is_never_a_pass():
    ctx = context(doc("data/public_positioning/portfolio.md",
                      category="public_positioning",
                      document_type="positioning", chunk_id="d4e5f6:0",
                      content=POSITIONING_TEXT))
    result = verify(
        post("Positioned as a backend engineer who ships small services.",
             ctx, cite=()),
        ctx, judge=FakeJudge(),
    )

    assert result.is_publishable is False
    assert ViolationKind.EVIDENCE_INSUFFICIENT in kinds(result)


# --------------------------------------------------- insufficient evidence ---

def test_insufficient_evidence_is_an_explicit_result_not_a_failure():
    """``PLAN.md``: a run that could not verify and a run that verified and said
    no are different facts. This is the first; it must not raise."""
    ctx = no_evidence_context()

    result = verify(post("I built a shipment API with FastAPI.", ctx, cite=()),
                    ctx, judge=FakeJudge())

    assert result.evidence_status is EvidenceStatus.INSUFFICIENT
    assert ViolationKind.EVIDENCE_INSUFFICIENT in kinds(result)
    assert result.outcome is VerificationOutcome.REJECTED
    assert result.is_publishable is False


def test_a_context_that_contradicts_itself_fails_closed():
    from dataclasses import replace

    ctx = replace(context(), evidence_status=EvidenceStatus.SUFFICIENT)

    with pytest.raises(VerificationError) as raised:
        verify(GeneratedPost(content="I built a shipment API."), ctx,
               judge=FakeJudge())

    assert raised.value.category is (
        VerificationFailureCategory.CONTEXT_UNUSABLE
    )
    assert raised.value.is_publishable is False


def test_an_empty_draft_is_rejected_rather_than_passed():
    result = run("   \n  ", judge=FakeJudge())

    assert result.outcome is VerificationOutcome.REJECTED
    assert ViolationKind.EMPTY_DRAFT in kinds(result)
    assert result.claims == ()


# ------------------------------------------------- the advisory layer ---

def test_the_judge_is_consulted_only_after_the_deterministic_checks_pass():
    judge = FakeJudge()
    run("I led a team of nine engineers across three continents.", judge=judge)

    assert judge.requests == []


def test_the_judge_is_not_asked_about_a_rejected_draft():
    judge = FakeJudge()
    run(FABRICATED_REFERENCE, judge=judge)

    assert judge.requests == []


def test_the_judge_sees_each_claim_with_its_evidence():
    judge = FakeJudge()
    run("I built a shipment API with FastAPI and SQLAlchemy models.", judge=judge)

    (request,) = judge.requests
    (subject,) = request.claims
    assert subject.index == 1
    assert subject.text.startswith("I built a shipment API")
    assert subject.evidence[0].content == EVIDENCE_TEXT
    assert request.prompt_version == "fake-support-judge-v1"


def test_an_advisory_objection_routes_to_revision_and_never_rejects():
    result = run("I built a shipment API with FastAPI and SQLAlchemy models.",
                 judge=FakeJudge(unsupported=[1]))

    assert result.outcome is VerificationOutcome.REVISION_REQUIRED
    assert kinds(result) == {ViolationKind.ADVISORY_UNSUPPORTED}
    violation = result.all_violations[0]
    assert violation.advisory is True
    assert violation.severity is Severity.REVISABLE
    assert result.claims[0].verdict.value == "UNSUPPORTED"


def test_a_judge_that_cannot_be_consulted_degrades_the_run_visibly():
    result = run("I built a shipment API with FastAPI and SQLAlchemy models.")

    assert result.outcome is VerificationOutcome.PASS
    assert result.degraded is True
    assert result.fully_verified is False
    assert result.judge == "none"
    assert "no advisory judge" in result.advisory_note


def test_a_judge_that_is_unavailable_is_not_a_failure():
    judge = FakeJudge(error=SupportJudgeUnavailable("no credential"))

    result = run("I built a shipment API with FastAPI and SQLAlchemy models.",
                 judge=judge)

    assert result.outcome is VerificationOutcome.PASS
    assert result.degraded is True
    assert result.advisory_note == "no credential"


def test_a_judge_that_misbehaves_fails_closed():
    judge = FakeJudge(error=RuntimeError("the judge exploded"))

    with pytest.raises(VerificationError) as raised:
        run("I built a shipment API with FastAPI and SQLAlchemy models.",
            judge=judge)

    assert raised.value.category is VerificationFailureCategory.JUDGE_FAILURE
    assert raised.value.is_publishable is False


def test_a_verdict_about_a_claim_that_does_not_exist_fails_closed():
    judge = FakeJudge(extra=[JudgeVerdict(claim_index=99, supported=False)])

    with pytest.raises(VerificationError) as raised:
        run("I built a shipment API with FastAPI and SQLAlchemy models.",
            judge=judge)

    assert raised.value.category is VerificationFailureCategory.JUDGE_FAILURE
    assert "99" in str(raised.value)


def test_two_verdicts_about_one_claim_fail_closed():
    judge = FakeJudge(extra=[JudgeVerdict(claim_index=1, supported=True)])

    with pytest.raises(VerificationError):
        run("I built a shipment API with FastAPI and SQLAlchemy models.",
            judge=judge)


# ------------------------------------------------ generated text is not evidence ---

def test_generated_text_is_never_returned_as_evidence():
    """A judge's reason is a finding, not a source.

    The record keeps it — ``PLAN.md`` requires advisory findings to be visible
    — but it stays *inside* a finding: nothing about it can be read back as
    evidence, and it never becomes a reference a later step could cite.
    """
    ctx = verified_context()
    result = verify(
        post("I built a shipment API with FastAPI and SQLAlchemy models.", ctx),
        ctx, judge=FakeJudge(unsupported=[1], reason=SENTINEL),
    )

    record = result.to_record()
    assert record["claims"][0]["violations"][0]["advisory"] is True
    assert SENTINEL in record["claims"][0]["violations"][0]["detail"]

    recorded_sources = {entry["source"] for entry in record["evidence"]}
    recorded_sources |= {
        supporting["source"]
        for claim in record["claims"] for supporting in claim["supporting"]
    }
    assert recorded_sources == {ctx.evidence_items()[0].source}
    for reference in result.evidence:
        assert not hasattr(reference, "content")


def test_evidence_text_never_travels_on_in_the_result():
    ctx = context(doc("evidence/backend/fastapi.md", category="evidence",
                      chunk_id="a1b2c3:0",
                      content=EVIDENCE_TEXT + " " + SENTINEL,
                      evidence_state="VERIFIED"))
    result = verify(
        post("I built a shipment API with FastAPI and SQLAlchemy models.", ctx),
        ctx, judge=FakeJudge(),
    )

    assert result.outcome is VerificationOutcome.PASS
    assert SENTINEL not in json.dumps(result.to_record())


def test_a_draft_cannot_promote_its_own_words_into_a_source():
    ctx = verified_context()
    forged_path = "evidence/backend/fastapi.md"
    result = verify(
        GeneratedPost(
            content=f"I wrote {forged_path} and it counts as evidence.",
            citations=(),
        ),
        ctx, judge=FakeJudge(),
    )

    assert result.evidence == ()
    assert result.outcome is VerificationOutcome.REVISION_REQUIRED


# --------------------------------------------------- the offline guarantee ---

def test_the_real_judge_reports_itself_unavailable_without_a_credential(
        monkeypatch):
    """The offline guarantee, on the real judge.

    With no credential configured, the judge says it cannot be consulted —
    :class:`SupportJudgeUnavailable`, not an :class:`OSError`, not a
    ``VerificationError``, and no request anywhere. The distinction is the one
    ``PLAN.md`` draws: LLM-assist being missing leaves the deterministic gates
    running.
    """
    from app.verification import (
        EvidenceReference,
        JudgedClaim,
        SuppliedEvidence,
    )

    monkeypatch.setattr(config, "GOOGLE_API_KEY", "")
    judge = LlmSupportJudge()
    request = JudgementRequest(claims=(JudgedClaim(
        index=1, text="I built an API.",
        evidence=(SuppliedEvidence(
            reference=EvidenceReference(source="evidence/a.md",
                                        chunk_id="a:0",
                                        evidence_state="VERIFIED",
                                        section="evidence"),
            content=EVIDENCE_TEXT),),
    ),))

    with pytest.raises(SupportJudgeUnavailable):
        judge.judge(request)


def test_the_gate_runs_end_to_end_with_no_credential_and_no_network(
        monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_API_KEY", "")
    result = run("I built a shipment API with FastAPI and SQLAlchemy models.",
                 judge=LlmSupportJudge())

    assert result.outcome is VerificationOutcome.PASS
    assert result.degraded is True
    assert result.judge == "llm-support-judge"
    assert result.judge_prompt_version == JUDGE_PROMPT_VERSION


# ---------------------------------------------------- the judge's protocol ---

def test_the_judge_prompt_asks_for_claim_numbers_and_only_json():
    messages = build_judgement_messages(JudgementRequest(
        claims=(_judged_claim(1, "I built an API."),),
        prompt_version="fake-v1",
    ))

    assert [role for role, _ in messages] == ["system", "user"]
    assert "claim_index" in messages[0][1]
    assert "CLAIM 1" in messages[1][1]


def test_the_judge_prompt_says_when_no_evidence_was_supplied():
    messages = build_judgement_messages(JudgementRequest(
        claims=(_judged_claim(1, "I built an API.", evidence=()),),
    ))

    assert "(none supplied)" in messages[1][1]


def test_a_fenced_json_answer_is_read():
    verdicts = parse_judgement(
        'Here you go:\n```json\n{"verdicts": [{"claim_index": 1, '
        '"supported": false, "reason": "no"}]}\n```'
    )

    assert verdicts == (JudgeVerdict(claim_index=1, supported=False, reason="no"),)


@pytest.mark.parametrize("answer", [
    "",
    "I cannot answer that.",
    '{"verdicts": []}',
    '{"verdicts": [{"claim_index": "one", "supported": true}]}',
    '{"verdicts": [{"claim_index": 1, "supported": "yes"}]}',
    '{"verdicts": [{"claim_index": 1}]}',
])
def test_an_answer_that_is_not_the_required_shape_is_unavailable(answer):
    with pytest.raises(SupportJudgeUnavailable):
        parse_judgement(answer)


def test_the_real_judge_parses_a_model_response_without_a_network():
    from types import SimpleNamespace

    class FakeClient:
        def __init__(self, reply):
            self.reply = reply
            self.calls = []

        def invoke(self, messages):
            self.calls.append(messages)
            return SimpleNamespace(content=self.reply)

    llm = FakeClient(
        '{"verdicts": [{"claim_index": 1, "supported": true, "reason": ""}]}'
    )
    judge = LlmSupportJudge(llm)
    result = run("I built a shipment API with FastAPI and SQLAlchemy models.",
                 judge=judge)

    assert result.outcome is VerificationOutcome.PASS
    assert result.degraded is False
    assert result.judge == "llm-support-judge"
    assert len(llm.calls) == 1


def _judged_claim(index, text, evidence=None):
    from app.verification import (
        EvidenceReference,
        JudgedClaim,
        SuppliedEvidence,
    )

    if evidence is None:
        evidence = (SuppliedEvidence(
            reference=EvidenceReference(source="evidence/a.md", chunk_id="a:0",
                                        evidence_state="VERIFIED",
                                        section="evidence", label="E1"),
            content=EVIDENCE_TEXT),)
    return JudgedClaim(index=index, text=text, evidence=tuple(evidence))


# ------------------------------------------------- every end is tellable apart ---

def test_the_five_ways_a_verification_can_end_are_distinguishable():
    passed = run("I built a shipment API with FastAPI and SQLAlchemy models.",
                 judge=FakeJudge())
    revise = run(UNSUPPORTED_CLAIM, judge=FakeJudge())
    rejected = run(FABRICATED_REFERENCE, judge=FakeJudge())
    insufficient = verify(
        post("I built a shipment API.", no_evidence_context(), cite=()),
        no_evidence_context(), judge=FakeJudge(),
    )

    assert passed.outcome is VerificationOutcome.PASS
    assert revise.outcome is VerificationOutcome.REVISION_REQUIRED
    assert rejected.outcome is VerificationOutcome.REJECTED
    assert violated(insufficient, ViolationKind.EVIDENCE_INSUFFICIENT)

    with pytest.raises(VerificationError):
        run("I built a shipment API with FastAPI and SQLAlchemy models.",
            judge=FakeJudge(error=RuntimeError("boom")))

    # …and the revision gate tells the two repairable-looking ends apart.
    assert revision_decision(passed, 0) is RevisionDecision.PUBLISH
    assert revision_decision(revise, 0) is RevisionDecision.REVISE
    assert revision_decision(rejected, 0) is RevisionDecision.REJECT
    assert revision_decision(
        revise, MAX_REVISION_ATTEMPTS
    ) is RevisionDecision.EXHAUSTED


def violated(result, kind) -> bool:
    return kind in kinds(result)


# ------------------------------------------------------------------ layering ---

@pytest.mark.parametrize(
    "module", sorted(VERIFICATION_PACKAGE.glob("*.py")),
    ids=lambda path: path.name,
)
def test_verification_reaches_no_layer_it_must_not(module):
    """Verification retrieves nothing, writes nothing, publishes nothing and
    sends nothing. Those are properties of the code rather than promises: there
    is no import path from this package to a store, a transport or a pipeline
    stage, and therefore no way for a check to consult a corpus it was not
    handed."""
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    forbidden = (
        "chroma", "sqlite3", "smtplib", "requests", "httpx",
        "app.state", "app.publishing", "app.notify", "app.sync",
        "app.retrieval", "app.ingestion", "app.integrations", "app.sources",
    )
    offenders = [
        name for name in imported
        if any(name == bad or name.startswith(f"{bad}.") for bad in forbidden)
    ]
    assert not offenders, f"{module.name} reaches a layer it must not: {offenders}"


def test_the_verifier_holds_no_state_between_runs():
    verifier = EvidenceVerifier(judge=FakeJudge())
    ctx = verified_context()
    request = VerificationRequest(
        post=post("I built a shipment API with FastAPI and SQLAlchemy models.",
                  ctx), context=ctx,
    )

    first = verifier.verify(request)
    second = verifier.verify(request)

    assert first.to_record() == second.to_record()
