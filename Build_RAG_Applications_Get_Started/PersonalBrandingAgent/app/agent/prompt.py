"""What the Agent is asked, and how its answer is read back.

Same two jobs as :mod:`app.generation.prompt` and
:mod:`app.verification.judge`, and the same three properties, because the
Agent's reasoning call is a model call like any other in this system:

**The prompt is blocks, not a concatenation.** ``PLAN.md`` Step 8 forbids one
undifferentiated prompt, and the reason applies here with more force: a
reasoner told *"here are the opportunities, here is the evidence, here is what
has already been published"* in one run of text cannot tell which of the three
it is allowed to choose from. As separate named blocks, the separation is a
property of a value a test asserts on, not of a string nobody diffs.

**Everything offered is derived from the context.** Opportunities are the
context's own non-empty evidence sections; evidence options are the context's
own items, labelled ``E1``…``En`` in the context's own order. Nothing here
reads retrieval, the store, a clock or the environment, so two runs over the
same context offer a model exactly the same choices — which is what makes a
reproducible decision possible at all.

**The answer is read strictly and resolved elsewhere.** :func:`parse_reasoning_answer`
is forgiving about a code fence and strict about everything else, because a
model's answer that cannot be read is not a proposal. What it returns is still
*raw* — labels and a topic the model named — and it is
:meth:`app.agent.agent.BrandingAgent._proposal_from` that resolves them
against the request and refuses what does not exist. Splitting those two is
what keeps "the Agent cannot invent a source" checkable: the parser can never
make an invented label real, and the resolver never trusts one.
"""
import json
import re
from dataclasses import dataclass
from typing import ClassVar

from app.agent.errors import ReasoningUnavailable
from app.agent.models import (
    EvidenceOption,
    HistoryDigest,
    ReasoningAnswer,
    ReasoningRequest,
    TopicCandidate,
)
from app.context.models import PersonalBrandingContext
from app.generation.prompt import NO_STATE_LABEL, PROHIBITED_CLAIMS

__all__ = [
    "AGENT_PROMPT_VERSION",
    "ReasoningPrompt",
    "build_reasoning_prompt",
    "evidence_options",
    "parse_reasoning_answer",
    "topic_candidates",
]

#: Bumped whenever the wording or the structure below changes in a way that
#: would produce a different decision from the same context. It travels with
#: every proposal, so a decision that reads oddly months from now can be traced
#: to the prompt that produced it instead of being explained by whatever the
#: prompt says today. The same convention as ``PROMPT_VERSION`` (Step 8) and
#: ``JUDGE_PROMPT_VERSION`` (Step 9).
AGENT_PROMPT_VERSION = "branding-agent-v1"

#: How many already-published rows of each kind the prompt lists. Bounded so a
#: long history cannot make a prompt grow without limit; the digest itself is
#: already bounded by the read service's own limits.
HISTORY_LINES = 10

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _prohibited_phrase(claims: tuple[str, ...] = PROHIBITED_CLAIMS) -> str:
    """``a, b, or c`` — the same construction
    :func:`app.generation.prompt._prohibited_phrase` uses, restated here so
    this module is built from the corpus's list without importing a private
    helper out of another layer."""
    if not claims:
        return ""
    if len(claims) == 1:
        return claims[0]
    return ", ".join(claims[:-1]) + f", or {claims[-1]}"


