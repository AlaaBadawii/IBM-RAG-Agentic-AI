"""Step 8: deterministic, differentiated prompt assembly.

``PLAN.md`` Step 8 forbids one thing above all others — concatenating the
context into an undifferentiated prompt — and requires the prohibitions on
fabrication to be explicit. Both are properties of *assembly*, so they are
tested here, without a model: everything below asserts on the value
:func:`app.generation.prompt.build_prompt` returns.

The context is built through the real :func:`app.context.builder.build_context`
from hand-built retrieval results, so these tests exercise the seam Step 8
actually sits on rather than a stand-in for it. No model, no key, no network.
"""
import hashlib
import json

import pytest

from app.context.builder import build_context
from app.generation import (
    PROHIBITED_CLAIMS,
    PublishingConstraints,
    GenerationRequest,
    build_prompt,
    selected_evidence,
)
from app.generation.prompt import INSTRUCTIONS, NO_STATE_LABEL
from app.paths import DATA_DIR
from app.retrieval.models import RetrievalResult, RetrievedDocument

EVIDENCE_TEXT = (
    "Built a FastAPI shipment API with SQLAlchemy models and Alembic "
    "migrations, deployed behind a documented retry policy."
)
SECOND_EVIDENCE_TEXT = "Completed the IBM RAG applications course."
STYLE_TEXT = "Write directly, in short sentences, without marketing language."
POSITIONING_TEXT = "Positioned as a backend engineer who ships working systems."
VISION_TEXT = "Become a recognised engineer in applied AI systems."


# ------------------------------------------------------------------ helpers ---

def doc(source: str, *, category: str, chunk_id: str, content: str,
        evidence_state: str | None = None, document_type: str | None = None,
        rank: int = 1) -> RetrievedDocument:
    """A retrieved document shaped the way the ingestion pipeline writes them."""
    metadata = {
        "source": source,
        "category": category,
        "document_type": document_type or "unknown",
        "content_hash": chunk_id.split(":")[0],
    }
    if evidence_state is not None:
        metadata["evidence_state"] = evidence_state
    return RetrievedDocument(
        content=content, score=0.5, source=source, metadata=metadata,
        strategy="vector", chunk_id=chunk_id, rank=rank,
    )


def evidence_doc(**kwargs) -> RetrievedDocument:
    defaults = dict(
        source="evidence/backend/fastapi.md", category="evidence",
        chunk_id="a1b2c3:0", content=EVIDENCE_TEXT, evidence_state="VERIFIED",
    )
    return doc(**{**defaults, **kwargs})


def guidance_doc(*, category: str, document_type: str, content: str,
                 source: str | None = None, rank: int = 1) -> RetrievedDocument:
    # The chunk id is derived from the category: ids are content-addressed in
    # the real pipeline, and the context layer collapses items that share one,
    # so three guidance documents need three addresses.
    digest = hashlib.md5(category.encode()).hexdigest()
    return doc(
        source or f"data/{category}/{category}.md", category=category,
        document_type=document_type, content=content,
        chunk_id=f"{digest}:0", rank=rank,
    )


def context(*documents: RetrievedDocument):
    """Assemble a context the way the pipeline really does."""
    return build_context(RetrievalResult(
        query="a topic", strategy="vector", documents=list(documents),
        diagnostics={},
    ))


def full_context_docs() -> tuple[RetrievedDocument, ...]:
    """The evidence plus all three kinds of guidance."""
    return (
        evidence_doc(),
        guidance_doc(category="writing_style", document_type="writing_style",
                     content=STYLE_TEXT, rank=2),
        guidance_doc(category="public_positioning", document_type="positioning",
                     content=POSITIONING_TEXT, rank=3),
        guidance_doc(category="vision_goals", document_type="vision",
                     content=VISION_TEXT, rank=4),
    )


def full_context():
    return context(*full_context_docs())


def request(**kwargs) -> GenerationRequest:
    return GenerationRequest(context=kwargs.pop("context", full_context()),
                             **kwargs)


# ------------------------------------------------- who sees what, and apart ---

def test_evidence_reaches_the_prompt():
    """Acceptance: generation consumes assembled context, not raw chunks."""
    prompt = build_prompt(request())

    assert EVIDENCE_TEXT in prompt.evidence_block
    assert prompt.has_evidence


def test_guidance_reaches_the_prompt():
    prompt = build_prompt(request())

    assert STYLE_TEXT in prompt.guidance_block
    assert POSITIONING_TEXT in prompt.guidance_block
    assert VISION_TEXT in prompt.guidance_block


def test_style_and_positioning_stay_out_of_the_evidence_block():
    """The separation Step 4 built is spent here, where it matters.

    A model told *"write without marketing language"* in the same block as
    *"I built X"* has no way to tell that one is a manner of speaking and the
    other is a fact it may claim.
    """
    prompt = build_prompt(request())

    for guidance in (STYLE_TEXT, POSITIONING_TEXT, VISION_TEXT):
        assert guidance not in prompt.evidence_block
    assert EVIDENCE_TEXT not in prompt.guidance_block


