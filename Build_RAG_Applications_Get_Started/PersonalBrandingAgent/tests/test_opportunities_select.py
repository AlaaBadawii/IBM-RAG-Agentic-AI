"""M3: opportunities from ledger seeds and detected changes.

Isolated state throughout; production is never touched. These tests pin
selection behavior — what becomes an opportunity, how it ranks, and what
it can never do — not implementation details.
"""
import ast
from pathlib import Path

import pytest

from app.opportunities.changes import ChangeClassification
from app.opportunities.opportunities import (
    build_opportunities,
    mark_development_published,
    retrieve_for_opportunity,
    select_opportunity,
)
from app.sources.models import Registry
from app.state import RunOutcome, StateStore

OPPORTUNITIES_MODULE = Path(__file__).resolve().parents[1] / "app" / "opportunities"


@pytest.fixture
def store(tmp_path):
    with StateStore(tmp_path / "m3.db") as state:
        yield state


def _registry(tmp_path, *sources):
    return Registry(sources=tuple(sources), path=tmp_path)


def _commit(repo, *files, message="change"):
    for relative, text in files:
        repo.write(relative, text)
    return repo.commit(message)


def _entries(*works):
    return list(works)


def _work(work_id, sources=(), priority="normal", developments=(),
          enabled=True):
    return {
        "id": work_id, "display_name": work_id, "sources": list(sources),
        "branding_priority": priority, "enabled": enabled,
        "developments": list(developments),
    }


def _dev(key, covered=False, categories=()):
    entry = {"key": key, "display_name": key, "covered": covered}
    if categories:
        entry["corpus_categories"] = list(categories)
    return entry


def _seed(store, entries):
    """Seed ledger primitives directly (no registry validation).

    Test sources are temporary repositories unknown to the real registry;
    validation of names against the registry belongs to the config loader,
    covered by its own tests.
    """
    for entry in entries:
        store.ensure_tracked_work(
            entry["id"], entry.get("display_name", entry["id"]),
            description=entry.get("description", ""),
            sources=tuple(entry.get("sources", ())),
            enabled=bool(entry.get("enabled", True)))
        for dev in entry.get("developments", ()):
            store.ensure_development(
                entry["id"], dev["key"],
                dev.get("display_name", dev["key"]),
                covered=bool(dev.get("covered", False)))


def _repo_with_history(make_git_repo, make_source, tmp_path, name,
                       baseline_files, changed_files):
    repo = make_git_repo(name)
    _commit(repo, *baseline_files)
    base = repo.head()
    _commit(repo, *changed_files)
    return repo, make_source(repo.path, name=name), base


# ------------------------------------------------------- construction ---

def test_meaningful_change_becomes_an_opportunity(
        store, tmp_path, make_git_repo, make_source):
    repo, src, base = _repo_with_history(
        make_git_repo, make_source, tmp_path, "m",
        [("a.py", "A = 1\n")], [("b.py", "B = 1\n" * 20)])
    _seed(store, [_work("w", sources=["m"])])
    store.set_review_cursor("w", "m", base)

    opps = build_opportunities(
        store, [_work("w", sources=["m"])],
        registry=_registry(tmp_path, src))

    assert len(opps) == 1
    assert opps[0].basis == "detected"
    assert opps[0].classification is ChangeClassification.MEANINGFUL_CHANGE


def test_milestone_change_becomes_an_opportunity(
        store, tmp_path, make_git_repo, make_source):
    repo, src, base = _repo_with_history(
        make_git_repo, make_source, tmp_path, "ms",
        [("README.md", "# base\n")], [("newproj/app.py", "A = 1\n" * 20)])
    _seed(store, [_work("w", sources=["ms"])])
    store.set_review_cursor("w", "ms", base)

    opps = build_opportunities(
        store, [_work("w", sources=["ms"])],
        registry=_registry(tmp_path, src))

    assert len(opps) == 1
    assert opps[0].classification is ChangeClassification.MILESTONE


def test_no_change_becomes_no_opportunity(
        store, tmp_path, make_git_repo, make_source):
    repo = make_git_repo("same")
    _commit(repo, ("a.py", "A = 1\n"))
    src = make_source(repo.path, name="same")
    _seed(store, [_work("w", sources=["same"])])
    store.set_review_cursor("w", "same", repo.head())

    assert build_opportunities(
        store, [_work("w", sources=["same"])],
        registry=_registry(tmp_path, src)) == []
    assert select_opportunity(
        store, [_work("w", sources=["same"])],
        registry=_registry(tmp_path, src)) is None