INSTRUCTIONS = (
    "You choose what a software engineer should write about on LinkedIn "
    "today, from the material they actually have. You do not write the post; "
    "a separate writer does that from the evidence you select.\n"
    "\n"
    "These rules are absolute:\n"
    "1. Choose the topic from the OPPORTUNITIES section and nothing else. "
    "Each opportunity is a section of the material that was actually "
    "retrieved. If none of them is worth publishing about, decline.\n"
    "2. Select evidence only by its label from the EVIDENCE section, and "
    "never name a label that is not listed there. You may not invent a "
    "source, a chunk, a project, a metric, a date, or a citation.\n"
    f"3. The angle you choose must not imply {_prohibited_phrase()} that the "
    "supplied evidence does not support. An angle is a framing, not a fact.\n"
    "4. ALREADY PUBLISHED is what the person's audience has recently seen. "
    "It is not evidence and never a source of facts — use it only to avoid "
    "repeating yourself.\n"
    "5. Say less rather than more. Declining is a normal, correct answer, and "
    "publishing something thin is worse than publishing nothing.\n"
    "\n"
    "Answer with a single JSON object and nothing else — no prose around it, "
    "no code fence:\n"
    '{"publish": true, "topic": "<one of the OPPORTUNITIES names>", '
    '"angle": "<one short sentence>", "project": "<the project, or empty>", '
    '"evidence": ["E1", "E2"], "strategy": "<a listed retrieval strategy>", '
    '"rationale": "<why this is worth publishing>", "decline_reason": ""}\n'
    'Set "publish" to false, leave "topic" and "evidence" empty, and explain '
    'why in "decline_reason" when there is nothing worth publishing.'
)
"""The system message: role, the absolute grounding rules, and the output
shape. Separate from the material so that a prohibition is never something the
caller's context could push out of the prompt — the same reasoning Step 8
records for generation."""


# ------------------------------------------------- what there is to choose ---

def topic_candidates(context: PersonalBrandingContext
                     ) -> tuple[TopicCandidate, ...]:
    """The content opportunities this context actually holds.

    One per **non-empty evidence section**, in the context's own section order
    — which is the corpus's hierarchy rank, so the strongest material is
    offered first and an empty section is not offered at all. This is the
    Agent's vocabulary of topics, and it is derived rather than invented: a
    section exists because retrieval returned documents that belong to it.

    Guidance sections are deliberately absent. A writing-style document is not
    something to publish *about*, and offering it would invite exactly the
    confusion Step 4's separation of evidence from guidance exists to prevent.
    """
    return tuple(
        TopicCandidate(
            name=section.name,
            item_count=len(section.items),
            evidence_states=section.coverage.evidence_states_present,
        )
        for section in context.evidence_sections
        if section.items
    )


def evidence_options(context: PersonalBrandingContext
                     ) -> tuple[EvidenceOption, ...]:
    """Every piece of evidence in the context, under the label it is offered by.

    Labels are assigned by position over
    ``PersonalBrandingContext.evidence_items()`` order — section order, then
    the context's own in-section order — so they are a property of the context
    and not of the order a retriever happened to return things in. Identical in
    construction to :func:`app.generation.prompt.build_prompt`'s citations,
    which is what lets a selection made here resolve against the same list
    generation will later build.
    """
    options: list[EvidenceOption] = []
    for section in context.evidence_sections:
        for item in section.items:
            options.append(EvidenceOption(
                label=f"E{len(options) + 1}",
                source=item.source,
                chunk_id=item.chunk_id,
                evidence_state=item.evidence_state,
                section=section.name,
                category=item.category,
            ))
    return tuple(options)


# ---------------------------------------------------------- the prompt value ---

