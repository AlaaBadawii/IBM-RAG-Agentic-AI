"""M6: the LinkedIn writing contract and first-publication safety.

Isolated state throughout. Voice and structure are asserted on the
contract text itself (deterministic); grounding and publishing authority
are asserted on the unchanged machinery. Model output quality is proven
by the live dry run, not by fakes.
"""
import pytest

from app.generation.prompt import INSTRUCTIONS
from app.generation.voice import LINKEDIN_CONTRACT
from app.state import RunOutcome, StateStore


@pytest.fixture
def store(tmp_path):
    with StateStore(tmp_path / "m6.db") as state:
        yield state


# ------------------------------------------------------- voice ---

def test_contract_reaches_the_writer():
    assert LINKEDIN_CONTRACT in INSTRUCTIONS


def test_contract_demands_first_person_voice():
    assert "first person" in LINKEDIN_CONTRACT


def test_contract_demands_direct_opening():
    assert "first 1-2 lines" in LINKEDIN_CONTRACT
    assert "excited to announce" in LINKEDIN_CONTRACT


def test_contract_demands_one_idea_shown_not_inventoried():
    assert "one development, one clear story" in LINKEDIN_CONTRACT
    assert "do not inventory" in LINKEDIN_CONTRACT or \
        "inventory architectures" in LINKEDIN_CONTRACT


def test_contract_marks_current_vs_future():
    assert "Planned" in LINKEDIN_CONTRACT
    assert "Never present planned functionality as implemented" in \
        LINKEDIN_CONTRACT


def test_contract_bounds_length():
    assert "120-220" in LINKEDIN_CONTRACT
    assert "Never pad" in LINKEDIN_CONTRACT


def test_contract_limits_formatting_and_bait():
    assert "hashtag spam" in LINKEDIN_CONTRACT
    assert "engagement bait" in LINKEDIN_CONTRACT
    assert "ALL CAPS" in LINKEDIN_CONTRACT
    assert "never fabricate a mention" in LINKEDIN_CONTRACT.lower()


def test_contract_names_no_project_or_post():
    """Reusable means reusable: no persona, post text, or repo internals."""
    for forbidden in ("Abu Prompt", "@AbuPrompt", "Step 14", "app/",
                      "DO_NOT_PUBLISH"):
        assert forbidden not in LINKEDIN_CONTRACT, forbidden


# ------------------------------------------------------- grounding ---

def test_grounding_rules_survive_the_contract():
    for claim in ("projects", "metrics", "certificates"):
        assert claim in INSTRUCTIONS
    assert "only source of facts" in INSTRUCTIONS


def test_comment_response_cannot_pass_as_current():
    """Planned mention-triggered interaction described as live must fail
    verification against evidence that documents it as planned."""
    from app.verification.policy import _HEDGED_CLAIM

    assert _HEDGED_CLAIM.search("mention-triggered responses are future work")
    assert not _HEDGED_CLAIM.search(
        "mention-triggered responses are live today")


def test_unsupported_claims_still_rejected():
    from app.verification.errors import SupportJudgeUnavailable
    from app.verification.judge import parse_judgement

    with pytest.raises(SupportJudgeUnavailable):
        parse_judgement("looks great, publish it")


# ------------------------------------------------------- publishing ---

def test_normal_publishing_path_intact():
    from app.publishing.service import PublishingService
    from app.verification.verifier import EvidenceVerifier

    assert callable(PublishingService.publish)
    assert callable(EvidenceVerifier.verify)


def test_failed_publication_covers_nothing(store):
    from app.opportunities.opportunities import mark_development_published

    run = store.start_run("branding")
    intent = store.create_publish_intent(run.run_id, "post text here")
    store.mark_attempt_started(intent.intent_id)
    failed = store.record_publication(intent.intent_id, "failed")
    store.finish_run(run.run_id, RunOutcome.DO_NOT_PUBLISH)
    store.ensure_tracked_work("w", "W")
    store.ensure_development("w", "d", "D")

    with pytest.raises(ValueError, match="not published"):
        mark_development_published(store, "w", "d", failed.publication_id)

    assert store.get_development("w", "d").covered is False


def test_no_intent_created_by_contract_or_selection(store):
    from app.opportunities.opportunities import select_opportunity

    store.ensure_tracked_work("w", "W")
    store.ensure_development("w", "d", "D")
    before = store._conn.execute(
        "SELECT COUNT(*) FROM publish_intents").fetchone()[0]
    select_opportunity(store, [{"id": "w", "display_name": "W",
                                "developments": [{"key": "d"}]}])
    assert "first person" in INSTRUCTIONS
    assert store._conn.execute(
        "SELECT COUNT(*) FROM publish_intents").fetchone()[0] == before
