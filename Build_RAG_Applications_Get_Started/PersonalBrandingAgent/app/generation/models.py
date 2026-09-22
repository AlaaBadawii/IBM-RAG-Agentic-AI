"""The shape of a generated post (``PLAN.md`` Step 8).

``PLAN.md`` requires a **structured result, not a bare string**. That is not
decoration: four different consumers need four different parts of it, and all
four would otherwise be re-deriving them from prose.

    the workflow      outcome, and the reason when there is no post
    the audit record  model id, prompt version, parameters
    Step 9            which evidence the draft claims to rest on
    Step 6            the same references, as ``source path + content hash``

Same rule as every other model module here: these carry a result, never
behaviour that touches the network. :mod:`app.generation.generator` decides;
a test can build any of these directly and assert on it without a model, an
API key, or a network call.

Two things are deliberately absent. There is no **quality score** — Step 9
owns verification, and a number invented here would be an unverified opinion
about a draft nothing has checked yet. There is no **publication state** —
generation writes nothing, and ``PLAN.md`` Step 8 is explicit that persistence
happens only at the publish step.
"""
from dataclasses import dataclass, field
from typing import Any, ClassVar, Mapping

from app.context.models import ContextItem, PersonalBrandingContext
from app.generation.enums import DeclineReason, GenerationOutcome

__all__ = [
    "EvidenceCitation",
    "GeneratedPost",
    "GenerationMetadata",
    "GenerationPrompt",
    "GenerationRequest",
    "GenerationResult",
    "PublishingConstraints",
]


@dataclass(frozen=True)
class PublishingConstraints:
    """What has already been published, as an input to this post.

    A plain value rather than ``PublishingHistory`` or a store row, for the
    same reason :class:`app.notify.models.PublishedPost` is: generation sits
    above the knowledge layer and beside the publishing layer, and neither is
    its to reach into. The caller — Step 10's Agent, through Step 6's read
    service — hands over exactly what a writer needs to avoid repeating
    itself, and nothing else about the history crosses the boundary.

    Nothing here is a rule about what *may* be published. The duplicate policy
    is enforced by Step 6 over stored state, because it has to hold whether or
    not a model chose to respect it. These are writing constraints: what the
    person reading the post has already seen.
    """

    recent_topics: tuple[str, ...] = ()
    recent_projects: tuple[str, ...] = ()
    recent_angles: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    """Free-form constraints, verbatim — a length limit, a language, anything
    the caller wants the writer told. Passed through unedited rather than
    interpreted here, because a constraint this layer silently reworded would
    be one the caller cannot verify was applied."""

    @property
    def is_empty(self) -> bool:
        return not (self.recent_topics or self.recent_projects
                    or self.recent_angles or self.notes)


@dataclass(frozen=True)
class GenerationRequest:
    """One generation call: an assembled context, and the labels for the post.

    The context is required and is the *only* source of facts. There is no
    parameter for "extra text to include", because that is how a raw chunk
    would get back in: the layer above assembles, and generation reads what was
    assembled (``PLAN.md`` Step 8).

    ``topic``, ``angle`` and ``project`` are labels — what the caller has
    decided to write about, and what Step 6 should record if this is
    published. They are instructions to the writer, never evidence: nothing
    prevents a caller from naming a topic the evidence does not support, which
    is exactly why they are labelled as a task rather than placed in the
    evidence block.
    """

    context: PersonalBrandingContext
    topic: str | None = None
    angle: str | None = None
    project: str | None = None

    evidence: tuple[ContextItem, ...] | None = None
    """The subset of the context's evidence to write from, or ``None`` for all
    of it.

    Selection is the Agent's job (``PLAN.md`` Step 10); generation's job is to
    write from what it was given. An explicit subset must come *from this
    context* — :func:`app.generation.prompt.build_prompt` refuses anything
    else, so a caller cannot pass retrieved-looking material that the assembly
    layer never placed.
    """

    constraints: PublishingConstraints = field(
        default_factory=PublishingConstraints
    )

    def __post_init__(self) -> None:
        for name in ("topic", "angle", "project"):
            value = getattr(self, name)
            if value is not None and not str(value).strip():
                raise ValueError(
                    f"{name} was given but is empty; pass None instead, so a "
                    f"blank label cannot reach the record"
                )


@dataclass(frozen=True)
class EvidenceCitation:
    """One piece of evidence, under the label the prompt gave it.

    The label (``E1``, ``E2``, …) is the interface between the model and the
    corpus: the prompt lists evidence under labels and asks for the labels it
    used back. That is what makes a citation checkable — the text of a source
    path is something a model can invent, whereas a label either resolves
    against the list that was sent or does not exist.
    """

    label: str
    source: str
    chunk_id: str
    evidence_state: str | None = None

    @classmethod
    def from_item(cls, label: str, item: ContextItem) -> "EvidenceCitation":
        return cls(
            label=label,
            source=item.source,
            chunk_id=item.chunk_id,
            evidence_state=item.evidence_state,
        )


@dataclass(frozen=True)
class GeneratedPost:
    """A candidate post and the evidence it says it used.

    ``citations`` can only ever contain evidence that was *supplied* —
    :mod:`app.generation.generator` resolves the model's labels against the
    prompt's own list, so an invented label cannot become a citation. Labels
    that did not resolve are not silently dropped: they are reported in
    ``unresolved_labels``, because a model citing a source it was never given
    is a fact about the draft that Step 9 must be able to see.
    """

    content: str
    citations: tuple[EvidenceCitation, ...] = ()
    unresolved_labels: tuple[str, ...] = ()

    @property
    def cited_labels(self) -> tuple[str, ...]:
        return tuple(citation.label for citation in self.citations)

    @property
    def is_cited(self) -> bool:
        """True when the draft points at at least one supplied piece of
        evidence.

        Not a quality judgement and not a gate — the question *"is this claim
        supported?"* needs the text, the evidence and Step 9's checks. It says
        only whether the draft named anything, which is the first thing a
        person reading an audit wants to know.
        """
        return bool(self.citations)