@dataclass(frozen=True)
class ReasoningPrompt:
    """An assembled reasoning prompt, as separate named blocks.

    Same shape as :class:`app.generation.models.GenerationPrompt`, and for the
    same reason: the parts are *fields*, so a test can assert which block holds
    what without asserting on wording. Rendering is deterministic — same
    request, same bytes — because the blocks come from ordered tuples and
    nothing here reads a clock or the environment.
    """

    version: str
    instructions: str
    opportunities_block: str = ""
    evidence_block: str = ""
    history_block: str = ""
    strategies_block: str = ""

    options: tuple[EvidenceOption, ...] = ()
    """The labels the evidence block actually lists, in the order it lists
    them. This is the set a model's answer is resolved against, so "the Agent
    selected only evidence it was given" is a structural property of the value
    rather than a promise about the model."""

    topics: tuple[TopicCandidate, ...] = ()
    """The names the opportunities block actually offers, for the same
    reason."""

    #: Section headers, in render order. Public because a test asserting the
    #: separation should name the same headers a model reads.
    SECTION_TITLES: ClassVar[tuple[tuple[str, str], ...]] = (
        ("opportunities_block", "OPPORTUNITIES"),
        ("evidence_block", "EVIDENCE"),
        ("history_block", "ALREADY PUBLISHED"),
        ("strategies_block", "RETRIEVAL STRATEGIES"),
    )

    @property
    def has_evidence(self) -> bool:
        """True when the prompt lists evidence at all. Derived from
        ``options``, so it cannot disagree with what a model would read."""
        return bool(self.options)

    @property
    def topic_names(self) -> tuple[str, ...]:
        return tuple(topic.name for topic in self.topics)

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(option.label for option in self.options)

    @property
    def blocks(self) -> tuple[tuple[str, str], ...]:
        """The non-empty blocks, as ``(title, text)``, in render order."""
        return tuple(
            (title, getattr(self, name))
            for name, title in self.SECTION_TITLES
            if getattr(self, name)
        )

    def body(self) -> str:
        """The user message: labelled blocks, one after another."""
        return "\n\n".join(f"## {title}\n{text}" for title, text in self.blocks)

    def messages(self) -> tuple[dict[str, str], ...]:
        """The prompt as chat messages, ready for any OpenAI-compatible client.

        Plain dicts rather than framework message objects, so the seam a test
        records is the same seam a real client receives.
        """
        return (
            {"role": "system", "content": self.instructions},
            {"role": "user", "content": self.body()},
        )

    def render(self) -> str:
        """The whole prompt as one string, for logging and assertions."""
        return f"{self.instructions}\n\n{self.body()}"


def build_reasoning_prompt(request: ReasoningRequest, *,
                           version: str = AGENT_PROMPT_VERSION
                           ) -> ReasoningPrompt:
    """Assemble the deterministic reasoning prompt for one request.

    Nothing is looked up and nothing is inferred: every block is rendered from
    values the request already carries, so building a prompt twice produces the
    same bytes and a test can assert on the structure without a model.
    """
    return ReasoningPrompt(
        version=version,
        instructions=INSTRUCTIONS,
        opportunities_block=_opportunities_block(request.topics),
        evidence_block=_evidence_block(request.evidence),
        history_block=_history_block(request.history),
        strategies_block=_strategies_block(request.strategies),
        options=request.evidence,
        topics=request.topics,
    )


# ------------------------------------------------------------------ blocks ---

def _opportunities_block(topics: tuple[TopicCandidate, ...]) -> str:
    if not topics:
        return ""
    lines = [
        f"- {topic.name}: {topic.item_count} item(s)"
        + (
            ", evidence states: " + ", ".join(sorted(topic.evidence_states))
            if topic.evidence_states else ", no declared evidence state"
        )
        for topic in topics
    ]
    return (
        "Sections of the retrieved material. Choose exactly one by name, or "
        "decline.\n" + "\n".join(lines)
    )


def _evidence_block(options: tuple[EvidenceOption, ...]) -> str:
    if not options:
        return ""
    lines = [
        f"[{option.label}] source: {option.source} "
        f"(chunk {option.chunk_id}, section {option.section}, "
        f"category {option.category or 'none'}, "
        f"evidence state: {option.evidence_state or NO_STATE_LABEL})"
        for option in options
    ]
    return (
        "The only evidence that exists. Select by label; never name a label "
        "that is not here.\n" + "\n".join(lines)
    )


