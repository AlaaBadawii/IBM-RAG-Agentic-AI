"""M4: development-specific evidence targeting.

Isolated state and isolated Chroma throughout. These tests pin the
evidence boundary — which documents an opportunity may draw on — not
model behavior. Draft correctness beyond plumbing is proven by the live
dry run, not by fakes.
"""
import pytest

from app.opportunities.opportunities import (
    build_opportunities,
    retrieve_for_opportunity,
    select_opportunity,
)
from app.state import StateStore

ABU_IDENTITY = "Abu Prompt, known as @AbuPrompt"
ABU_ARABIC = "أبو برومبت"


@pytest.fixture
def store(tmp_path):
    with StateStore(tmp_path / "m4.db") as state:
        yield state


def _work(work_id, sources=(), priority="normal", developments=()):
    return {
        "id": work_id, "display_name": work_id,
        "sources": list(sources), "branding_priority": priority,
        "enabled": True, "developments": list(developments),
    }


def _dev(key, covered=False, categories=(), evidence_sources=()):
    entry = {"key": key, "display_name": key, "covered": covered}
    if categories:
        entry["corpus_categories"] = list(categories)
    if evidence_sources:
        entry["evidence_sources"] = list(evidence_sources)
    return entry


def _seed(store, entries):
    for entry in entries:
        store.ensure_tracked_work(
            entry["id"], entry.get("display_name", entry["id"]),
            sources=tuple(entry.get("sources", ())))
        for dev in entry.get("developments", ()):
            store.ensure_development(
                entry["id"], dev["key"],
                dev.get("display_name", dev["key"]),
                covered=bool(dev.get("covered", False)))


def _chroma(tmp_path, fake_embeddings, docs):
    from langchain_core.documents import Document
    from langchain_chroma import Chroma

    chroma = Chroma(
        collection_name="targeting_tests",
        embedding_function=fake_embeddings,
        persist_directory=str(tmp_path / "chroma-targeting"),
    )
    chroma.add_documents(
        [Document(page_content=text,
                  metadata={"source": source, "category": category})
         for text, source, category in docs],
        ids=[f"d{n}" for n in range(len(docs))],
    )
    return chroma


ABU_DOCS = [
    (ABU_IDENTITY + " plans ahead.", "in_progress_projects/personal_branding_agent.md",
     "in_progress_projects"),
    (ABU_ARABIC + " intro.", "public_positioning/abu_prompt.md",
     "public_positioning"),
    ("Evaluator Core judges submissions.", "in_progress_projects/evaluator_core.md",
     "in_progress_projects"),
    ("Quiz versioning copy-on-write.", "in_progress_projects/quizey_v2.md",
     "in_progress_projects"),
    ("Some certificate course.", "certificates/some.md", "certificates"),
]

ABU_ENTRIES = [_work(
    "personal-branding-agent", priority="high", developments=[
        _dev("historical-baseline", covered=True),
        _dev("abu-prompt-introduction",
             categories=["in_progress_projects"],
             evidence_sources=["in_progress_projects/personal_branding_agent.md",
                               "public_positioning/abu_prompt.md"])])]


def _abu_selected(store):
    _seed(store, ABU_ENTRIES)
    selected = select_opportunity(store, ABU_ENTRIES)
    assert (selected.work_id, selected.key) == (
        "personal-branding-agent", "abu-prompt-introduction")
    return selected


# ------------------------------------------------------- targeting ---

def test_abu_retrieves_abu_evidence_not_the_category(store, tmp_path,
                                                     fake_embeddings):
    chroma = _chroma(tmp_path, fake_embeddings, ABU_DOCS)
    selected = _abu_selected(store)

    result = retrieve_for_opportunity(selected, vector_store=chroma)

    assert result.documents
    assert {d.metadata["source"] for d in result.documents} == {
        "in_progress_projects/personal_branding_agent.md",
        "public_positioning/abu_prompt.md"}