@dataclass(frozen=True)
class GenerationMetadata:
    """What produced this draft, for the audit record.

    ``PLAN.md`` Step 8: *"Model id, prompt/version identifier, and parameters
    are returned with the draft."* A published post whose model, prompt version
    and parameters cannot be named afterwards is a post nobody can explain, and
    the corpus's audit policy is built on being able to explain.

    Every field is a value the caller passed in or that was measured here.
    Nothing is inferred, and no secret is present: model id, prompt version
    and generation parameters are ordinary configuration, and the credential
    is never read into this object at all.
    """

    model_id: str
    prompt_version: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    evidence_item_count: int = 0
    guidance_item_count: int = 0
    evidence_labels: tuple[str, ...] = ()
    latency_ms: float | None = None
    """Measured, and ``None`` when no call was made — a declined result that
    never reached the model must not carry a plausible-looking duration."""


@dataclass(frozen=True)
class GenerationResult:
    """The outcome of one generation call.

    Exactly one of ``post`` and ``decline_reason`` is set, and
    ``outcome`` says which. A failure is not a third case: it is a
    :class:`~app.generation.errors.GenerationError`, because there is nothing
    to return.
    """

    outcome: GenerationOutcome
    metadata: GenerationMetadata
    post: GeneratedPost | None = None
    decline_reason: DeclineReason | None = None
    decline_message: str = ""

    @property
    def generated(self) -> bool:
        return self.outcome is GenerationOutcome.GENERATED

    @property
    def declined(self) -> bool:
        """True when generation deliberately produced nothing.

        A normal outcome, not a failure — the workflow ends the run as
        ``DO_NOT_PUBLISH`` and Step 7 sends no notification.
        """
        return self.outcome is GenerationOutcome.DECLINED

    @property
    def text(self) -> str:
        """The post, or an empty string. For callers that only need the text."""
        return self.post.content if self.post else ""

    @property
    def citations(self) -> tuple[EvidenceCitation, ...]:
        return self.post.citations if self.post else ()


@dataclass(frozen=True)
class GenerationPrompt:
    """An assembled prompt, as separate named blocks.

    The whole point of this type is that the parts of the prompt are *fields*.
    ``PLAN.md`` Step 8 forbids one thing above all: *"Do not concatenate
    everything into an undifferentiated prompt."* The failure that produces is
    specific — evidence and communication guidance end up in one block of text,
    and a model told *"write in a direct, technical voice"* beside *"I built a
    FastAPI shipment API"* has no way to know that one is a fact it may claim
    and the other is a manner of speaking. The post that comes back claims a
    writing style as an achievement.

    Because the blocks are separate, that separation is testable as a property
    of the value rather than as a property of a string nobody diffs: no test
    has to assert on a prompt's *wording*, only on which block holds what.

    Rendering is deterministic — same request, same bytes — and adds section
    headers rather than merging: what a model reads is labelled sections, and
    what the code holds is the same thing unmerged.
    """

    version: str
    instructions: str
    """The system message: role, the absolute grounding rules, and the output
    shape. Separate from the material so that a prohibition is never something
    a caller's context could push out of the prompt."""

    task_block: str = ""
    evidence_block: str = ""
    guidance_block: str = ""
    constraints_block: str = ""

    citations: tuple[EvidenceCitation, ...] = ()
    """The labels the evidence block actually lists, in the order it lists
    them. This is the set a model's answer is resolved against, which is what
    makes "the draft cites only supplied evidence" a structural property."""

    #: Section headers, in the order they are rendered. Public because a test
    #: asserting the separation should name the same headers a model reads.
    #: A ``ClassVar`` rather than a field: it is the shape of every prompt, not
    #: something a caller may vary per request.
    SECTION_TITLES: ClassVar[tuple[tuple[str, str], ...]] = (
        ("task_block", "TASK"),
        ("evidence_block", "EVIDENCE"),
        ("guidance_block", "COMMUNICATION GUIDANCE"),
        ("constraints_block", "CONSTRAINTS"),
    )

    @property
    def has_evidence(self) -> bool:
        """True when the prompt lists evidence at all.

        Derived from ``citations``, which is built from the items actually
        placed in the block, so this cannot disagree with what a model would
        read.
        """
        return bool(self.citations)

    @property
    def blocks(self) -> tuple[tuple[str, str], ...]:
        """The non-empty blocks, as ``(title, text)``, in render order."""
        return tuple(
            (title, getattr(self, name))
            for name, title in self.SECTION_TITLES
            if getattr(self, name)
        )

    def body(self) -> str:
        """The user message: labelled blocks, one after another.

        Deterministic by construction — the blocks come from a tuple, not from
        a dict, and nothing here reads a clock, a random source, or the
        environment.
        """
        return "\n\n".join(f"## {title}\n{text}" for title, text in self.blocks)

    def messages(self) -> tuple[dict[str, str], ...]:
        """The prompt as chat messages, ready for any OpenAI-compatible client.

        Plain dicts rather than framework message objects, so the seam a test
        records is the same seam a real client receives and no test double has
        to be a framework type to be usable.
        """
        return (
            {"role": "system", "content": self.instructions},
            {"role": "user", "content": self.body()},
        )

    def render(self) -> str:
        """The whole prompt as one string, for logging and assertions."""
        return f"{self.instructions}\n\n{self.body()}"
