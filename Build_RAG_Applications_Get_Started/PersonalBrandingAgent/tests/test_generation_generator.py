"""Step 8: the generation service's contract.

What a caller can rely on: the model is given the assembled context and not a
pile of chunks; the answer comes back as a structure; a decline is a result and
a failure is not; and nothing is ever written down.

Every test here drives ``PostGenerator`` with a plain fake that records what it
was asked. No API key, no network, no model — and one test proves that by
calling the generator with a configuration that has no key at all.
"""
import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import config
from app.context.builder import build_context
from app.generation import (
    PROMPT_VERSION,
    DeclineReason,
    GenerationError,
    GenerationFailureCategory,
    GenerationOutcome,
    GenerationRequest,
    PostGenerator,
    PublishingConstraints,
)
from app.logging_config import known_secrets
from app.retrieval.models import RetrievalResult, RetrievedDocument

GENERATION_PACKAGE = Path(__file__).resolve().parents[1] / "app" / "generation"

EVIDENCE_TEXT = "Built a FastAPI shipment API with SQLAlchemy and Alembic."
OTHER_EVIDENCE_TEXT = "Completed the IBM RAG applications course."
STYLE_TEXT = "Write directly, without marketing language."
POSITIONING_TEXT = "Positioned as a backend engineer who ships."
POST_TEXT = (
    "I spent this week on a shipment API: FastAPI, SQLAlchemy models, Alembic "
    "migrations. The migrations were the part that taught me the most."
)


# ------------------------------------------------------------------ helpers ---

class FakeLLM:
    """A model that answers with whatever it was told to, and remembers being
    asked. The whole point is that it is not a framework type: anything with
    ``invoke`` is a model as far as this layer is concerned."""

    def __init__(self, reply: str | None = None, *, error: Exception | None = None):
        self.reply = reply
        self.error = error
        self.calls: list[tuple[dict, ...]] = []

    def invoke(self, messages):
        self.calls.append(messages)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(content=self.reply)

    @property
    def prompts(self) -> str:
        """Everything this fake was asked, as one string."""
        return "\n".join(
            message["content"] for call in self.calls for message in call
        )


def answer(*, post: str = POST_TEXT, evidence_used=(), declined: bool = False,
           reason: str = "") -> str:
    return json.dumps({
        "post": post,
        "evidence_used": list(evidence_used),
        "declined": declined,
        "reason": reason,
    })


def doc(source: str, *, category: str, chunk_id: str, content: str,
        evidence_state: str | None = None, document_type: str | None = None,
        rank: int = 1) -> RetrievedDocument:
    metadata = {
        "source": source, "category": category,
        "document_type": document_type or "unknown",
        "content_hash": chunk_id.split(":")[0],
    }
    if evidence_state is not None:
        metadata["evidence_state"] = evidence_state
    return RetrievedDocument(
        content=content, score=0.5, source=source, metadata=metadata,
        strategy="vector", chunk_id=chunk_id, rank=rank,
    )


def context(*documents: RetrievedDocument):
    return build_context(RetrievalResult(
        query="a topic", strategy="vector", documents=list(documents),
        diagnostics={},
    ))


def grounded_context():
    """One verified piece of evidence plus one piece of style guidance."""
    return context(
        doc("evidence/backend/fastapi.md", category="evidence",
            chunk_id="a1b2c3:0", content=EVIDENCE_TEXT,
            evidence_state="VERIFIED"),
        doc("data/writing_style/alaa_writing_style.md", category="writing_style",
            document_type="writing_style", chunk_id="d4e5f6:0",
            content=STYLE_TEXT, rank=2),
    )


def two_evidence_context():
    return context(
        doc("evidence/backend/fastapi.md", category="evidence",
            chunk_id="a1b2c3:0", content=EVIDENCE_TEXT,
            evidence_state="VERIFIED"),
        doc("certificates/ibm_rag.md", category="certificates",
            chunk_id="ffff00:1", content=OTHER_EVIDENCE_TEXT, rank=2),
    )


def guidance_only_context():
    return context(
        doc("data/public_positioning/portfolio.md", category="public_positioning",
            document_type="positioning", chunk_id="d4e5f6:0",
            content=POSITIONING_TEXT),
    )


