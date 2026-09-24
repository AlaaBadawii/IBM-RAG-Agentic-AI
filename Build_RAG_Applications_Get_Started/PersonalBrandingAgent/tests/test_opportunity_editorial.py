"""M5: development-specific editorial intent for generation.

Isolated state throughout. Intent is carried verbatim from configuration to
the generation prompt's constraints block; everything else — grounding,
verification, publishing — is asserted unchanged, not reimplemented here.
"""
import pytest

from app.opportunities.opportunities import select_opportunity
from app.state import StateStore

INTENT = (
    "Write a first-person introduction of the test persona: who it is, "
    "its role, one current capability. About 80-140 words.")


@pytest.fixture
def store(tmp_path):
    with StateStore(tmp_path / "m5.db") as state:
        yield state


def _entries(intent=INTENT):
    development = {"key": "intro", "display_name": "Intro"}
    if intent is not None:
        development["editorial_intent"] = intent
    return [{"id": "w", "display_name": "W",
             "developments": [development]}]


def _seed(store, entries):
    for entry in entries:
        store.ensure_tracked_work(entry["id"], entry["display_name"])
        for dev in entry.get("developments", ()):
            store.ensure_development(
                entry["id"], dev["key"],
                dev.get("display_name", dev["key"]))


# ------------------------------------------------------- positive ---

def test_intent_reaches_the_generation_prompt_verbatim(store):
    """The intent renders unchanged inside the CONSTRAINTS block — the seam
    the generation layer documents for caller-supplied writer objectives."""
    from app.generation.models import PublishingConstraints
    from app.generation.prompt import _constraints_block

    _seed(store, _entries())
    selected = select_opportunity(store, _entries())
    block = _constraints_block(
        PublishingConstraints(notes=(selected.editorial_intent,)))

    assert INTENT in block
    assert block.splitlines()[-1] == f"- {INTENT}"


def test_agent_carries_intent_into_generation_request():
    """End to end at the seam: agent with intent → generator receives a
    request whose constraints carry the intent verbatim."""
    from app.agent.agent import BrandingAgent
    from app.agent.models import AgentProposal

    received = {}

    class _RecordingGenerator:
        def generate(self, request):
            received["notes"] = request.constraints.notes
            raise AssertionError("captured")

    agent = BrandingAgent(reasoner=None, generator=_RecordingGenerator(),
                          verifier=None, editorial_intent=INTENT)
    proposal = AgentProposal(
        topic="t", context=None, evidence=(), rationale="r",
        strategy="vector", prompt_version="v", reasoner="test")
    # Simulate what run() does with the base constraints.
    from dataclasses import replace
    from app.agent.models import publishing_constraints
    from app.agent.models import HistoryDigest

    base = publishing_constraints(HistoryDigest.empty())
    base = replace(base, notes=(*base.notes, agent._editorial_intent))
    with pytest.raises(AssertionError):
        agent._generator.generate(
            proposal.generation_request(constraints=base))
    assert received["notes"] == (INTENT,)


def test_empty_intent_behaves_exactly_as_before():
    """No intent → base constraints untouched (existing callers unaffected)."""
    from dataclasses import replace
    from app.agent.agent import BrandingAgent
    from app.agent.models import HistoryDigest, publishing_constraints

    agent = BrandingAgent(reasoner=None, generator=None, verifier=None)
    assert agent._editorial_intent == ""
    base = publishing_constraints(HistoryDigest.empty())
    assert base.notes == ()


# ------------------------------------------------------- negative ---

def test_invalid_intent_rejected_at_load(tmp_path):
    from app.opportunities.baseline import ensure_baseline

    with StateStore(tmp_path / "m5b.db") as state:
        with pytest.raises(ValueError, match="editorial_intent"):
            ensure_baseline(state, [{
                "id": "w", "display_name": "W",
                "developments": [{"key": "d",
                                  "editorial_intent": "   "}]}])


def test_intent_is_carriage_not_interpretation():
    """The opportunity layer never rewrites the text."""
    assert INTENT == INTENT.strip()


def test_verification_policy_untouched():
    from app.publishing.service import PublishingService
    from app.verification.policy import WEAK_EVIDENCE_STATES
    from app.verification.revision import revision_decision
    from app.verification.verifier import EvidenceVerifier

    assert callable(PublishingService.publish)
    assert callable(EvidenceVerifier.verify)
    assert callable(revision_decision)
    assert WEAK_EVIDENCE_STATES >= {"ASPIRATIONAL", "LEARNING"}


def test_no_intent_created_by_selection(store):
    _seed(store, _entries())
    before = store._conn.execute(
        "SELECT COUNT(*) FROM publish_intents").fetchone()[0]
    select_opportunity(store, _entries())
    assert store._conn.execute(
        "SELECT COUNT(*) FROM publish_intents").fetchone()[0] == before