def _history_block(history: HistoryDigest) -> str:
    """What the audience has recently seen — as context, never as evidence.

    Rendered from the digest's own rows, in the order the read service
    returned them, which is already deterministic (count descending, then
    value) so two runs over the same store render the same block.
    """
    lines: list[str] = []
    if history.topics:
        lines.append("Recently covered topics: " + ", ".join(
            f"{row.value} ({row.uses})" for row in history.topics[:HISTORY_LINES]
        ))
    if history.projects:
        lines.append("Recently covered projects: " + ", ".join(
            f"{row.value} ({row.uses})"
            for row in history.projects[:HISTORY_LINES]
        ))
    if history.evidence:
        lines.append("Recently reused evidence: " + ", ".join(
            f"{row.source_path} ({row.uses})"
            for row in history.evidence[:HISTORY_LINES]
        ))
    if history.publications:
        lines.append(
            f"Publications so far: {len(history.publications)}"
        )
    if history.unresolved_ambiguity:
        lines.append(
            f"Attempts whose outcome is still unknown: "
            f"{len(history.requires_review)}"
        )
    if not lines:
        return "Nothing has been published yet."
    return (
        "Not evidence, and never a source of facts. Use it only to avoid "
        "repeating what the audience has already seen.\n" + "\n".join(lines)
    )


def _strategies_block(strategies: tuple[str, ...]) -> str:
    if not strategies:
        return ""
    return (
        "Retrieval strategies available for a fresh pass at the chosen topic. "
        "Choose one by name, or leave it empty to reuse the current one.\n"
        + "\n".join(f"- {name}" for name in strategies)
    )


# ------------------------------------------------------------- the answer ---

def parse_reasoning_answer(text: str) -> ReasoningAnswer:
    """The answer in a model's reply.

    Strict about the shape and forgiving about the wrapping, because asking a
    model for bare JSON reliably produces JSON in a code fence — the same rule
    :func:`app.verification.judge.parse_judgement` applies to the advisory
    judge.

    What is *not* checked here is whether the answer makes sense: a topic that
    is not an opportunity, a label that does not exist, a publish with no
    evidence. Those are resolution failures, and they are refused by
    :meth:`app.agent.agent.BrandingAgent._proposal_from` as
    :class:`~app.agent.errors.UnusableReasoningAnswer` — a different fact about
    a run from "nobody could read the answer".

    Raises:
        ReasoningUnavailable: the reply is not the required shape — not JSON,
            not an object, or missing the one boolean the decision rests on.
            In every case the Agent has no answer, which is ``DO_NOT_PUBLISH``.
    """
    match = _JSON_BLOCK.search(text or "")
    if not match:
        raise ReasoningUnavailable(
            "the branding agent did not answer with JSON"
        )
    try:
        payload = json.loads(match.group(0))
    except ValueError as exc:
        raise ReasoningUnavailable(
            f"the branding agent's answer was not valid JSON: "
            f"{type(exc).__name__}"
        ) from exc

    if not isinstance(payload, dict):
        raise ReasoningUnavailable(
            "the branding agent's answer was not a JSON object"
        )

    publish = payload.get("publish")
    if not isinstance(publish, bool):
        raise ReasoningUnavailable(
            "the branding agent's answer carried no boolean 'publish'"
        )

    labels = payload.get("evidence", [])
    if not isinstance(labels, list) or not all(
        isinstance(label, str) for label in labels
    ):
        raise ReasoningUnavailable(
            "the branding agent's answer listed evidence that is not a list "
            "of labels"
        )

    return ReasoningAnswer(
        publish=publish,
        topic=_optional_text(payload.get("topic")),
        angle=_optional_text(payload.get("angle")),
        project=_optional_text(payload.get("project")),
        evidence_labels=tuple(label.strip() for label in labels if label.strip()),
        strategy=_optional_text(payload.get("strategy")),
        rationale=_text(payload.get("rationale")),
        decline_reason=_text(payload.get("decline_reason")),
    )


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _optional_text(value: object) -> str | None:
    """A label the model may leave empty. Empty means *absent*, not *blank*:
    ``GenerationRequest`` refuses a blank label, and rightly — a blank one is
    either a mistake or an absence, and calling it an absence is the honest
    reading."""
    text = _text(value)
    return text or None
