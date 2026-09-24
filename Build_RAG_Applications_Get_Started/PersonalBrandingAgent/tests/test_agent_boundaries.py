"""Step 10: what the agent package is structurally unable to do.

``PLAN.md`` Step 10 states the Agent's boundaries as prohibitions — it *"must
not write to SQLite or publishing state"*, must not *"bypass state rules,
evidence gates, duplicate rules, max-post limits, or publication safeguards"*,
and must read history *"through the Step 6 read service — never by querying the
store directly"*.

Asserted here as import scans rather than as behaviour, for the reason Step 8
and Step 9 give about their own packages: *"this module cannot reach a store"
is a property that cannot silently regress, whereas "no test observed a write"
only proves that no test looked.* A behavioural test would have to remember to
check every path forever; an AST scan checks the only thing that matters, that
there is no path at all.
"""
import ast
from pathlib import Path

import pytest

from app.agent import PublicationHistoryReader
from app.publishing import PublishingHistory

AGENT_PACKAGE = Path(__file__).resolve().parents[1] / "app" / "agent"

#: Import roots the Agent must have no path to, and why each one is here.
#:
#: ``app.state`` / ``sqlite3``      the Agent writes no state, and recording is
#:                                  the workflow's, "or the system could
#:                                  forget to record" (``PLAN.md`` Step 10).
#: ``app.publishing.service``       the Agent proposes; it does not publish, and
#:                                  it must not be able to. The read *service*
#:                                  is a different module on purpose, and the
#:                                  Agent does not even import that — it is
#:                                  handed an object satisfying a protocol.
#: ``app.notify`` / ``smtplib``     the Agent exposes a failure; the workflow
#:                                  notifies (``PLAN.md`` Step 10).
#: ``app.retrieval`` / ``chroma``   selection is confined to what retrieval
#:                                  already returned. An Agent that can query
#:                                  the corpus can select evidence the context
#:                                  layer never placed.
#: ``app.ingestion`` / ``app.sync`` / ``app.sources``
#:                                  the knowledge layer, above this one.
#: ``app.integrations``             LinkedIn. Nothing here may send anything.
FORBIDDEN = (
    "chroma", "sqlite3", "smtplib", "requests", "httpx",
    "app.state", "app.publishing.service", "app.publishing.duplicates",
    "app.notify", "app.sync", "app.retrieval", "app.ingestion",
    "app.integrations", "app.sources",
)

#: Names that must not appear in the package's public surface. The Agent hands
#: a workflow values; it never hands it a way to act.
FORBIDDEN_EXPORTS = (
    "PublishingService", "StateStore", "NotificationService", "Retriever",
    "RetrievalEngine", "PostGenerator", "EvidenceVerifier", "publish_to_linkedin",
)


def _imported(module: Path) -> list[str]:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


AGENT_MODULES = sorted(AGENT_PACKAGE.glob("*.py"))


@pytest.mark.parametrize("module", AGENT_MODULES, ids=lambda path: path.name)
def test_the_agent_reaches_no_layer_it_must_not(module):
    """No store, no publisher, no transport, no corpus, no knowledge layer."""
    offenders = [
        name for name in _imported(module)
        if any(name == bad or name.startswith(f"{bad}.")
               for bad in FORBIDDEN)
    ]
    assert not offenders, f"{module.name} reaches a layer it must not: {offenders}"


@pytest.mark.parametrize("module", AGENT_MODULES, ids=lambda path: path.name)
def test_the_agent_can_only_reach_generation_verification_context_and_values(module):
    """The positive half of the same rule.

    Every ``app.*`` import in this package is accounted for here, so a new one
    is a deliberate act rather than something that slips in beside a change.
    ``app.publishing.models`` is values — ``UsageCount``, ``PublicationSummary``,
    ``EvidenceUsage`` — and carries no method that could touch a store.
    """
    allowed = (
        "app.agent", "app.context", "app.generation", "app.verification",
        "app.publishing.models", "app.logging_config", "app.errors",
        # Transport only: the Gemini JSON client carries prompts to the
        # pinned model and returns text. It holds no store, no publisher,
        # no corpus handle — the first test above already bars all of those.
        "app.gemini",
    )
    offenders = [
        name for name in _imported(module)
        if name.startswith("app.")
        and not any(name == good or name.startswith(f"{good}.")
                    for good in allowed)
    ]
    assert not offenders, (
        f"{module.name} imports a layer outside the Agent's remit: {offenders}"
    )


def test_the_agent_never_mentions_a_write_it_could_perform():
    """The Agent's only history access is the four read methods its protocol
    declares — asserted over the source, so a write added later is a failure
    here rather than something a test has to notice."""
    writes = (
        "create_publish_intent", "record_publication", "start_run",
        "save_", "insert", "commit(", "execute(",
    )
    for module in AGENT_MODULES:
        source = module.read_text(encoding="utf-8")
        for name in writes:
            assert name not in source, (
                f"{module.name} mentions {name!r}; the Agent writes nothing"
            )


def test_the_public_surface_exposes_no_way_to_act():
    """What a workflow gets back is values. There is no handle, no client and
    no service on the Agent's surface."""
    from app import agent

    for name in FORBIDDEN_EXPORTS:
        assert name not in agent.__all__, (
            f"app.agent exports {name!r}; the Agent proposes and stops"
        )


def test_publishing_history_is_a_read_service_by_contract():
    """The one thing the Agent is given about the store, and it reads only.

    ``PublishingHistory`` has no write method at all, so "the Agent cannot
    write publishing state" is a property of the object it was handed as well
    as of the code it runs.
    """
    surface = {
        name for name in dir(PublishingHistory) if not name.startswith("_")
    }
    assert surface == {
        "recent_publications", "requires_review", "unresolved_intents",
        "recent_topics", "recent_projects", "recent_evidence",
    }


def test_the_protocol_declares_only_the_read_methods_the_agent_uses():
    """The Agent's view of the read service, kept narrow on purpose: widening
    it is how a read-only boundary stops being one."""
    declared = {
        name for name in vars(PublicationHistoryReader)
        if not name.startswith("_")
    }
    assert declared == {
        "recent_publications", "requires_review", "recent_topics",
        "recent_projects", "recent_evidence",
    }


def test_the_agent_holds_no_state_between_runs():
    """A second run with the same inputs is the same run — nothing the first
    one did is remembered anywhere in the object. Eight collaborators and
    settings, and no accumulator of any kind."""
    from app.agent import BrandingAgent

    bare = BrandingAgent(reasoner=None, generator=None, verifier=None)

    assert set(vars(bare)) == {
        "_reasoner", "_generator", "_verifier", "_history", "_strategies",
        "_revision_limit", "_history_limit", "_prompt_version",
        "_editorial_intent",
    }