def request(**kwargs) -> GenerationRequest:
    return GenerationRequest(context=kwargs.pop("context", grounded_context()),
                             **kwargs)


def generate(reply: str, *, request_kwargs=None):
    llm = FakeLLM(reply)
    generator = PostGenerator(llm)
    return generator.generate(request(**(request_kwargs or {}))), llm


# ------------------------------------------------ what the model is given ---

def test_the_model_is_called_with_the_assembled_prompt():
    result, llm = generate(answer(evidence_used=["E1"]))

    assert result.generated
    assert len(llm.calls) == 1
    system, user = llm.calls[0]
    assert system["role"] == "system"
    assert user["role"] == "user"
    for title in ("## TASK", "## EVIDENCE", "## COMMUNICATION GUIDANCE"):
        assert title in user["content"]


def test_the_contexts_evidence_is_what_the_model_receives():
    """Acceptance: generation consumes assembled context, not raw chunks."""
    _, llm = generate(answer(evidence_used=["E1"]))

    assert EVIDENCE_TEXT in llm.prompts
    assert "evidence/backend/fastapi.md" in llm.prompts
    assert "a1b2c3:0" in llm.prompts


def test_style_guidance_reaches_the_model_apart_from_the_evidence():
    _, llm = generate(answer())

    _, user = llm.calls[0]
    body = user["content"]
    evidence_section, _, guidance_section = body.partition(
        "## COMMUNICATION GUIDANCE"
    )
    assert STYLE_TEXT in guidance_section
    assert STYLE_TEXT not in evidence_section
    assert EVIDENCE_TEXT in evidence_section
    assert EVIDENCE_TEXT not in guidance_section


def test_a_selection_is_all_the_model_sees():
    """Evidence the caller did not select does not reach the prompt."""
    ctx = two_evidence_context()
    selected = ctx.evidence_items()[1]

    _, llm = generate(answer(evidence_used=["E1"]),
                      request_kwargs={"context": ctx, "evidence": (selected,)})

    assert OTHER_EVIDENCE_TEXT in llm.prompts
    assert EVIDENCE_TEXT not in llm.prompts
    assert "[E1]" in llm.prompts
    assert "[E2]" not in llm.prompts


def test_two_generators_assemble_the_same_prompt_for_the_same_request():
    """Determinism survives the service, not just the assembly function."""
    first, second = FakeLLM(answer()), FakeLLM(answer())
    req = request(topic="backend work",
                  constraints=PublishingConstraints(recent_topics=("sync",)))

    PostGenerator(first).generate(req)
    PostGenerator(second).generate(req)

    assert first.calls == second.calls


def test_generation_parameters_and_model_id_are_the_configured_ones():
    """The repository's existing configuration boundary, not a new one."""
    _, llm = generate(answer())
    result, _ = generate(answer())

    assert result.metadata.model_id == config.GEMINI_MODEL_ID
    assert result.metadata.parameters == config.GENERATION_PARAMS
    assert result.metadata.prompt_version == PROMPT_VERSION


# --------------------------------------------------------- the way out ---

def test_a_draft_comes_back_as_a_structured_result():
    result, _ = generate(answer(evidence_used=["E1"]))

    assert result.outcome is GenerationOutcome.GENERATED
    assert result.post is not None
    assert result.post.content == POST_TEXT
    assert result.text == POST_TEXT
    assert result.decline_reason is None


def test_the_draft_carries_the_evidence_it_says_it_used():
    result, _ = generate(answer(evidence_used=["E1"]))

    assert result.post.cited_labels == ("E1",)
    citation = result.citations[0]
    assert citation.source == "evidence/backend/fastapi.md"
    assert citation.chunk_id == "a1b2c3:0"
    assert citation.evidence_state == "VERIFIED"


def test_the_result_carries_model_prompt_version_and_parameters():
    """``PLAN.md`` Step 8: the audit record has to be able to name them."""
    result, _ = generate(answer())

    assert result.metadata.model_id == config.GEMINI_MODEL_ID
    assert result.metadata.prompt_version == PROMPT_VERSION
    assert result.metadata.parameters["max_tokens"] == (
        config.GENERATION_PARAMS["max_tokens"]
    )
    assert result.metadata.evidence_item_count == 1
    assert result.metadata.guidance_item_count == 1
    assert result.metadata.evidence_labels == ("E1",)
    assert result.metadata.latency_ms is not None


