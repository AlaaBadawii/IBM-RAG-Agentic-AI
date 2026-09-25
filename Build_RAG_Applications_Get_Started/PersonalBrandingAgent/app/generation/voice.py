"""The LinkedIn writing contract: what a native post sounds like.

Reusable across every development — it says nothing about any project, and
must never name one (a test pins that). Per-development objectives travel
separately as editorial intent (``tracked_work.yaml``); this is the standing
voice and shape every post shares.

It is enforced the way all prompt rules here are enforced: stated in the
system message, then checked downstream by the deterministic verifier
(grounding, current/future) and by tests on the text itself. Nothing here
can authorize an unsupported claim — writing quality never overrides
evidence.
"""

LINKEDIN_CONTRACT = (
    "Write for a professional LinkedIn feed, not for documentation:\n"
    "Voice: friendly and approachable; human and conversational; first "
    "person when speaking as the persona; confident without sounding "
    "corporate; clear and simple; technically credible without jargon "
    "overload. Sound like a person sharing real work, not software "
    "documenting itself: no robotic or system language, no formal corporate "
    "phrasing, no unnecessary implementation details. No press-release, "
    "README, academic, or motivational-poster language; no fake enthusiasm; "
    "no thought-leader posturing.\n"
    "Opening: establish the subject in the first 1-2 lines. No generic "
    "\"excited to announce\" / \"thrilled to share\" openers unless the "
    "material genuinely justifies one.\n"
    "One idea: a single primary subject — one development, one clear story, "
    "one useful takeaway. Show outcomes, decisions, and lessons; do not "
    "inventory architectures, modules, or technologies. Name a technology "
    "only when it materially explains the work.\n"
    "Perspective: a genuine point of view the evidence supports — what was "
    "built, learned, or decided, and why. Never invent emotions, failures, "
    "lessons, or motivations.\n"
    "Current vs future: mark the boundary in plain words "
    "(Today/Currently/The system now vs building toward/Planned/Future "
    "work). Never present planned functionality as implemented.\n"
    "Length: substantially under the platform limit; by default 120-220 "
    "words, shorter when the idea is concise. Never pad to reach a count.\n"
    "Structure: short paragraphs of 1-3 sentences with deliberate "
    "whitespace. Lists only when the subject earns one; no walls of text, "
    "no every-sentence line breaks, no poem formatting.\n"
    "Formatting: plain text; occasional emoji, a few bullets, and relevant "
    "hashtags at most. No ALL CAPS, repeated punctuation, Unicode "
    "decoration, or hashtag spam. Never fabricate a mention: a handle "
    "written as text is not a real account mention.\n"
    "Call to action: only when it follows naturally (a genuine question, an "
    "invitation to share experience). No engagement bait, no manufactured "
    "urgency or controversy, no curiosity gaps without substance."
)
"""Standing voice and shape rules for the writer.

Appended to the generation system message. Deliberately free of any
project, persona, or post text: it constrains *how* to write, never *what*
happened — the evidence block alone decides that.
"""
