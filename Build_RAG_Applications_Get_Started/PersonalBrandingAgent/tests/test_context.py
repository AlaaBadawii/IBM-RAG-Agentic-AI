"""Tests for the branding context layer (``PLAN.md`` Step 4).

Two groups, deliberately:

* **Assembly** — driven from hand-built ``RetrievalResult``s, so every
  assertion is about this layer's rules (grouping, ordering, coverage,
  insufficiency, separation) and not about retrieval's behaviour.
* **Milestone** — driven through the *real* corpus with the repository's fake
  embeddings: real ingestion, real chunk ids, real metadata, no network and no
  LLM. It proves that a context for a known topic carries the expected evidence
  with correct provenance, which is Step 4's stated milestone.

Nothing here needs an API key, a model download, a LinkedIn token, or a
synchronization run.
"""
import pytest

from app.context import (
    EvidenceStatus,
    FreshnessState,
    PersonalBrandingContext,
    build_context,
)
from app.context.taxonomy import (
    ALL_SECTIONS,
    EVIDENCE_SECTIONS,
    EVIDENCE_SECTION_BY_CATEGORY,
    GUIDANCE_SECTIONS,
    REPOSITORY_EVIDENCE_SECTION,
    SECTION_ORDER,
    STALE_STATE_RANK,
    UNCLASSIFIED_SECTION,
    UNCLASSIFIED_STATE_RANK,
    is_declared_state,
    state_rank,
)
from app.ingestion.metadata import EVIDENCE_STATES
from app.paths import DATA_DIR
from app.retrieval.engine import RetrievalEngine
from app.retrieval.models import RetrievalResult, RetrievedDocument
from app.sync.namespace import source_key
from tests.conftest import FakeEmbeddings


# ------------------------------------------------------------------ helpers ---

def doc(source: str, *, category: str, chunk_id: str,
        evidence_state: str | None = None, document_type: str | None = None,
        rank: int = 1, content: str = "chunk text", **extra) -> RetrievedDocument:
    """A retrieved document shaped the way the pipeline really writes them."""
    metadata = {
        "source": source,
        "category": category,
        "document_type": document_type or "unknown",
        "content_hash": "0123456789abcdef",
        **extra,
    }
    if evidence_state is not None:
        metadata["evidence_state"] = evidence_state
    return RetrievedDocument(
        content=content, score=0.5, source=source, metadata=metadata,
        strategy="vector", chunk_id=chunk_id, rank=rank,
    )


def result(*documents: RetrievedDocument, query: str = "a topic") -> RetrievalResult:
    return RetrievalResult(
        query=query, strategy="vector", documents=list(documents),
        diagnostics={"k_requested": len(documents)},
    )


def placement(context: PersonalBrandingContext) -> tuple:
    """The context's ordering, stripped of everything that is not ordering.

    ``rank`` and ``score`` are excluded on purpose: they describe the retrieval
    run, and two runs that found the same evidence in a different order must
    still assemble into the same context. Comparing them would test the input,
    not this layer.
    """
    return tuple(
        (section.name,
         tuple((item.source, item.chunk_id, item.evidence_state)
               for item in section.items))
        for section in context.all_sections
    )


# ------------------------------------------------------------ section model ---

def test_sections_are_the_corpus_categories_not_a_second_taxonomy():
    """The taxonomy cannot drift from the corpus it claims to describe.

    Read from ``data/`` itself rather than from a list copied into the test: a
    category directory added to the corpus with no section to receive it — or a
    section left behind for a directory that is gone — fails here.
    """
    categories = {path.name for path in DATA_DIR.iterdir() if path.is_dir()}
    sections = set(EVIDENCE_SECTION_BY_CATEGORY) | set(GUIDANCE_SECTIONS)
    assert sections == categories