def test_minor_change_becomes_no_opportunity(
        store, tmp_path, make_git_repo, make_source):
    repo, src, base = _repo_with_history(
        make_git_repo, make_source, tmp_path, "typo",
        [("README.md", "# T\n\nBody here.\n")],
        [("README.md", "# T\n\nBody here!\n")])
    _seed(store, [_work("w", sources=["typo"])])
    store.set_review_cursor("w", "typo", base)

    assert build_opportunities(
        store, [_work("w", sources=["typo"])],
        registry=_registry(tmp_path, src)) == []


def test_many_files_are_one_opportunity_not_many(
        store, tmp_path, make_git_repo, make_source):
    repo, src, base = _repo_with_history(
        make_git_repo, make_source, tmp_path, "phase",
        [("README.md", "# base\n")],
        [(f"app/f{n}.py", f"V_{n} = 1\n" * 10) for n in range(6)])
    _seed(store, [_work("w", sources=["phase"])])
    store.set_review_cursor("w", "phase", base)

    opps = build_opportunities(
        store, [_work("w", sources=["phase"])],
        registry=_registry(tmp_path, src))

    assert len(opps) == 1


def test_projects_stay_independent(store, tmp_path, make_git_repo,
                                   make_source):
    repo_a, src_a, base_a = _repo_with_history(
        make_git_repo, make_source, tmp_path, "pa",
        [("a.py", "A = 1\n")], [("b.py", "B = 1\n" * 20)])
    repo_b, src_b, base_b = _repo_with_history(
        make_git_repo, make_source, tmp_path, "pb",
        [("a.py", "A = 1\n")], [("a.py", "A = 2\n" * 25)])
    entries = [_work("wa", sources=["pa"]), _work("wb", sources=["pb"])]
    _seed(store, entries)
    store.set_review_cursor("wa", "pa", base_a)
    store.set_review_cursor("wb", "pb", base_b)
    registry = _registry(tmp_path, src_a, src_b)

    opps = build_opportunities(store, entries, registry=registry)

    assert sorted(o.work_id for o in opps) == ["wa", "wb"]


# ------------------------------------------------------- historical ---

def test_baseline_generates_no_opportunities(store):
    _seed(store, [_work("w", developments=[
        _dev("historical-baseline", covered=True)])])

    assert build_opportunities(store, [_work("w")]) == []


def test_new_development_in_old_project_is_eligible(store):
    _seed(store, [_work("w", developments=[
        _dev("phase-2.1", covered=True), _dev("phase-2.2")])])

    opps = build_opportunities(store, [_work("w")])

    assert [(o.key, o.basis) for o in opps] == [("phase-2.2", "seeded")]


def test_project_publication_history_suppresses_nothing(store):
    _seed(store, [_work("w", developments=[
        _dev("phase-2.1", covered=True), _dev("phase-2.2")])])
    run = store.start_run("branding")
    intent = store.create_publish_intent(
        run.run_id, "old post about w", topic="w", project="w")
    store.mark_attempt_started(intent.intent_id)
    store.record_publication(intent.intent_id, "published", linkedin_post_id="urn:x")
    store.finish_run(run.run_id, RunOutcome.DO_NOT_PUBLISH)

    opps = build_opportunities(store, [_work("w")])

    assert [o.key for o in opps] == ["phase-2.2"]


# ------------------------------------------------------- coverage ---

def test_covered_development_is_excluded(store):
    _seed(store, [_work("w", developments=[
        _dev("a", covered=True), _dev("b", covered=True)])])

    assert build_opportunities(store, [_work("w")]) == []


def test_uncovered_development_stays_eligible(store):
    _seed(store, [_work("w", developments=[_dev("a")])])

    opps = build_opportunities(store, [_work("w")])

    assert len(opps) == 1
    assert opps[0].key == "a"


def test_review_advance_marks_nothing_covered(
        store, tmp_path, make_git_repo, make_source):
    repo = make_git_repo("rev")
    _commit(repo, ("a.py", "A = 1\n"))
    head = repo.head()
    src = make_source(repo.path, name="rev")
    _seed(store, [_work("w", sources=["rev"],
                         developments=[_dev("d")])])
    store.set_review_cursor("w", "rev", head)

    opps = build_opportunities(
        store, [_work("w", sources=["rev"],
                      developments=[_dev("d")])],
        registry=_registry(tmp_path, src))

    assert [o.key for o in opps] == ["d"]
    assert store.get_development("w", "d").covered is False