def test_same_category_decoy_cannot_replace(store, tmp_path,
                                            fake_embeddings):
    chroma = _chroma(tmp_path, fake_embeddings, ABU_DOCS)
    selected = _abu_selected(store)

    for strategy in ("vector", "bm25", "hybrid"):
        result = retrieve_for_opportunity(
            selected, vector_store=chroma, strategy=strategy)
        sources = {d.metadata["source"] for d in result.documents}
        assert "in_progress_projects/evaluator_core.md" not in sources, strategy
        assert "in_progress_projects/quizey_v2.md" not in sources, strategy


def test_quizey_development_targets_quizey_evidence(store, tmp_path,
                                                    fake_embeddings):
    docs = ABU_DOCS + [
        ("Quizey phase two versioning.", "in_progress_projects/quizey_v2.md",
         "in_progress_projects")]
    chroma = _chroma(tmp_path, fake_embeddings, docs)
    entries = [_work("quizey", sources=["quizey-v2"], developments=[
        _dev("phase-2", evidence_sources=[
            "in_progress_projects/quizey_v2.md"])])]
    _seed(store, entries)

    selected = select_opportunity(store, entries)
    result = retrieve_for_opportunity(selected, vector_store=chroma)

    assert result.documents
    assert {d.metadata["source"] for d in result.documents} == {
        "in_progress_projects/quizey_v2.md"}


def test_developments_under_one_project_target_independently(
        store, tmp_path, fake_embeddings):
    chroma = _chroma(tmp_path, fake_embeddings, ABU_DOCS)
    entries = [_work("pba", developments=[
        _dev("intro", evidence_sources=[
            "in_progress_projects/personal_branding_agent.md"]),
        _dev("other", evidence_sources=["certificates/some.md"])])]
    _seed(store, entries)

    opps = {o.key: o for o in
            __import__("app.opportunities.opportunities",
                       fromlist=["build_opportunities"]).build_opportunities(
                           store, entries)}

    first = retrieve_for_opportunity(opps["intro"], vector_store=chroma)
    second = retrieve_for_opportunity(opps["other"], vector_store=chroma)
    assert {d.metadata["source"] for d in first.documents} == {
        "in_progress_projects/personal_branding_agent.md"}
    assert {d.metadata["source"] for d in second.documents} == {
        "certificates/some.md"}


def test_future_development_assignable_without_branches(store, tmp_path,
                                                       fake_embeddings):
    chroma = _chroma(tmp_path, fake_embeddings, ABU_DOCS)
    entries = [_work(" w2 ".strip(), developments=[
        _dev("v2", evidence_sources=["certificates/some.md"])])]
    _seed(store, entries)

    selected = select_opportunity(store, entries)
    result = retrieve_for_opportunity(selected, vector_store=chroma)

    assert selected.key == "v2"
    assert {d.metadata["source"] for d in result.documents} == {
        "certificates/some.md"}


# ------------------------------------------------------- grounding ---

def test_abu_evidence_carries_authoritative_content(store, tmp_path,
                                                   fake_embeddings):
    chroma = _chroma(tmp_path, fake_embeddings, ABU_DOCS)
    selected = _abu_selected(store)

    result = retrieve_for_opportunity(selected, vector_store=chroma)
    text = "\n".join(d.content for d in result.documents)

    assert ABU_IDENTITY in text
    assert ABU_ARABIC in text


def test_published_text_never_becomes_evidence(store, tmp_path,
                                               fake_embeddings):
    docs = ABU_DOCS + [
        ("My published LinkedIn post about Abu Prompt yesterday.",
         "evidence/old_post.md", "evidence")]
    chroma = _chroma(tmp_path, fake_embeddings, docs)
    selected = _abu_selected(store)

    result = retrieve_for_opportunity(selected, vector_store=chroma)

    assert all("published LinkedIn post" not in d.content
               for d in result.documents)


def test_missing_evidence_fails_closed_without_fallback(store, tmp_path,
                                                        fake_embeddings):
    chroma = _chroma(tmp_path, fake_embeddings, ABU_DOCS)
    entries = [_work("w", developments=[
        _dev("ghost", categories=["in_progress_projects"],
             evidence_sources=["in_progress_projects/nope.md"])])]
    _seed(store, entries)

    selected = select_opportunity(store, entries)
    result = retrieve_for_opportunity(selected, vector_store=chroma)

    assert result.documents == []