def test_evidence_sections_are_densely_ranked_in_hierarchy_order():
    assert [s.rank for s in EVIDENCE_SECTIONS] == list(range(1, len(EVIDENCE_SECTIONS) + 1))
    assert SECTION_ORDER == tuple(s.name for s in EVIDENCE_SECTIONS)


def test_every_corpus_evidence_state_is_ranked_and_none_collides():
    """A state added to the corpus must not silently join the unranked pile."""
    ranks = [state_rank(state) for state in EVIDENCE_STATES]
    assert len(set(ranks)) == len(EVIDENCE_STATES)
    assert all(is_declared_state(state) for state in EVIDENCE_STATES)

    # STALE is the exception that makes "declared" and "ranked above
    # unclassified" different questions: it is a state the corpus names, and
    # the only one it declares no longer valid, so it sorts after everything
    # unrecognised.
    assert is_declared_state("STALE") is True
    assert state_rank("STALE") == STALE_STATE_RANK
    assert STALE_STATE_RANK > UNCLASSIFIED_STATE_RANK

    assert not is_declared_state(None)
    assert not is_declared_state("")
    assert not is_declared_state("MADE_UP")
    assert state_rank(None) == UNCLASSIFIED_STATE_RANK
    assert state_rank("MADE_UP") == UNCLASSIFIED_STATE_RANK


# ----------------------------------------------------------------- grouping ---

def test_material_lands_in_the_section_its_category_names(state_store):
    context = build_context(result(
        doc("evidence/backend/fastapi.md", category="evidence",
            chunk_id="a:0", evidence_state="VERIFIED"),
        doc("completed_projects/quizey.md", category="completed_projects",
            chunk_id="b:0"),
        doc("stories_lessons/quizey_idempotency.md", category="stories_lessons",
            chunk_id="c:0"),
        doc("certificates/ibm_genai.md", category="certificates", chunk_id="d:0"),
    ), store=state_store)

    assert [i.chunk_id for i in context.section("evidence").items] == ["a:0"]
    assert [i.chunk_id for i in context.section("completed_projects").items] == ["b:0"]
    assert [i.chunk_id for i in context.section("stories_lessons").items] == ["c:0"]
    assert [i.chunk_id for i in context.section("certificates").items] == ["d:0"]


def test_source_derived_documents_are_repository_evidence(state_store):
    """The two populations in one collection stay distinguishable.

    ``@source/<name>/…`` is authored repository code; ``data/`` is curated
    self-description. The namespace is the only thing that tells them apart,
    and a context that merged them would treat a raw source file as a claim the
    user made about themselves.
    """
    key = source_key("quizey-v2", "src/api/main.py")
    context = build_context(result(
        doc(key, category="quizey-v2", chunk_id="e:0"),
        doc("evidence/backend/fastapi.md", category="evidence", chunk_id="f:0"),
    ), store=state_store)

    repository = context.section(REPOSITORY_EVIDENCE_SECTION)
    assert [i.source for i in repository.items] == [key]
    assert [i.source for i in context.section("evidence").items] == [
        "evidence/backend/fastapi.md"
    ]
    # Its category is the source *name*, which is not a corpus category: it
    # must not have been routed to a corpus section by coincidence.
    assert repository.items[0].category == "quizey-v2"


def test_unrecognised_category_is_kept_rather_than_dropped(state_store):
    """Nothing retrieved may disappear during assembly, however odd it looks."""
    context = build_context(result(
        doc("misc/unknown.md", category="misc", chunk_id="z:0"),
    ), store=state_store)

    section = context.section(UNCLASSIFIED_SECTION)
    assert section.coverage.item_count == 1
    assert section.order == len(SECTION_ORDER) - 1
    assert context.coverage.evidence_item_count == 1


# ---------------------------------------------------------------- ordering ---