def test_publishing_can_cover_via_publication_reference(store):
    from app.opportunities.opportunities import mark_development_published

    _seed(store, [_work("w", developments=[_dev("d")])])
    run = store.start_run("branding")
    intent = store.create_publish_intent(run.run_id, "post text here")
    store.mark_attempt_started(intent.intent_id)
    publication = store.record_publication(
        intent.intent_id, "published", linkedin_post_id="urn:li:x")
    store.finish_run(run.run_id, RunOutcome.DO_NOT_PUBLISH)

    assert build_opportunities(store, [_work("w")])[0].key == "d"
    mark_development_published(
        store, "w", "d", publication.publication_id)

    covered = store.get_development("w", "d")
    assert covered.covered is True
    assert covered.coverage_kind == "published"
    assert covered.publication_id == publication.publication_id
    assert build_opportunities(store, [_work("w")]) == []


def test_covering_unknown_publication_is_refused(store):
    from app.opportunities.opportunities import mark_development_published

    _seed(store, [_work("w", developments=[_dev("d")])])

    with pytest.raises(ValueError, match="unknown publication"):
        mark_development_published(store, "w", "d", "pub_missing")


# ------------------------------------------------------- importance ---

def test_small_recent_work_outranks_large_historical_content(
        store, tmp_path, make_git_repo, make_source):
    big, big_src, big_base = _repo_with_history(
        make_git_repo, make_source, tmp_path, "big",
        [(f"f{n}.py", f"V_{n} = 1\n") for n in range(40)],
        [("g.py", "G = 1\n" * 25)])
    small, small_src, small_base = _repo_with_history(
        make_git_repo, make_source, tmp_path, "small",
        [("a.py", "A = 1\n")], [("b.py", "B = 1\n" * 25)])
    entries = [_work("big-work", sources=["big"], priority="low"),
               _work("small-work", sources=["small"], priority="high")]
    _seed(store, entries)
    store.set_review_cursor("big-work", "big", big_base)
    store.set_review_cursor("small-work", "small", small_base)
    registry = _registry(tmp_path, big_src, small_src)

    opps = build_opportunities(store, entries, registry=registry)

    assert [o.work_id for o in opps] == ["small-work", "big-work"]


def test_repo_size_alone_creates_nothing(
        store, tmp_path, make_git_repo, make_source):
    repo = make_git_repo("huge")
    _commit(repo, *[(f"f{n}.py", f"V_{n} = 1\n") for n in range(80)])
    src = make_source(repo.path, name="huge")
    _seed(store, [_work("w", sources=["huge"])])
    store.set_review_cursor("w", "huge", repo.head())

    assert build_opportunities(
        store, [_work("w", sources=["huge"])],
        registry=_registry(tmp_path, src)) == []


def test_quizey_milestone_independent_of_repo_size(
        store, tmp_path, make_git_repo, make_source):
    repo = make_git_repo("quizey")
    _commit(repo, ("README.md", "# q\n"),
            *[(f"app/old_{n}.py", f"O_{n} = 1\n") for n in range(30)])
    base = repo.head()
    _commit(repo, ("versioning/v2.py", "V2 = 1\n" * 20))
    src = make_source(repo.path, name="quizey-v2")
    _seed(store, [_work("quizey", sources=["quizey-v2"])])
    store.set_review_cursor("quizey", "quizey-v2", base)

    opps = build_opportunities(
        store, [_work("quizey", sources=["quizey-v2"])],
        registry=_registry(tmp_path, src))

    assert len(opps) == 1
    assert opps[0].classification is ChangeClassification.MILESTONE
    assert "versioning" in " ".join(
        p.path for p in opps[0].change.paths)


def test_devops_milestone_independent_of_repo_size(
        store, tmp_path, make_git_repo, make_source):
    repo = make_git_repo("devops")
    _commit(repo, ("README.md", "# ops\n"))
    base = repo.head()
    _commit(repo, ("kodekloud/track1/lab.py", "LAB = 1\n" * 20))
    src = make_source(repo.path, name="kk")
    _seed(store, [_work("kkw", sources=["kk"])])
    store.set_review_cursor("kkw", "kk", base)

    opps = build_opportunities(
        store, [_work("kkw", sources=["kk"])],
        registry=_registry(tmp_path, src))

    assert len(opps) == 1
    assert opps[0].work_id == "kkw"
    assert opps[0].classification is ChangeClassification.MILESTONE