def test_a_draft_cites_only_evidence_that_was_supplied():
    """The milestone: labels resolve against the prompt, or they are nothing.

    ``E9`` is not in the prompt. It cannot become a citation, because the only
    way to a citation is a lookup in the list that was sent.
    """
    result, _ = generate(answer(evidence_used=["E1", "E9"]))

    assert result.post.cited_labels == ("E1",)
    assert result.post.citations[0].source == "evidence/backend/fastapi.md"


def test_an_invented_label_is_reported_rather_than_silently_dropped():
    result, _ = generate(answer(evidence_used=["E9", "E1"]))

    assert result.post.unresolved_labels == ("E9",)


def test_the_same_label_twice_is_one_citation():
    result, _ = generate(answer(evidence_used=["E1", "E1"]))

    assert result.post.cited_labels == ("E1",)


def test_a_draft_that_names_no_evidence_is_still_a_draft():
    """Nothing is fabricated, and nothing is invented either: Step 9 decides
    what an uncited draft means. Generation does not pretend it cited."""
    result, _ = generate(answer(evidence_used=[]))

    assert result.generated
    assert result.post.citations == ()
    assert result.post.is_cited is False


# ------------------------------------------------------- declining ---

def test_insufficient_evidence_declines_without_calling_the_model():
    """Acceptance: not silently treated as sufficient — and not paid for.

    Asking a model to write from no evidence is asking it to invent, so the
    decision is made before the request exists.
    """
    llm = FakeLLM(answer())

    result = PostGenerator(llm).generate(request(context=guidance_only_context()))

    assert result.declined
    assert result.decline_reason is DeclineReason.INSUFFICIENT_EVIDENCE
    assert result.post is None
    assert llm.calls == []


def test_a_declined_result_carries_metadata_but_no_measurement():
    llm = FakeLLM(answer())

    result = PostGenerator(llm).generate(request(context=guidance_only_context()))

    assert result.metadata.prompt_version == PROMPT_VERSION
    assert result.metadata.evidence_item_count == 0
    # No call was made, so there is no duration to report — and inventing one
    # would be a fabricated measurement in an audit record.
    assert result.metadata.latency_ms is None


def test_an_empty_selection_declines_rather_than_writing_from_style_alone():
    llm = FakeLLM(answer())

    result = PostGenerator(llm).generate(
        request(evidence=())  # an explicit "write from nothing"
    )

    assert result.declined
    assert result.decline_reason is DeclineReason.INSUFFICIENT_EVIDENCE
    assert llm.calls == []


def test_the_model_may_decline_and_its_reason_is_carried():
    result, _ = generate(answer(
        declined=True, post="",
        reason="the evidence covers a course exercise, not something worth a post",
    ))

    assert result.declined
    assert result.decline_reason is DeclineReason.MODEL_DECLINED
    assert "not something worth a post" in result.decline_message
    assert result.post is None


def test_a_decline_is_not_a_failure():
    """``PLAN.md`` Step 8: insufficient evidence produces a declining result.

    A decline ends the run as ``DO_NOT_PUBLISH`` and Step 7 waives it, so
    raising here would turn a correct "nothing to say" into an alert.
    """
    result, _ = generate(answer(declined=True, post="", reason="nothing here"))

    assert result.declined
    assert not result.generated


# ------------------------------------------------------------ failures ---

def test_an_unreachable_model_raises_rather_than_producing_a_post():
    llm = FakeLLM(error=RuntimeError("connection reset by peer"))

    with pytest.raises(GenerationError) as raised:
        PostGenerator(llm).generate(request())

    assert raised.value.category is GenerationFailureCategory.LLM_UNAVAILABLE
    assert raised.value.requires_human_intervention is False
    assert isinstance(raised.value.__cause__, RuntimeError)


def test_a_missing_credential_is_a_configuration_failure(monkeypatch):
    """Reported as what it is: a person has to fix it, a retry cannot."""
    monkeypatch.setattr(config, "GOOGLE_API_KEY", "")

    with pytest.raises(GenerationError) as raised:
        PostGenerator().generate(request())

    assert raised.value.category is GenerationFailureCategory.CONFIGURATION
    assert raised.value.requires_human_intervention is True
    assert "GOOGLE_API_KEY" in str(raised.value)


