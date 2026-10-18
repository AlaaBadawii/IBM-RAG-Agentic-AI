"""Advisory editorial checks: discoverability signals, never a gate.

A post can be perfectly grounded and still be hard to *find*: an opening that
announces excitement instead of naming the subject, or a post that is only a
link. Those are writing-quality observations, not evidence problems, and the
gate's job is evidence — so they are reported and recorded, never used to
reject or revise. This is the same posture as the advisory judge
(:mod:`app.verification.judge`), one layer down and entirely deterministic: no
model, no clock, no network, the text alone.

The checks are deliberately light. They say what a reader (and a search) would
miss and nothing more; a writer that follows the LinkedIn contract in
:mod:`app.generation.voice` will not trip them, and a writer that does is
still published if the evidence supports it.
"""
import re

__all__ = ["discoverability_notes"]

#: Openers that carry no subject. A reader scanning the feed, and a search
#: indexing the post, learn nothing from them about what the post is about.
_GENERIC_OPENERS = (
    "excited to announce",
    "excited to share",
    "thrilled to announce",
    "thrilled to share",
    "happy to announce",
    "happy to share",
    "proud to announce",
    "proud to share",
    "delighted to announce",
    "delighted to share",
    "humbled to announce",
)

_URL = re.compile(r"https?://\S+")

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9'-]*")

#: Below this many non-link characters, a post is "mostly a link". A link with
#: a one-line caption is a share, not a post about anything findable.
_MIN_BODY_CHARS = 50


def discoverability_notes(content: str) -> tuple[str, ...]:
    """Advisory notes about how findable a post is. Empty when it reads fine.

    Deterministic and order-stable, so the same text always yields the same
    notes and a test can assert on them. Never raises: an empty or blank draft
    has nothing to say about discoverability and returns ``()``.
    """
    text = (content or "").strip()
    if not text:
        return ()

    notes: list[str] = []
    first_line = next(
        (line.strip() for line in text.splitlines() if line.strip()), ""
    )
    lowered = first_line.casefold()
    opener = next((p for p in _GENERIC_OPENERS if p in lowered), None)
    if opener is not None:
        notes.append(
            f"the opening is a generic announcement ({opener!r}); lead with "
            f"the subject so a reader — and a search — can find it"
        )
    elif len(_WORD.findall(first_line)) < 3:
        notes.append(
            "the first line is too short to establish the subject; name what "
            "the post is about in the first one or two lines"
        )

    if len(_URL.sub(" ", text).strip()) < _MIN_BODY_CHARS:
        notes.append(
            "the post is mostly a link; a link-only post gives a reader and a "
            "search nothing to find"
        )
    return tuple(notes)