def test_sections_follow_the_documented_evidence_hierarchy(state_store):
    """Concrete repository evidence first; the audit — analysis, not work — last."""
    context = build_context(result(
        doc("audit/cross_source_audit.md", category="audit", chunk_id="a:0"),
        doc("@source/quizey-v2/src/api/main.py", category="quizey-v2",
            chunk_id="b:0"),
        doc("stories_lessons/x.md", category="stories_lessons", chunk_id="c:0"),
        doc("certificates/x.md", category="certificates", chunk_id="d:0"),
        doc("evidence/backend/fastapi.md", category="evidence", chunk_id="e:0"),
        doc("completed_projects/x.md", category="completed_projects", chunk_id="f:0"),
    ), store=state_store)

    assert [s.name for s in context.evidence_sections] == list(SECTION_ORDER)
    assert [s.order for s in context.evidence_sections] == list(range(len(SECTION_ORDER)))

    position = {s.name: s.order for s in context.evidence_sections}
    assert position[REPOSITORY_EVIDENCE_SECTION] < position["evidence"]
    assert position["evidence"] < position["completed_projects"]
    assert position["completed_projects"] < position["stories_lessons"]
    assert position["stories_lessons"] < position["audit"]


def test_stronger_evidence_states_come_first_within_a_section(state_store):
    context = build_context(result(
        doc("evidence/x/unknown.md", category="evidence", chunk_id="a:0"),
        doc("evidence/x/stale.md", category="evidence", chunk_id="b:0",
            evidence_state="STALE"),
        doc("evidence/x/documented.md", category="evidence", chunk_id="c:0",
            evidence_state="DOCUMENTED"),
        doc("evidence/x/verified.md", category="evidence", chunk_id="d:0",
            evidence_state="VERIFIED"),
        doc("evidence/x/unverified.md", category="evidence", chunk_id="e:0",
            evidence_state="UNVERIFIED"),
    ), store=state_store)

    assert [i.evidence_state for i in context.section("evidence").items] == [
        "VERIFIED", "DOCUMENTED", "UNVERIFIED", None, "STALE",
    ]


def test_ordering_is_identical_for_different_input_orders(state_store):
    """The same evidence, retrieved in a different order, assembles the same.

    Each document is given the rank its position in the input would imply, so
    the two results differ in ``rank`` exactly as two retrieval runs would.
    The assembled contexts must still be identical in placement — an ordering
    that followed the input would make a context a function of the strategy
    that produced it.
    """
    documents = [
        doc("evidence/backend/fastapi.md", category="evidence", chunk_id="a:0",
            evidence_state="DOCUMENTED"),
        doc("evidence/backend/databases.md", category="evidence", chunk_id="b:0",
            evidence_state="VERIFIED"),
        doc("completed_projects/quizey.md", category="completed_projects",
            chunk_id="c:0"),
        doc("stories_lessons/quizey_idempotency.md", category="stories_lessons",
            chunk_id="d:0"),
        doc("writing_style/alaa_writing_style.md", category="writing_style",
            chunk_id="e:0"),
        doc("@source/quizey-v2/src/api/main.py", category="quizey-v2",
            chunk_id="f:0"),
    ]
    forward = result(*[
        _reranked(document, rank) for rank, document in enumerate(documents, start=1)
    ])
    backward = result(*[
        _reranked(document, rank) for rank, document in enumerate(reversed(documents), start=1)
    ])

    assert placement(build_context(forward, store=state_store)) == placement(
        build_context(backward, store=state_store)
    )


def _reranked(document: RetrievedDocument, rank: int) -> RetrievedDocument:
    """A copy of a document as a different retrieval run would have ranked it."""
    return RetrievedDocument(
        content=document.content, score=float(rank), source=document.source,
        metadata=document.metadata, strategy=document.strategy,
        chunk_id=document.chunk_id, rank=rank,
    )


def test_duplicate_chunks_are_counted_once(state_store):
    """A fused strategy can return one chunk twice; one chunk is one evidence."""
    context = build_context(result(
        _reranked(doc("evidence/x/a.md", category="evidence", chunk_id="a:0"), 1),
        _reranked(doc("evidence/x/a.md", category="evidence", chunk_id="a:0"), 2),
    ), store=state_store)

    assert context.section("evidence").coverage.item_count == 1
    assert context.coverage.evidence_item_count == 1
    assert context.diagnostics["duplicates_skipped"] == 1