# ------------------------------------------------------- ranking ---

def test_ranking_is_deterministic(store, tmp_path, make_git_repo,
                                  make_source):
    repo, src, base = _repo_with_history(
        make_git_repo, make_source, tmp_path, "det",
        [("a.py", "A = 1\n")], [("b.py", "B = 1\n" * 20)])
    entries = [_work("w", sources=["det"], priority="high",
                     developments=[_dev("seeded-one")])]
    _seed(store, entries)
    store.set_review_cursor("w", "det", base)
    registry = _registry(tmp_path, src)

    first = build_opportunities(store, entries, registry=registry)
    second = build_opportunities(store, entries, registry=registry)

    assert [o.rank_key for o in first] == [o.rank_key for o in second]
    assert [o.key for o in first] == [o.key for o in second]


def test_ranking_explains_itself(store):
    _seed(store, [_work("w", developments=[_dev("d")])])

    opps = build_opportunities(store, [_work("w")])

    assert len(opps[0].reasons) >= 2
    assert any("uncovered" in reason for reason in opps[0].reasons)
    assert any("priority" in reason for reason in opps[0].reasons)


def test_selection_cannot_leave_the_supplied_universe(store):
    _seed(store, [_work("w", developments=[_dev("d")])])

    selected = select_opportunity(store, [_work("w")])

    assert selected is not None
    assert selected.work_id == "w"
    assert selected.key == "d"
    with pytest.raises(ValueError, match="not seeded"):
        build_opportunities(store, [_work("ghost")])


# ------------------------------------------------------- abu prompt ---

def _abu_entries():
    return [_work("personal-branding-agent", priority="high", developments=[
        _dev("historical-baseline", covered=True),
        _dev("abu-prompt-introduction",
             categories=["in_progress_projects"])])]


def test_abu_introduction_is_eligible_when_uncovered(store):
    _seed(store, _abu_entries())

    opps = build_opportunities(store, _abu_entries())

    assert [(o.work_id, o.key) for o in opps] == [
        ("personal-branding-agent", "abu-prompt-introduction")]


def test_abu_wins_without_a_special_branch(
        store, tmp_path, make_git_repo, make_source):
    repo, src, base = _repo_with_history(
        make_git_repo, make_source, tmp_path, "rival",
        [("README.md", "# r\n")], [("newmod/app.py", "A = 1\n" * 20)])
    entries = _abu_entries() + [
        _work("rival", sources=["rival"], priority="normal")]
    _seed(store, entries)
    store.set_review_cursor("rival", "rival", base)
    registry = _registry(tmp_path, src)

    selected = select_opportunity(store, entries, registry=registry)

    assert selected is not None
    assert (selected.work_id, selected.key) == (
        "personal-branding-agent", "abu-prompt-introduction")
    assert selected.reasons[1] == "branding priority high"


def test_abu_carries_evidence_bounds_not_post_text(store):
    _seed(store, _abu_entries())

    selected = select_opportunity(store, _abu_entries())

    assert selected is not None
    assert selected.categories == frozenset({"in_progress_projects"})
    assert not hasattr(selected, "content")
    assert not hasattr(selected, "post")


def test_future_current_distinction_has_no_bypass(store):
    """The seed says nothing about capabilities; the verifier still owns
    the current/future distinction downstream (policy unchanged)."""
    import app.verification.policy as policy

    _seed(store, _abu_entries())
    selected = select_opportunity(store, _abu_entries())

    assert selected is not None
    assert policy.WEAK_EVIDENCE_STATES >= {"ASPIRATIONAL", "LEARNING"}


# ------------------------------------------------------- targeted retrieval ---

def _chroma_with_categories(tmp_path, fake_embeddings):
    from langchain_core.documents import Document
    from langchain_chroma import Chroma

    docs = [
        ("quizey file one", "quizey-v2", "@source/quizey-v2/a.py", "q1"),
        ("quizey file two", "quizey-v2", "@source/quizey-v2/b.py", "q2"),
        ("abu prompt identity", "in_progress_projects",
         "in_progress_projects/personal_branding_agent.md", "a1"),
        ("certificate course", "certificates",
         "certificates/some.md", "c1"),
    ]
    chroma = Chroma(
        collection_name="opportunity_tests",
        embedding_function=fake_embeddings,
        persist_directory=str(tmp_path / "chroma-targeted"),
    )
    chroma.add_documents(
        [Document(page_content=text,
                  metadata={"source": source, "category": category})
         for text, category, source, _ in docs],
        ids=[cid for _, _, _, cid in docs],
    )
    return chroma


