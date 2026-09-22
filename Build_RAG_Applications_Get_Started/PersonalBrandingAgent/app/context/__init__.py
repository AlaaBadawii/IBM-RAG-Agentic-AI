"""Branding context layer (``PLAN.md`` Step 4).

The layer between retrieval and generation: it takes what a retrieval strategy
found and assembles it into a structured, grounded, auditable context.

    RetrievalResult  ->  PersonalBrandingContext  ->  generation

It answers four questions that generation, verification (Step 9) and the agent
(Step 10) all need, and that a list of chunks cannot answer at all:

    What is here, by kind?      named sections, never one concatenated blob
    Where did it come from?     every item keeps its source, chunk id and state
    How strong is it?           the corpus's own evidence hierarchy, applied
    Is there any of it at all?  an explicit SUFFICIENT / INSUFFICIENT outcome

Public surface, and deliberately nothing more:

    build_context          the single entry point
    PersonalBrandingContext  what it returns
    EvidenceStatus         the first-class insufficiency state
    FreshnessState         how current a source's indexed evidence is

Not a second retriever, not a summarizer, not a fact database, not a
generator, and not an agent. It assembles what retrieval found; it adds no
facts of its own and calls no model.
"""
from app.context.builder import build_context
from app.context.enums import EvidenceStatus, FreshnessState
from app.context.models import (
    ContextCoverage,
    ContextItem,
    ContextSection,
    PersonalBrandingContext,
    SectionCoverage,
    SourceState,
    SourceStateReport,
)

__all__ = [
    "ContextCoverage",
    "ContextItem",
    "ContextSection",
    "EvidenceStatus",
    "FreshnessState",
    "PersonalBrandingContext",
    "SectionCoverage",
    "SourceState",
    "SourceStateReport",
    "build_context",
]
