"""Abu Prompt launch context: discoverable, behaviour-preserving, no bypass.

Covers the `Prepare Abu Prompt launch context` change, which touches only
`data/` plus this test:

* launch facts are discoverable through the existing pipeline
  (ingestion -> retrieval -> context assembly), in the right sections;
* Agent/workflow behaviour is unchanged (PUBLISH still needs a passing
  verification; the workflow still has exactly its three phases);
* no special launch publish path exists anywhere in `app/`.
"""
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = PROJECT_ROOT / "app"


@pytest.fixture(scope="module")
def launch_store(tmp_path_factory):
    """The real `data/` corpus, ingested with the repository's fake embeddings."""
    from langchain_chroma import Chroma

    from app.ingestion.pipeline import run_ingestion
    from app.paths import DATA_DIR
    from tests.conftest import FakeEmbeddings

    store = Chroma(
        collection_name="abu_prompt_launch_context",
        embedding_function=FakeEmbeddings(),
        persist_directory=str(tmp_path_factory.mktemp("abu_prompt_chroma")),
    )
    run_ingestion(data_dir=DATA_DIR, embeddings=FakeEmbeddings(), store=store)
    return store


def _retrieve_category(store, category: str):
    from app.retrieval.engine import RetrievalEngine

    engine = RetrievalEngine(store=store)
    return engine.retrieve(
        "Abu Prompt", strategy="metadata", top_k=50,
        filters={"category": category},
    )


def test_launch_facts_are_discoverable_through_the_context_pipeline(
        launch_store, state_store):
    """Both launch records arrive, in their own sections, via real pipeline."""
    from app.context import build_context
    from app.retrieval.models import RetrievalResult

    factual = _retrieve_category(launch_store, "in_progress_projects")
    positioning = _retrieve_category(launch_store, "public_positioning")

    combined = RetrievalResult(
        query="Abu Prompt", strategy="metadata",
        documents=[*factual.documents, *positioning.documents],
        diagnostics={"k_requested": len(factual.documents) + len(positioning.documents)},
    )
    context = build_context(combined, store=state_store)

    factual_sources = {
        item.source for item in context.section("in_progress_projects").items
    }
    assert "in_progress_projects/personal_branding_agent.md" in factual_sources

    guidance_sources = {
        item.source for item in context.section("public_positioning").items
    }
    assert "public_positioning/abu_prompt.md" in guidance_sources

    # Evidence/positioning separation holds: positioning is guidance, never
    # evidence, so it cannot become proof for a post on its own.
    assert context.coverage.evidence_item_count >= 1
    evidence_sources = {item.source for item in context.evidence_items()}
    assert "public_positioning/abu_prompt.md" not in evidence_sources

    # Identity + milestone + future-plan wording is present in the assembled
    # material (not just on disk).
    texts = [item.content for item in context.section("in_progress_projects").items]
    texts += [item.content for item in context.section("public_positioning").items]
    blob = "\n".join(texts)
    assert "@AbuPrompt" in blob
    assert "Abu Prompt" in blob
    assert "first public introduction" in blob
    assert "no launch post has been published" in blob.lower()
    assert "planned, not implemented" in blob.lower()


def test_agent_decision_policy_is_unchanged():
    """PUBLISH still cannot be built without a passing verification."""
    from app.agent.enums import AgentDecision
    from app.agent.models import AgentResult
    from app.verification.enums import Severity, VerificationOutcome, ViolationKind
    from app.verification.models import VerificationResult, Violation

    refused = VerificationResult(
        outcome=VerificationOutcome.REJECTED,
        violations=(
            Violation(
                kind=ViolationKind.CITATION_NOT_IN_CONTEXT,
                severity=Severity.REJECT,
                detail="cites evidence the context does not hold",
            ),
        ),
    )
    with pytest.raises((ValueError, TypeError)):
        AgentResult(decision=AgentDecision.PUBLISH, verification=refused)

    from app.publishing.service import MAX_PUBLISHES_PER_RUN
    assert MAX_PUBLISHES_PER_RUN == 1

    from app.workflows.branding import BRANDING_PHASES
    assert BRANDING_PHASES == ("context", "decide", "publish")


def test_no_special_launch_publish_path_exists():
    """No launch-specific logic anywhere in the application code."""
    py_files = sorted(APP_ROOT.rglob("*.py"))
    assert py_files, "expected application modules under app/"

    forbidden = ("abuprompt", "abu_prompt", "أبو برومبت")
    offenders = [
        path for path in py_files
        if any(
            token in path.read_text(encoding="utf-8").lower()
            for token in forbidden
        )
    ]
    assert not offenders, (
        f"launch-specific logic found in app code: "
        f"{[p.relative_to(PROJECT_ROOT).as_posix() for p in offenders]}"
    )

    # The decision/publish layers must not branch on a launch either. The
    # check names launch-post phrases rather than the bare word "launch",
    # which pre-exists as ordinary verification vocabulary
    # (app/verification/policy.py matches "launched|launching" as claim verbs).
    launch_phrases = ("launch post", "launch milestone", "first public introduction")
    launch_hits = []
    for sub in ("agent", "workflows", "publishing", "generation", "verification"):
        for path in (APP_ROOT / sub).rglob("*.py"):
            text = path.read_text(encoding="utf-8").lower()
            if any(phrase in text for phrase in launch_phrases):
                launch_hits.append(path.relative_to(PROJECT_ROOT).as_posix())
    assert not launch_hits, f"launch branching in decision/publish layers: {launch_hits}"