# ---------------------------------------------------------------- coverage ---

def test_coverage_reports_counts_and_distinct_states_per_section(state_store):
    context = build_context(result(
        doc("evidence/x/a.md", category="evidence", chunk_id="a:0",
            evidence_state="VERIFIED"),
        doc("evidence/x/b.md", category="evidence", chunk_id="b:0",
            evidence_state="VERIFIED"),
        doc("evidence/x/c.md", category="evidence", chunk_id="c:0",
            evidence_state="DOCUMENTED"),
        doc("evidence/x/d.md", category="evidence", chunk_id="d:0"),
    ), store=state_store)

    coverage = context.section("evidence").coverage
    assert coverage.item_count == 4
    assert coverage.is_empty is False
    # Set semantics: the repeated VERIFIED appears once.
    assert coverage.evidence_states_present == frozenset({"VERIFIED", "DOCUMENTED"})
    assert coverage.unclassified_count == 1

    assert context.coverage.evidence_item_count == 4
    assert "evidence" in context.coverage.populated_sections


def test_an_empty_section_is_present_and_says_so(state_store):
    """Emptiness is a reported result; absence would be an omission."""
    context = build_context(result(
        doc("evidence/backend/fastapi.md", category="evidence", chunk_id="a:0"),
    ), store=state_store)

    section = context.section("certificates")
    assert section.coverage.item_count == 0
    assert section.coverage.is_empty is True
    assert section.coverage.evidence_states_present == frozenset()
    assert section.coverage.unclassified_count == 0
    assert "certificates" in context.coverage.empty_sections
    # The context as a whole is still usable — one empty section is not
    # insufficient evidence.
    assert context.evidence_status is EvidenceStatus.SUFFICIENT


# ----------------------------------------------------------- insufficiency ---

def test_no_documents_is_a_valid_explicit_insufficiency(state_store):
    """Not ``{}``, not ``None``, and not an exception. A domain result."""
    context = build_context(result(query="a topic with nothing behind it"),
                            store=state_store)

    assert isinstance(context, PersonalBrandingContext)
    assert context.evidence_status is EvidenceStatus.INSUFFICIENT
    assert context.is_insufficient is True

    # Every named section exists, and every one of them is honestly empty.
    assert [s.name for s in context.all_sections] == list(ALL_SECTIONS)
    assert all(s.coverage.is_empty for s in context.all_sections)
    assert context.coverage.total_item_count == 0
    assert context.evidence_items() == ()
    assert context.guidance_items() == ()
    assert context.query == "a topic with nothing behind it"


def test_a_context_with_no_evidence_and_one_with_evidence_are_distinguishable(state_store):
    """The two states a generator must never confuse, side by side."""
    empty = build_context(result(), store=state_store)
    populated = build_context(result(
        doc("evidence/backend/fastapi.md", category="evidence", chunk_id="a:0"),
    ), store=state_store)

    assert empty.evidence_status is EvidenceStatus.INSUFFICIENT
    assert populated.evidence_status is EvidenceStatus.SUFFICIENT
    assert empty.evidence_status is not populated.evidence_status


# ------------------------------------------------- evidence vs. positioning ---

