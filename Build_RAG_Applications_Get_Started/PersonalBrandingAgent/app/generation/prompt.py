"""Deterministic prompt assembly for grounded post generation (Step 8).

This module turns a :class:`~app.generation.models.GenerationRequest` into a
:class:`~app.generation.models.GenerationPrompt` — a value whose parts are
separate fields — and it is the only place where the wording of a generation
prompt exists.

Three properties it has to have, and why each is structural rather than
stylistic:

**Evidence and guidance never mix.** The prompt's evidence block is built from
``context.evidence_items()`` and nothing else; the guidance block from
``context.guidance_items()`` and nothing else. The context layer already
separated them into different fields (``PLAN.md`` Step 4), and this is where
that separation is spent: a model reading a labelled ``EVIDENCE`` section and a
labelled ``COMMUNICATION GUIDANCE`` section is being told which of the two it
may claim as fact. Merging them here would undo Step 4 for the one consumer
that matters most.

**The prohibitions are constant, and derived from one list.** Every prompt
carries the same rules — never invent what the evidence does not support,
never present guidance as achievement, never describe coursework as
professional experience. :data:`PROHIBITED_CLAIMS` is the single source of the
enumerated ones, so the sentence a model reads and the list a test checks
cannot drift apart.

**Assembly is deterministic.** Same request, same bytes: the blocks come from
ordered tuples, the labels are assigned by position, and nothing reads a clock,
a random source, the environment, or the retrieval order. That is what lets a
test assert on the prompt at all — otherwise every assertion would be about one
run of one process.

Nothing here calls a model. :mod:`app.generation.generator` does that.
"""
from app.context.models import ContextItem, ContextSection
from app.generation.models import (
    EvidenceCitation,
    GenerationPrompt,
    GenerationRequest,
    PublishingConstraints,
)
from app.generation.voice import LINKEDIN_CONTRACT

__all__ = [
    "PROHIBITED_CLAIMS",
    "PROMPT_VERSION",
    "build_prompt",
    "selected_evidence",
]

#: Bumped whenever the wording or the structure below changes in a way that
#: would produce a different post from the same context. It travels with every
#: draft (``GenerationMetadata.prompt_version``), so a post that reads oddly six
#: months from now can be traced to the prompt that produced it instead of
#: being explained by whatever the prompt says today.
PROMPT_VERSION = "grounded-post-v2"

#: The claims a post must never contain unless the supplied evidence supports
#: them. Named here as a tuple so the rule can be *generated* into the
#: instructions and *checked* by a test against the same source — the corpus's
#: own audit policy names these categories (``data/audit/README.md``), and a
#: hand-written sentence is a second copy free to fall out of step with it.
PROHIBITED_CLAIMS = (
    "projects",
    "achievements",
    "technologies",
    "metrics",
    "dates",
    "certificates",
    "experiences",
    "claims",
)

#: How a missing ``evidence_state`` reads to a model. The context layer keeps
#: ``None`` as ``None`` rather than guessing a state, and this is the prompt's
#: way of saying the same thing: not a state, an absence of one.
NO_STATE_LABEL = "none declared"


def _prohibited_phrase(claims: tuple[str, ...] = PROHIBITED_CLAIMS) -> str:
    """``a, b, or c`` — so the sentence reads as English and stays generated."""
    if len(claims) == 1:
        return claims[0]
    return ", ".join(claims[:-1]) + f", or {claims[-1]}"


INSTRUCTIONS = (
    "You write one LinkedIn post for the person described by the context "
    "below, in the first person.\n"
    "\n"
    "These rules are absolute:\n"
    f"1. The EVIDENCE section is the only source of facts. Never invent "
    f"{_prohibited_phrase()} that are not supported by the supplied context. "
    f"If a claim is not supported there, do not make it.\n"
    "2. The COMMUNICATION GUIDANCE section shapes how the post is written — "
    "its voice, its positioning, its framing. It is not evidence: nothing in "
    "it may be presented as an achievement, a fact about the person's work, "
    "or support for a claim.\n"
    "3. Do not describe a course, an exercise, or a learning project as "
    "professional experience, and do not describe a local or practice project "
    "as a production system.\n"
    "4. Cite the labels of the evidence you actually used, and never cite a "
    "label that is not listed in the EVIDENCE section.\n"
    "5. Say less rather than more. If the evidence does not support a post "
    "worth publishing, decline.\n"
    "\n"
    "Answer with a single JSON object and nothing else — no prose around it, "
    "no code fence:\n"
    '{"post": "<the post text>", "evidence_used": ["E1", "E2"], '
    '"declined": false, "reason": "<short explanation>"}\n'
    'Set "declined" to true, leave "post" empty, and explain why in "reason" '
    "when the evidence does not support a post."
    "\n"
    + LINKEDIN_CONTRACT
)
"""The system message. Constant, and carrying the rules above it in this
module's docstring as well as here — the enumerated prohibition is generated
from :data:`PROHIBITED_CLAIMS` so the two cannot disagree."""