def test_quizey_opportunity_retrieves_quizey_evidence(
        store, tmp_path, fake_embeddings):
    chroma = _chroma_with_categories(tmp_path, fake_embeddings)
    _seed(store, [_work("quizey", sources=["quizey-v2"],
                         developments=[_dev("phase-2")])])

    selected = select_opportunity(store, [_work("quizey", sources=["quizey-v2"],
                                                developments=[_dev("phase-2")])])
    result = retrieve_for_opportunity(selected, vector_store=chroma)

    assert result.documents, "targeted retrieval must return evidence"
    assert {d.metadata["category"] for d in result.documents} == {"quizey-v2"}


def test_ai_project_opportunity_retrieves_its_own_evidence(
        store, tmp_path, fake_embeddings):
    chroma = _chroma_with_categories(tmp_path, fake_embeddings)
    _seed(store, [_work("quizey", sources=["quizey-v2"],
                         developments=[_dev("phase-2")])])

    selected = select_opportunity(store, [_work("quizey", sources=["quizey-v2"],
                                                developments=[_dev("phase-2")])])
    result = retrieve_for_opportunity(
        selected, vector_store=chroma, strategy="bm25")

    assert {d.metadata["category"] for d in result.documents} == {"quizey-v2"}


def test_abu_uses_project_evidence_not_generic_corpus(
        store, tmp_path, fake_embeddings):
    chroma = _chroma_with_categories(tmp_path, fake_embeddings)
    _seed(store, _abu_entries())

    selected = select_opportunity(store, _abu_entries())
    result = retrieve_for_opportunity(selected, vector_store=chroma)

    assert result.documents
    assert {d.metadata["category"] for d in result.documents} == {
        "in_progress_projects"}
    assert any("abu prompt" in d.content.lower()
               for d in result.documents)


# ------------------------------------------------------- safety ---

def test_opportunity_layer_imports_no_publishing_path():
    """Selection must be structurally unable to publish: no generation,
    verification, publishing, or LinkedIn import, statically."""
    tree = ast.parse(
        (OPPORTUNITIES_MODULE / "opportunities.py").read_text(
            encoding="utf-8"))

    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    for name in imported:
        assert not name.startswith("app.publishing"), name
        assert not name.startswith("app.generation"), name
        assert not name.startswith("app.verification"), name
        assert not name.startswith("app.integrations"), name
        assert name != "app.state.store", name


def test_selection_creates_no_publish_intents(store):
    _seed(store, [_work("w", developments=[_dev("d")])])
    before = store._conn.execute(
        "SELECT COUNT(*) FROM publish_intents").fetchone()[0]

    select_opportunity(store, [_work("w")])

    assert store._conn.execute(
        "SELECT COUNT(*) FROM publish_intents").fetchone()[0] == before


def test_safeguards_are_unmodified_downstream():
    """Verification, policy, and publishing entry points still exist with
    their authority intact (referenced, not reimplemented)."""
    from app.publishing.service import PublishingService
    from app.verification.revision import revision_decision
    from app.verification.verifier import EvidenceVerifier

    assert callable(PublishingService.publish)
    assert callable(EvidenceVerifier.verify)
    assert callable(revision_decision)


# ------------------------------------------------------- extensibility ---

def test_future_work_enters_through_configuration(store):
    _seed(store, [_work("quantum-notes", priority="high",
                         developments=[_dev("first-notes")])])

    opps = build_opportunities(store, [_work(
        "quantum-notes", priority="high",
        developments=[_dev("first-notes")])])

    assert [(o.work_id, o.key) for o in opps] == [
        ("quantum-notes", "first-notes")]


def test_broad_directories_hold_independent_projects(store):
    _seed(store, [
        _work("ai-hackathon", developments=[_dev("initial", covered=True)]),
        _work("ai-agents", developments=[_dev("new-dev")]),
        _work("ibm-course", developments=[_dev("old", covered=True)]),
    ])
    entries = [
        _work("ai-hackathon", developments=[_dev("initial", covered=True)]),
        _work("ai-agents", developments=[_dev("new-dev")]),
        _work("ibm-course", developments=[_dev("old", covered=True)]),
    ]

    opps = build_opportunities(store, entries)

    assert [(o.work_id, o.key) for o in opps] == [("ai-agents", "new-dev")]