def test_the_evidence_and_guidance_blocks_are_separate_fields():
    """Not one concatenated blob: the parts of the prompt are addressable."""
    prompt = build_prompt(request())

    assert prompt.evidence_block != prompt.guidance_block
    assert prompt.evidence_block and prompt.guidance_block
    assert prompt.evidence_block not in prompt.guidance_block
    assert prompt.guidance_block not in prompt.evidence_block


def test_each_block_is_rendered_under_its_own_header():
    prompt = build_prompt(request())
    body = prompt.body()

    titles = [title for title, _ in prompt.blocks]
    assert titles == ["TASK", "EVIDENCE", "COMMUNICATION GUIDANCE"]
    for title in titles:
        assert f"## {title}" in body

    # The material under each header is that header's material and no other.
    _, after_evidence = body.split("## EVIDENCE\n", 1)
    evidence_section, _, guidance_section = after_evidence.partition(
        "## COMMUNICATION GUIDANCE"
    )
    assert EVIDENCE_TEXT in evidence_section
    assert STYLE_TEXT not in evidence_section
    assert STYLE_TEXT in guidance_section
    assert EVIDENCE_TEXT not in guidance_section


def test_the_rules_travel_in_the_system_message_and_material_in_the_user_one():
    prompt = build_prompt(request())
    system, user = prompt.messages()

    assert system["role"] == "system"
    assert user["role"] == "user"
    assert system["content"] == INSTRUCTIONS
    assert STYLE_TEXT not in system["content"]
    assert EVIDENCE_TEXT in user["content"]
    assert STYLE_TEXT in user["content"]


# ---------------------------------------------- the prohibitions are explicit ---

@pytest.mark.parametrize("claim", PROHIBITED_CLAIMS)
def test_every_prohibited_claim_is_named_in_the_instructions(claim):
    """Acceptance: unsupported personal claims are explicitly prohibited.

    Asserted per term rather than as one sentence, so dropping a category from
    the rule fails a test instead of quietly narrowing it.
    """
    assert claim in INSTRUCTIONS


def test_the_prohibition_is_generated_from_the_list_it_is_checked_against():
    """The sentence a model reads and the list a test checks share a source."""
    phrase = ", ".join(PROHIBITED_CLAIMS[:-1]) + f", or {PROHIBITED_CLAIMS[-1]}"
    assert phrase in INSTRUCTIONS


def test_the_instructions_forbid_guidance_being_claimed_as_evidence():
    assert "not evidence" in INSTRUCTIONS


def test_the_instructions_forbid_coursework_and_practice_read_as_experience():
    instructions = INSTRUCTIONS.lower()
    assert "course" in instructions
    assert "professional experience" in instructions
    assert "production system" in instructions


def test_the_instructions_require_citations_limited_to_supplied_labels():
    assert "cite" in INSTRUCTIONS.lower()
    assert "not listed" in INSTRUCTIONS


def test_the_instructions_allow_declining_and_state_the_output_shape():
    assert '"declined"' in INSTRUCTIONS
    assert '"post"' in INSTRUCTIONS
    assert '"evidence_used"' in INSTRUCTIONS

    # A JSON object a parser can rely on, not prose to interpret.
    shape = INSTRUCTIONS.split("no code fence:\n", 1)[1].splitlines()[0]
    assert json.loads(shape)["post"] == "<the post text>"


# ------------------------------------------------------------- determinism ---

def test_the_same_request_assembles_the_same_prompt_twice():
    assert build_prompt(request()) == build_prompt(request())


def test_assembly_does_not_depend_on_the_order_documents_arrived_in():
    """The prompt is a function of the evidence, not of the retrieval run.

    Same documents, reversed input order: the context layer re-sorts them, so
    the labels, the blocks and the rendered text must be identical. Otherwise
    the prompt would depend on which strategy ran and in what order.
    """
    forward = build_prompt(request(context=full_context()))
    backward = build_prompt(
        request(context=context(*reversed(full_context_docs())))
    )

    assert forward.render() == backward.render()
    assert forward.citations == backward.citations


def test_the_prompt_carries_the_version_that_produced_it():
    from app.generation import PROMPT_VERSION

    assert build_prompt(request()).version == PROMPT_VERSION


# --------------------------------------------------------- empty and partial ---

def test_a_context_with_no_evidence_assembles_a_prompt_with_no_evidence_block():
    """The empty case is representable, so declining can be tested at all."""
    only_guidance = context(
        guidance_doc(category="writing_style", document_type="writing_style",
                     content=STYLE_TEXT),
    )
    prompt = build_prompt(request(context=only_guidance))

    assert prompt.has_evidence is False
    assert prompt.evidence_block == ""
    assert prompt.citations == ()
    assert "## EVIDENCE" not in prompt.body()
    # Guidance is still there: what is absent is evidence, not the prompt.
    assert STYLE_TEXT in prompt.guidance_block