def selected_evidence(request: GenerationRequest) -> tuple[ContextItem, ...]:
    """The context items this request asks to write from, in context order.

    ``None`` means *all of them* — not *none of them*. A caller that wants no
    evidence is asking for a decline, and it gets one; a caller that wants to
    write from a subset gets that subset in the context's own deterministic
    order, because reorderable input would make the prompt a function of how
    the caller happened to build a tuple.

    Raises:
        ValueError: the request names an item this context does not contain.
            Selection is the Agent's job (``PLAN.md`` Step 10), and material
            that the assembly layer never placed is not evidence this layer
            may write from — refusing loudly is the difference between "the
            Agent chose badly" and "generation invented a source".
    """
    declared = request.context.evidence_items()
    if request.evidence is None:
        return declared

    allowed = {(item.source, item.chunk_id) for item in declared}
    unknown = [
        item for item in request.evidence
        if (item.source, item.chunk_id) not in allowed
    ]
    if unknown:
        raise ValueError(
            "generation was given evidence that is not in the supplied "
            "context: " + ", ".join(f"{item.source}" for item in unknown)
        )

    # Deduplicate by identity, keeping the context's order rather than the
    # caller's: the same item offered twice is one piece of evidence, and the
    # prompt's labels must not depend on how a caller built a tuple.
    selected = {(item.source, item.chunk_id) for item in request.evidence}
    return tuple(
        item for item in declared
        if (item.source, item.chunk_id) in selected
    )


def build_prompt(request: GenerationRequest, *,
                 version: str = PROMPT_VERSION) -> GenerationPrompt:
    """Assemble the prompt for one request. Pure, total, and deterministic.

    Total on purpose: a request whose context holds no evidence yields a
    prompt whose ``evidence_block`` is empty and whose
    :attr:`~app.generation.models.GenerationPrompt.has_evidence` is ``False``.
    Deciding to decline is
    :meth:`~app.generation.generator.PostGenerator.generate`'s job, and it
    happens *before* anything is sent — but keeping this function total is
    what lets a test assert on the empty case at all.
    """
    evidence = selected_evidence(request)
    citations = tuple(
        EvidenceCitation.from_item(f"E{index}", item)
        for index, item in enumerate(evidence, start=1)
    )
    return GenerationPrompt(
        version=version,
        instructions=INSTRUCTIONS,
        task_block=_task_block(request),
        evidence_block=_evidence_block(evidence, citations),
        guidance_block=_guidance_block(request.context.guidance_sections),
        constraints_block=_constraints_block(request.constraints),
        citations=citations,
    )


def _task_block(request: GenerationRequest) -> str:
    """What to write about. Instructions, never evidence.

    The topic, angle and project are the caller's decisions about *what to
    cover*, and none of them is checked against the evidence — that check is
    Step 9's, over the draft. Placing them here rather than in the evidence
    block is what keeps a caller's label from reading as a supported fact.
    """
    lines = ["Write one post."]
    if request.topic:
        lines.append(f"Topic: {request.topic}")
    if request.angle:
        lines.append(f"Angle: {request.angle}")
    if request.project:
        lines.append(f"Project: {request.project}")
    return "\n".join(lines)


def _evidence_block(evidence: tuple[ContextItem, ...],
                    citations: tuple[EvidenceCitation, ...]) -> str:
    """The labelled evidence. The only block a factual claim may come from.

    Content is the chunk exactly as it was stored — this layer does not
    summarise, truncate or merge it. The moment it does, a verifier is
    checking a claim against this layer's prose instead of against the corpus,
    and the ``chunk_id`` next to it no longer identifies what was read.
    """
    if not evidence:
        return ""
    blocks = []
    for citation, item in zip(citations, evidence):
        state = item.evidence_state or NO_STATE_LABEL
        header = (
            f"[{citation.label}] source: {item.source} "
            f"| chunk: {item.chunk_id} | evidence state: {state}"
        )
        blocks.append(f"{header}\n{item.content.strip()}")
    return "\n\n".join(blocks)


def _guidance_block(sections: tuple[ContextSection, ...]) -> str:
    """Voice, positioning and vision — clearly marked as not-evidence.

    Every item keeps its section name and its source, so a model can be told
    *"follow the style in ``writing_style``"* and a reader later can check
    which file was meant.
    """
    blocks = []
    for section in sections:
        if not section.items:
            continue
        lines = [f"### {section.name}"]
        for item in section.items:
            lines.append(f"(source: {item.source})")
            lines.append(item.content.strip())
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _constraints_block(constraints: PublishingConstraints) -> str:
    """What the audience has already seen.

    Omitted entirely when there is nothing to say, rather than rendered as an
    empty section: a header with no content invites a model to fill it.
    """
    if constraints.is_empty:
        return ""
    lines = ["Already published, so avoid repeating it:"]
    if constraints.recent_topics:
        lines.append(f"- topics: {', '.join(constraints.recent_topics)}")
    if constraints.recent_projects:
        lines.append(f"- projects: {', '.join(constraints.recent_projects)}")
    if constraints.recent_angles:
        lines.append(f"- angles: {', '.join(constraints.recent_angles)}")
    lines.extend(f"- {note}" for note in constraints.notes)
    return "\n".join(lines)