def test_an_injected_model_needs_no_credential_at_all(monkeypatch):
    """Proves the suite is offline by construction, not by luck."""
    monkeypatch.setattr(config, "GOOGLE_API_KEY", "")

    result, _ = generate(answer(evidence_used=["E1"]))

    assert result.generated


@pytest.mark.parametrize("reply", [
    "",
    "   ",
    "I am afraid I cannot help with that.",
    '{"declined": false, "post": "   "}',
    '{"declined": false, "post": 42}',
    "[1, 2, 3]",
])
def test_an_answer_that_is_not_the_required_shape_is_a_failure(reply):
    """No post to check and no post to publish — so no post is returned."""
    with pytest.raises(GenerationError) as raised:
        PostGenerator(FakeLLM(reply)).generate(request())

    assert raised.value.category is GenerationFailureCategory.INVALID_RESPONSE


def test_a_code_fenced_answer_is_still_usable():
    fenced = f"```json\n{answer(evidence_used=['E1'])}\n```"

    result, _ = generate(fenced)

    assert result.generated
    assert result.post.content == POST_TEXT


def test_an_answer_wrapped_in_prose_is_still_usable():
    chatty = f"Here is the post:\n{answer(evidence_used=['E1'])}\nHope that helps."

    result, _ = generate(chatty)

    assert result.generated
    assert result.citations[0].source == "evidence/backend/fastapi.md"


def test_a_failure_never_becomes_a_weaker_post():
    """The one fallback this layer must not have: ``PLAN.md`` Step 8 is explicit
    that there is no valid degraded post, because unverified text about a real
    person would reach the publish path indistinguishable from a draft."""
    for broken in (FakeLLM(error=RuntimeError("boom")), FakeLLM("not json")):
        with pytest.raises(GenerationError):
            PostGenerator(broken).generate(request())


def test_evidence_the_context_does_not_hold_is_refused():
    """A caller cannot smuggle in material the assembly layer never placed."""
    foreign = doc("evidence/backend/elsewhere.md", category="evidence",
                  chunk_id="999999:0", content="Something never retrieved.")

    with pytest.raises(ValueError, match="not in the supplied context"):
        PostGenerator(FakeLLM(answer())).generate(
            request(evidence=(foreign,))
        )


def test_a_failed_call_is_redacted_before_it_is_kept(monkeypatch):
    """Failure text is external input, and providers quote the request back.

    The redaction list is the repository's, not a second one invented here, so
    a value this process knows is a secret is scrubbed wherever it appears —
    including in an error a caller is about to log.
    """
    secret = "sk-or-v1-not-a-real-key"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)
    assert secret in known_secrets()
    llm = FakeLLM(error=RuntimeError(f"401 unauthorized; key was {secret}"))

    with pytest.raises(GenerationError) as raised:
        PostGenerator(llm).generate(request())

    assert secret not in str(raised.value)
    assert "[REDACTED]" in str(raised.value)


def test_the_credential_never_reaches_the_result(monkeypatch):
    """Metadata is audit data: model id, prompt version, parameters. No key."""
    monkeypatch.setattr(config, "GOOGLE_API_KEY", "AIza-not-a-real-key")

    result, _ = generate(answer(evidence_used=["E1"]))

    assert "AIza-not-a-real-key" not in repr(result)


# ------------------------------------------------- what this layer cannot do ---

@pytest.mark.parametrize("module", sorted(GENERATION_PACKAGE.glob("*.py")),
                         ids=lambda path: path.name)
def test_generation_cannot_reach_state_publishing_notifications_or_knowledge(module):
    """Asserted structurally, not behaviourally.

    Generation writes no state, publishes nothing, sends nothing, and never
    queries the vector store. Those are properties of the code rather than
    promises a test would have to keep re-checking: there is no import path
    from this package to any of them.
    """
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    forbidden = (
        "chroma", "sqlite3", "smtplib", "requests",
        "app.state", "app.publishing", "app.notify",
        "app.retrieval", "app.ingestion",
    )
    offenders = [
        name for name in imported
        if any(name == bad or name.startswith(f"{bad}.") for bad in forbidden)
    ]
    assert not offenders, f"{module.name} reaches a layer it must not: {offenders}"