def test_an_empty_constraints_block_is_omitted_rather_than_left_blank():
    bare = build_prompt(request(constraints=PublishingConstraints()))
    constrained = build_prompt(request(constraints=PublishingConstraints(
        recent_topics=("retrieval",), recent_angles=("lessons learned",),
        recent_projects=("Quizey",), notes=("keep it under 900 characters",),
    )))

    assert bare.constraints_block == ""
    assert "CONSTRAINTS" not in bare.body()

    block = constrained.constraints_block
    assert "retrieval" in block
    assert "lessons learned" in block
    assert "Quizey" in block
    assert "keep it under 900 characters" in block
    assert "## CONSTRAINTS" in constrained.body()


def test_task_labels_are_instructions_and_never_evidence():
    prompt = build_prompt(request(topic="retrieval quality",
                                  angle="what I measured",
                                  project="PersonalBrandingAgent"))

    assert "retrieval quality" in prompt.task_block
    assert "what I measured" in prompt.task_block
    assert "PersonalBrandingAgent" in prompt.task_block
    assert "retrieval quality" not in prompt.evidence_block
    assert "PersonalBrandingAgent" not in prompt.evidence_block


def test_a_blank_label_is_refused_rather_than_recorded():
    with pytest.raises(ValueError, match="topic"):
        request(topic="   ")


# ------------------------------------------------------------- provenance ---

def test_every_evidence_item_carries_its_source_and_chunk_id():
    """A citation has to resolve to the chunk it was read from, not to a path."""
    prompt = build_prompt(request())

    for citation, item in zip(prompt.citations, full_context().evidence_items()):
        assert citation.source == item.source
        assert citation.chunk_id == item.chunk_id
        assert citation.source in prompt.evidence_block
        assert citation.chunk_id in prompt.evidence_block


def test_labels_are_assigned_in_context_order_starting_at_e1():
    two = context(
        evidence_doc(),
        doc(source="certificates/ibm_rag.md", category="certificates",
            chunk_id="ffff00:1", content=SECOND_EVIDENCE_TEXT, rank=2),
    )
    prompt = build_prompt(request(context=two))

    assert [c.label for c in prompt.citations] == ["E1", "E2"]


def test_a_declared_evidence_state_is_shown_and_an_absent_one_is_not_invented():
    mixed = context(
        evidence_doc(),
        doc(source="stories_lessons/notes.md", category="stories_lessons",
            chunk_id="987654:0", content=SECOND_EVIDENCE_TEXT, rank=2),
    )
    prompt = build_prompt(request(context=mixed))

    assert "VERIFIED" in prompt.evidence_block
    assert NO_STATE_LABEL in prompt.evidence_block
    assert "None" not in prompt.evidence_block


# -------------------------------------------------------------- selection ---

def test_selection_defaults_to_every_evidence_item_in_the_context():
    ctx = full_context()
    assert selected_evidence(GenerationRequest(context=ctx)) == (
        ctx.evidence_items()
    )


def test_a_selection_is_limited_to_what_the_context_contains():
    """Evidence the assembly layer never placed is not this layer's to write
    from — and saying so is the difference between a bad choice and an
    invention."""
    ctx = full_context()
    foreign = evidence_doc(source="evidence/backend/other.md", chunk_id="999:0")

    with pytest.raises(ValueError, match="not in the supplied context"):
        build_prompt(GenerationRequest(context=ctx, evidence=(foreign,)))
    with pytest.raises(ValueError, match="not in the supplied context"):
        selected_evidence(GenerationRequest(context=ctx, evidence=(foreign,)))


def test_a_selection_comes_back_in_context_order_whatever_order_it_was_given():
    ctx = context(
        evidence_doc(),
        doc(source="certificates/ibm_rag.md", category="certificates",
            chunk_id="ffff00:1", content=SECOND_EVIDENCE_TEXT, rank=2),
    )
    everything = ctx.evidence_items()

    forward = selected_evidence(GenerationRequest(context=ctx,
                                                  evidence=everything))
    reversed_ = selected_evidence(
        GenerationRequest(context=ctx, evidence=tuple(reversed(everything)))
    )

    assert forward == everything
    assert reversed_ == everything


def test_selecting_the_same_item_twice_is_one_piece_of_evidence():
    ctx = full_context()
    item = ctx.evidence_items()[0]

    prompt = build_prompt(GenerationRequest(context=ctx, evidence=(item, item)))

    assert len(prompt.citations) == 1


# ------------------------------------------ guidance comes from the corpus ---

def test_style_guidance_comes_from_the_knowledge_file_not_a_hardcoded_prompt():
    """Acceptance: style and positioning come from knowledge files.

    The file's own text is put through the layer and read back out of the
    guidance block; and the constant instructions — the one place wording could
    be hardcoded — do not contain it.
    """
    style_file = DATA_DIR / "writing_style" / "alaa_writing_style.md"
    style_text = style_file.read_text(encoding="utf-8").strip()
    assert style_text, "the writing-style knowledge file is empty"

    ctx = context(
        evidence_doc(),
        guidance_doc(category="writing_style", document_type="writing_style",
                     content=style_text),
    )
    prompt = build_prompt(request(context=ctx))

    assert style_text in prompt.guidance_block
    assert style_text not in INSTRUCTIONS
    assert style_text not in prompt.evidence_block
