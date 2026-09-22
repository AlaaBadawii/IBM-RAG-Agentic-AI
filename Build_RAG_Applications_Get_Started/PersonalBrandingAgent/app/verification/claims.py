"""Turning a draft into the claims a verifier can check, deterministically.

``PLAN.md`` Step 9 asks for claim-level results, and it asks for the
deterministic checks to be cheap and strict. Both of those are decided here,
because everything downstream works on what this module produces:

**A claim is a sentence.** Not a semantic unit — a *sentence*, split on
sentence punctuation and newlines, with list markers stripped. That is a
deliberately crude definition, and the alternative is worse: classifying which
sentences "really make a claim" needs the semantic judgement this layer is not
allowed to fake, and a sentence that was skipped is a sentence nothing
downstream can check. Every non-empty sentence becomes a claim, so nothing
escapes; the classification that matters — is it supported? — is made against
evidence, per claim, by :mod:`app.verification.policy`.

**A reference is an exact factual token.** Numbers, percentages, dates,
versions and quantities: the things ``data/audit/README.md`` §3 names when it
forbids inventing *"dates, metrics, technologies, responsibilities, or
outcomes"*. They are found by pattern, and they are checked by exact
normalized-string membership in the evidence, which is the one kind of checking
that is genuinely deterministic — no model, no similarity score, no threshold.

**Its limit is known and written down.** ``40 %`` normalizes to ``40%`` and
matches; ``forty percent`` and ``2× faster`` do not, and a claim phrased that
way passes the reference check by not producing a reference — a false negative,
in the lenient direction. Semantic support is not this module's question at
all; it belongs to the advisory judge, which is where
:mod:`app.verification.support` puts it.

Tokenization is stated here rather than imported from ``app/retrieval``: the
overlap check below needs *content* terms, and reaching into the retrieval
package for its BM25 tokenizer would make this layer depend on the retrieval
stack — the boundary the package's import scan asserts. ``tests/
test_verification_rules.py`` asserts the two tokenizers agree, so the rule that
is shared stays shared and the dependency does not exist.
"""
import re

from app.verification.models import Claim, Reference

__all__ = [
    "content_terms",
    "extract_references",
    "split_claims",
    "tokenize",
]

# --------------------------------------------------------------- claims ---

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+|\n+")
_LIST_MARKER = re.compile(r"^\s*(?:[-*•·]|\d+[.)])\s*")


def split_claims(text: str) -> tuple[Claim, ...]:
    """Every non-empty sentence of ``text``, as a numbered claim.

    Indexes are 1-based and follow the order the sentences appear in, so a
    violation can point at "claim 3" and a person can count to it. The
    numbering is part of the report, which is why it is assigned here rather
    than left to whatever consumer iterates the tuple.
    """
    claims: list[Claim] = []
    for piece in _SENTENCE_BOUNDARY.split(text or ""):
        sentence = _LIST_MARKER.sub("", piece).strip()
        if not sentence:
            continue
        claims.append(
            Claim(
                index=len(claims) + 1,
                text=sentence,
                references=extract_references(sentence),
            )
        )
    return tuple(claims)


# ----------------------------------------------------------- references ---

_REFERENCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    # 40 %, 12.5% — a percentage is the metric a reader checks first.
    re.compile(r"\d+(?:[.,]\d+)?\s?%"),
    # 1.4.2, 3.10 — version numbers, which name technologies and releases.
    # The lookbehind is a *digit or dot*, not a word boundary: versions are
    # written "v1.4.2" and "Python 3.10", and a boundary test would match the
    # "4.2" inside the first and report a version the draft never stated.
    re.compile(r"(?<![\d.])\d+\.\d+(?:\.\d+)*"),
    # 2024, 1998 — born-on dates, which the audit names explicitly.
    re.compile(r"\b(?:19|20)\d{2}\b"),
    # 3 months, 20 years, 500 ms, 10k, 8x — counted things and quantities.
    re.compile(
        r"(?<![\d.])\d[\d,]*(?:\.\d+)?\s?"
        r"(?:ms|sec|secs|seconds|min|mins|minutes|hours|days|weeks|months|"
        r"years|k|kb|mb|gb|tb|x)\b"
    ),
)

_NORMALIZE_STRIP = re.compile(r"[\s,]")


def normalize_reference(raw: str) -> str:
    """The form a reference is compared in: lowercase, no spaces, no commas.

    ``1,000 ms`` and ``1,000ms`` are the same claim about the same thing; a
    comparison that treated them as different would reject a draft for
    formatting.
    """
    return _NORMALIZE_STRIP.sub("", raw.lower())


def extract_references(text: str) -> tuple[Reference, ...]:
    """Every exact factual token in ``text``, in order, each once.

    A reference is kept as it was written (``raw``) *and* in its comparable
    form (``normalized``): the report has to show a person the ``40 %`` the
    draft printed, and the check has to compare the ``40%`` the evidence
    stores.
    """
    found: list[Reference] = []
    seen: set[str] = set()
    for pattern in _REFERENCE_PATTERNS:
        for match in pattern.finditer(text or ""):
            raw = match.group(0).strip()
            normalized = normalize_reference(raw)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            found.append(Reference(raw=raw, normalized=normalized))
    return tuple(found)


# --------------------------------------------------------------- overlap ---

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

#: Terms too common to carry content. Short and explicit rather than imported:
#: a stopword list is a policy about *this* check, and it has to be readable
#: next to the check it governs. The overlap test that uses it is deliberately
#: conservative — it fires only when a claim's vocabulary comes from guidance
#: and from nowhere else — so a word that is wrongly absent from this list
#: makes the check quieter, never louder.
_STOPWORDS = frozenset({
    "about", "after", "again", "against", "all", "almost", "along", "also",
    "although", "always", "among", "and", "another", "anything", "any",
    "are", "around", "because", "been", "before", "being", "below", "between",
    "both", "but", "can", "cannot", "could", "did", "does",
    "doing", "done", "down", "during", "each", "either", "else", "even",
    "ever", "every", "for", "from", "further", "get", "got", "had", "has",
    "have", "having", "her", "here", "hers", "him", "his", "how",
    "himself", "into", "its", "itself", "just", "least", "less", "let",
    "like", "made", "make", "many", "may", "might", "more", "most", "much",
    "must", "myself", "neither", "never", "new", "not", "now", "off", "one",
    "only", "other", "others", "our", "out", "over", "own", "rather",
    "really", "same", "see", "she", "should", "since", "some", "still",
    "such", "than", "that", "the", "their", "theirs", "them", "themselves",
    "then", "there", "these", "they", "this", "those", "though", "through",
    "thus", "too", "two", "under", "until", "upon", "use", "very", "via",
    "want", "was", "way", "were", "what", "when", "where", "whether",
    "which", "while", "who", "why", "will", "with", "within", "without",
    "would", "yet", "you", "your", "yours",
})


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens — the same rule
    :func:`app.retrieval.bm25.tokenize` applies, stated here so this package
    needs no import from the retrieval layer."""
    return _TOKEN_PATTERN.findall((text or "").lower())


def content_terms(text: str) -> frozenset[str]:
    """The words in ``text`` that carry content: tokens of three letters or
    more that are not stopwords."""
    return frozenset(
        token for token in tokenize(text)
        if len(token) > 2 and token not in _STOPWORDS
    )