def test_positioning_and_style_are_kept_out_of_the_evidence(state_store):
    """The separation Step 4 exists to make structural."""
    context = build_context(result(
        doc("writing_style/alaa_writing_style.md", category="writing_style",
            chunk_id="a:0", document_type="writing_style"),
        doc("public_positioning/portfolio.md", category="public_positioning",
            chunk_id="b:0", document_type="positioning"),
        doc("vision_goals/my_vision.md", category="vision_goals",
            chunk_id="c:0", document_type="vision"),
        doc("evidence/backend/fastapi.md", category="evidence", chunk_id="d:0",
            evidence_state="VERIFIED"),
    ), store=state_store)

    # Counted apart, and only the evidence counts.
    assert context.coverage.evidence_item_count == 1
    assert context.coverage.guidance_item_count == 3

    assert [s.name for s in context.guidance_sections] == list(GUIDANCE_SECTIONS)
    for name in GUIDANCE_SECTIONS:
        assert context.section(name).coverage.item_count == 1

    # No guidance item reached an evidence section, and none contributed a
    # chunk id to the evidence item set.
    evidence_chunks = {i.chunk_id for i in context.evidence_items()}
    assert evidence_chunks == {"d:0"}
    evidence_sources = {i.source for i in context.evidence_items()}
    assert evidence_sources == {"evidence/backend/fastapi.md"}
    assert not any(
        s.coverage.item_count for s in context.evidence_sections
        if s.name in GUIDANCE_SECTIONS
    )


def test_document_type_recognises_guidance_when_the_category_does_not(state_store):
    """The secondary recognition path, and the one place a miss is dangerous.

    ``document_type`` is derived from ``category`` today, so this only bites
    when classification stops being path-derived. It is tested anyway because
    the failure mode is asymmetric: material that should be guidance gets
    counted as evidence, and a generator then treats a positioning statement as
    proof.
    """
    context = build_context(result(
        doc("somewhere/voice.md", category="misc", chunk_id="a:0",
            document_type="positioning"),
    ), store=state_store)

    assert context.section("public_positioning").coverage.item_count == 1
    assert context.coverage.evidence_item_count == 0
    assert context.evidence_status is EvidenceStatus.INSUFFICIENT


def test_positioning_alone_is_insufficient_evidence(state_store):
    """A post that only knows how to write has nothing to write about."""
    context = build_context(result(
        doc("writing_style/alaa_writing_style.md", category="writing_style",
            chunk_id="a:0"),
        doc("public_positioning/portfolio.md", category="public_positioning",
            chunk_id="b:0"),
    ), store=state_store)

    assert context.evidence_status is EvidenceStatus.INSUFFICIENT
    assert context.coverage.evidence_item_count == 0
    assert context.coverage.guidance_item_count == 2
    assert len(context.guidance_items()) == 2


# --------------------------------------------------------------- provenance ---

def test_every_evidence_item_keeps_its_attribution(state_store):
    context = build_context(result(
        doc("evidence/backend/fastapi.md", category="evidence", chunk_id="a:0",
            evidence_state="VERIFIED", domain="backend"),
        doc("evidence/backend/databases.md", category="evidence", chunk_id="b:0",
            domain="backend"),
        doc(source_key("quizey-v2", "src/api/main.py"), category="quizey-v2",
            chunk_id="c:0"),
    ), store=state_store)

    for item in context.evidence_items():
        assert item.source
        assert item.chunk_id
        # The metadata came through untouched, so nothing a later step needs
        # was predicted or dropped here.
        assert item.source == item.metadata["source"]
        assert item.metadata["content_hash"] == "0123456789abcdef"

    fastapi = next(i for i in context.evidence_items()
                   if i.source == "evidence/backend/fastapi.md")
    assert fastapi.chunk_id == "a:0"
    assert fastapi.evidence_state == "VERIFIED"
    assert fastapi.metadata["domain"] == "backend"

    # An undeclared state stays undeclared; it is not defaulted to something.
    databases = next(i for i in context.evidence_items()
                     if i.source == "evidence/backend/databases.md")
    assert databases.evidence_state is None


# ------------------------------------------------- retrieval failure paths ---

class _FailingCollection:
    """A Chroma collection that cannot be queried."""

    def query(self, **_kwargs):
        raise RuntimeError("vector store unreachable")