def test_boundaries_are_deterministic_and_inspectable(store):
    selected = _abu_selected(store)

    again = _abu_selected(store)
    assert selected.evidence_sources == again.evidence_sources
    assert "opportunity" not in str(selected.evidence_sources)
    assert any("configured source" in reason for reason in selected.reasons)


# ------------------------------------------------------- existing architecture ---

def test_m3_selection_unchanged(store, tmp_path, make_git_repo, make_source):
    from app.sources.models import Registry

    repo = make_git_repo("sel")
    (repo.path / "a.py").write_text("A = 1\n")
    repo.commit("base")
    base = repo.head()
    (repo.path / "b.py").write_text("B = 1\n" * 20)
    repo.commit("work")
    src = make_source(repo.path, name="sel")
    entries = [_work("w", sources=["sel"])]
    _seed(store, entries)
    store.set_review_cursor("w", "sel", base)
    registry = Registry(sources=(src,), path=tmp_path)

    opps = __import__("app.opportunities.opportunities",
                      fromlist=["build_opportunities"]).build_opportunities(
                          store, entries, registry=registry)

    assert len(opps) == 1 and opps[0].basis == "detected"


def test_verification_publishing_safeguards_unchanged():
    from app.publishing.service import PublishingService
    from app.verification.revision import revision_decision
    from app.verification.verifier import EvidenceVerifier

    assert callable(PublishingService.publish)
    assert callable(EvidenceVerifier.verify)
    assert callable(revision_decision)


def test_no_intent_created_by_targeting(store, tmp_path, fake_embeddings):
    chroma = _chroma(tmp_path, fake_embeddings, ABU_DOCS)
    selected = _abu_selected(store)
    before = store._conn.execute(
        "SELECT COUNT(*) FROM publish_intents").fetchone()[0]

    retrieve_for_opportunity(selected, vector_store=chroma)
    select_opportunity(store, ABU_ENTRIES)

    assert store._conn.execute(
        "SELECT COUNT(*) FROM publish_intents").fetchone()[0] == before


# ------------------------------------------------------- draft plumbing ---

def test_grounded_opportunity_reaches_generation(store, tmp_path,
                                                fake_embeddings):
    from app.context import build_context
    from app.generation.generator import PostGenerator

    chroma = _chroma(tmp_path, fake_embeddings, ABU_DOCS)
    selected = _abu_selected(store)
    context = build_context(
        retrieve_for_opportunity(selected, vector_store=chroma), store)

    assert context.evidence_items()

    class _FakeLLM:
        def __init__(self):
            self.calls = 0

        def invoke(self, messages):
            self.calls += 1

            class _Response:
                content = ('{"declined": false, "post": "Abu Prompt intro draft.", '
                           '"evidence_used": ["E1"], "reason": "grounded"}')

            return _Response()

    result = PostGenerator(llm=_FakeLLM()).generate(
        __import__("app.generation.models",
                   fromlist=["GenerationRequest"]).GenerationRequest(
                       context=context))

    assert result.generated


def test_empty_target_declines_without_a_model_call(store, tmp_path,
                                                   fake_embeddings):
    from app.context import build_context
    from app.generation.generator import PostGenerator
    from app.generation.models import GenerationRequest

    chroma = _chroma(tmp_path, fake_embeddings, ABU_DOCS)
    entries = [_work("w", developments=[
        _dev("ghost", evidence_sources=["in_progress_projects/nope.md"])])]
    _seed(store, entries)
    selected = select_opportunity(store, entries)
    context = build_context(
        retrieve_for_opportunity(selected, vector_store=chroma), store)

    class _ExplodingLLM:
        def invoke(self, messages):  # pragma: no cover
            raise AssertionError("model must not be called without evidence")

    result = PostGenerator(llm=_ExplodingLLM()).generate(
        GenerationRequest(context=context))

    assert result.declined
