"""Grounded post generation: assembled context in, one candidate post out.

``PLAN.md`` Step 8. This is the layer between context assembly (Step 4) and
verification (Step 9):

    PersonalBrandingContext  ->  PostGenerator  ->  GenerationResult
                                       |
                                       +->  the LLM (OpenRouter, OpenAI-compatible)

    from app.generation import PostGenerator, GenerationRequest

    result = PostGenerator().generate(GenerationRequest(context=context,
                                                        topic="retrieval"))

Three things this layer deliberately is not:

* **Not a retriever.** It never queries Chroma and never writes from a chunk
  the context layer did not place. Evidence is a value it is handed, which is
  what makes "the draft cites only supplied evidence" checkable.
* **Not a verifier.** It has no opinion on whether the draft is true, strong,
  or worth publishing. Step 9 owns that, and a judgement invented here would
  be a second opinion nothing has checked.
* **Not a fallback machine.** ``app/retrieval/multi_query.py`` degrades to the
  original query when the model is unreachable; generation cannot degrade to
  anything. ``PLAN.md`` Step 8, Failure/recovery: *"There is no valid degraded
  post."* An unreachable model or an unparseable answer raises
  :class:`~app.generation.errors.GenerationError`, the workflow records a
  failed phase, Step 7 notifies, and nothing is published.

The one thing it does do, when it should, is **decline**. A context with no
evidence, or evidence a model reports as insufficient, produces a
``DECLINED`` result — a normal outcome that lands on ``DO_NOT_PUBLISH``, which
Step 7 waives precisely because it is a success. Declining is the behaviour
``PLAN.md`` asks for: prefer no post over an unsupported one.

Nothing here writes state. ``PLAN.md`` Step 8 is explicit that persistence
happens only at the publish step, and this package cannot reach the store, the
publishing service, the notification transport, or the knowledge layers at all
— the test suite asserts that by parsing these modules rather than by trusting
that no test looked.

Public surface, and deliberately nothing more:

    PostGenerator            the single entry point
    GenerationRequest        what goes in — a context, and the labels
    GenerationResult         what comes out — a draft, or a decline
    GenerationOutcome        the two outcomes, for branching
    DeclineReason            why there was no post
    GenerationError          the failure, when there is no post and no decline
    build_prompt             the deterministic assembly, for inspection
"""
from app.generation.enums import (
    DeclineReason,
    GenerationFailureCategory,
    GenerationOutcome,
)
from app.generation.errors import GenerationError
from app.generation.generator import PostGenerator
from app.generation.models import (
    EvidenceCitation,
    GeneratedPost,
    GenerationMetadata,
    GenerationPrompt,
    GenerationRequest,
    GenerationResult,
    PublishingConstraints,
)
from app.generation.prompt import (
    PROHIBITED_CLAIMS,
    PROMPT_VERSION,
    build_prompt,
    selected_evidence,
)

__all__ = [
    "PROHIBITED_CLAIMS",
    "PROMPT_VERSION",
    "DeclineReason",
    "EvidenceCitation",
    "GeneratedPost",
    "GenerationError",
    "GenerationFailureCategory",
    "GenerationMetadata",
    "GenerationOutcome",
    "GenerationPrompt",
    "GenerationRequest",
    "GenerationResult",
    "PostGenerator",
    "PublishingConstraints",
    "build_prompt",
    "selected_evidence",
]