class _FailingStore:
    """Stands in for an unavailable Chroma store, embedding function included."""

    _collection = _FailingCollection()
    _embedding_function = FakeEmbeddings()


def test_retrieval_failure_propagates_instead_of_becoming_insufficiency(state_store):
    """Infrastructure failure and "no evidence" must not be reachable from
    one another. The failure is raised by the real retrieval stack and is not
    caught anywhere on the way out, so a caller cannot receive a context that
    reads as "there is nothing to say" when the truth is "retrieval is broken".
    """
    engine = RetrievalEngine(store=_FailingStore())

    with pytest.raises(RuntimeError, match="vector store unreachable"):
        build_context(engine.retrieve("FastAPI experience"), store=state_store)


# ---------------------------------------------------------------- freshness ---

def test_the_corpus_is_reported_as_untracked_rather_than_fresh_or_stale(state_store):
    """``data/`` has no checkpoint and never will; that is a boundary, not a gap."""
    context = build_context(result(
        doc("evidence/backend/fastapi.md", category="evidence", chunk_id="a:0"),
    ), store=state_store)

    corpus = context.source_state.for_identity("data")
    assert corpus is not None
    assert corpus.tracked is False
    assert corpus.state is FreshnessState.UNKNOWN
    assert corpus.last_synced_at is None
    assert corpus.last_revision is None
    assert context.source_state.is_known is False


def test_source_freshness_is_read_from_the_synchronization_checkpoint(state_store):
    state_store.record_sync_success("quizey-v2", "abc123")
    checkpoint = state_store.get_checkpoint("quizey-v2")

    context = build_context(result(
        doc(source_key("quizey-v2", "src/api/main.py"), category="quizey-v2",
            chunk_id="a:0"),
    ), store=state_store)

    state = context.source_state.for_identity("quizey-v2")
    assert state is not None
    assert state.tracked is True
    assert state.state is FreshnessState.SYNCHRONIZED
    assert state.last_revision == "abc123"
    # The timestamp is the checkpoint's, character for character — this layer
    # read it rather than producing one.
    assert state.last_synced_at == checkpoint.last_synced_at
    assert context.source_state.is_known is True


def test_a_source_that_has_never_been_synchronized_is_unknown(state_store):
    context = build_context(result(
        doc(source_key("quizey-v2", "src/api/main.py"), category="quizey-v2",
            chunk_id="a:0"),
    ), store=state_store)

    state = context.source_state.for_identity("quizey-v2")
    assert state.state is FreshnessState.UNKNOWN
    assert state.tracked is True
    assert state.last_synced_at is None
    assert state.last_revision is None


def test_a_failed_sync_reports_failure_without_erasing_the_last_good_revision(state_store):
    state_store.record_sync_success("quizey-v2", "abc123")
    state_store.record_sync_failure("quizey-v2")

    context = build_context(result(
        doc(source_key("quizey-v2", "src/api/main.py"), category="quizey-v2",
            chunk_id="a:0"),
    ), store=state_store)

    state = context.source_state.for_identity("quizey-v2")
    assert state.state is FreshnessState.FAILED
    # The content the last successful pass indexed is still indexed, so the
    # revision is still a true fact about this source.
    assert state.last_revision == "abc123"
    assert state.last_synced_at is not None
    assert context.source_state.for_identity("quizey-v2") in context.source_state.failed_sources


def test_freshness_carries_no_invented_timestamps(state_store):
    """Nothing here consults a clock. With no checkpoints, nothing is dated."""
    context = build_context(result(
        doc("evidence/backend/fastapi.md", category="evidence", chunk_id="a:0"),
        doc(source_key("quizey-v2", "src/api/main.py"), category="quizey-v2",
            chunk_id="b:0"),
    ), store=state_store)

    identities = [s.identity for s in context.source_state.sources]
    assert identities == ["data", "quizey-v2"]
    for state in context.source_state.sources:
        assert state.last_synced_at is None
        assert state.last_attempt_at is None
        assert state.last_revision is None
        assert state.state is FreshnessState.UNKNOWN
    assert context.source_state.is_known is False


def test_a_context_with_no_documents_reports_no_sources(state_store):
    context = build_context(result(), store=state_store)
    assert context.source_state.sources == ()
    assert context.source_state.is_known is False


# ---------------------------------------------------------------- milestone ---

@pytest.fixture(scope="module")
def corpus_store(tmp_path_factory):
    """The real ``data/`` corpus, ingested with the repository's fake embeddings.

    The whole corpus and not a slice, because a slice would change every
    category the metadata is derived from. No model download and no network.
    """
    from langchain_chroma import Chroma

    from app.ingestion.pipeline import run_ingestion

    store = Chroma(
        collection_name="context_milestone",
        embedding_function=FakeEmbeddings(),
        persist_directory=str(tmp_path_factory.mktemp("context_chroma")),
    )
    run_ingestion(data_dir=DATA_DIR, embeddings=FakeEmbeddings(), store=store)
    return store


def test_milestone_known_topic_has_expected_evidence_with_correct_provenance(
        corpus_store, state_store):
    """Step 4's milestone, on real corpus material.

    "Backend databases and FastAPI" is a topic the repository demonstrably
    holds evidence about, so the expected outcome is not a guess: the two
    ``data/evidence/backend/`` documents must arrive in the ``evidence``
    section, carrying the chunk ids ingestion actually wrote and the evidence
    states the extraction rules actually derived.
    """
    engine = RetrievalEngine(store=corpus_store)
    retrieved = engine.retrieve(
        "FastAPI and database work", strategy="metadata", top_k=50,
        filters={"category": "evidence", "domain": "backend"},
    )
    assert retrieved.documents, "the metadata filter found no backend evidence"

    context = build_context(retrieved, store=state_store)

    assert context.evidence_status is EvidenceStatus.SUFFICIENT
    assert context.strategy == "metadata"

    evidence = context.section("evidence")
    sources = {item.source for item in evidence.items}
    assert {"evidence/backend/fastapi.md", "evidence/backend/databases.md"} <= sources

    # Nothing appeared anywhere else, and the evidence section is where the
    # whole retrieval result went.
    assert evidence.coverage.item_count == len(retrieved.documents)
    assert context.coverage.evidence_item_count == len(retrieved.documents)

    # Provenance: every assembled chunk id is one the store really holds, and
    # the first chunk of the FastAPI document is the deterministic id the
    # pipeline derives for it.
    stored_ids = set(corpus_store.get(include=["metadatas"])["ids"])
    for item in evidence.items:
        assert item.chunk_id in stored_ids
        assert item.source == item.metadata["source"]

    from app.ingestion.chunker import clean_text, content_hash

    fastapi_text = (DATA_DIR / "evidence/backend/fastapi.md").read_text(encoding="utf-8")
    expected_first_chunk = f"{content_hash(clean_text(fastapi_text))}:0"
    fastapi_chunks = [i for i in evidence.items
                      if i.source == "evidence/backend/fastapi.md"]
    assert fastapi_chunks[0].chunk_id == expected_first_chunk

    # Evidence states are the corpus's own, not this layer's invention:
    # fastapi.md declares IN_PROGRESS, and databases.md declares its states
    # inline in prose, which the extraction rules deliberately do not trust.
    assert fastapi_chunks[0].evidence_state == "IN_PROGRESS"
    databases = next(i for i in evidence.items
                     if i.source == "evidence/backend/databases.md")
    assert databases.evidence_state is None

    # Ordering, on real metadata: a declared state outranks an undeclared one,
    # and within one source the chunks keep their deterministic id order.
    assert evidence.items.index(fastapi_chunks[0]) < evidence.items.index(databases)
    assert [i.chunk_id for i in fastapi_chunks] == sorted(
        i.chunk_id for i in fastapi_chunks
    )
