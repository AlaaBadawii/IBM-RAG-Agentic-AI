"""The deterministic checks, and the severities that make them gates.

``PLAN.md`` Step 9 asks for six deterministic checks and calls them
authoritative. They are all here, and they are all string comparisons:

```text
citation exists              → NO_CITATION
source exists                → CITATION_NOT_IN_CONTEXT
cited evidence available     → CITATION_NOT_IN_CONTEXT
evidence state satisfies     → EVIDENCE_STATE_TOO_WEAK
exact references validated   → UNSUPPORTED_REFERENCE / UNCITED_REFERENCE
required evidence not empty  → EVIDENCE_INSUFFICIENT (and EMPTY_DRAFT)
```

Two more come from the corpus's own policy rather than from that list, because
``PLAN.md`` says to operationalize what is already written down instead of
inventing a parallel philosophy:

* ``GUIDANCE_AS_EVIDENCE`` — Step 4 keeps positioning, vision and writing style
  in *separate fields* from evidence, and ``data/evidence/README.md`` scopes
  them to how a supported fact is communicated. A claim whose vocabulary comes
  from guidance and from nowhere else is a claim with no evidence behind it.
* ``FORBIDDEN_INFERENCE`` — the five "never infer X from Y" rules of
  ``data/audit/README.md`` §3, transcribed verbatim into
  :data:`FORBIDDEN_INFERENCES` with the line each one came from.

**Why severity is a table.** PLAN.md does not say which findings may be
revised and which end the attempt, and the answer has to be the same every
time it is asked. So each kind declares its severity once, in
:data:`VIOLATION_SEVERITY`, and the question that assigns it is the only
question that matters: *can rewriting this draft against this same evidence
make it publishable?* Findings about the **wording** say yes and revise.
Findings about the **evidence or the draft's provenance** say no and reject —
a source the context does not hold cannot be cited into existence, and a
metric the corpus does not contain cannot be reworded into one it does.

**What this module cannot do.** One shared word is enough overlap to attribute
a claim to a piece of evidence, and exact-string matching cannot see a
paraphrase. Both limits are real, both are known, and neither is papered over:
they are the reason the advisory judge in :mod:`app.verification.support`
exists, and the reason a judge's objection is reported rather than hidden.
"""
import re
from dataclasses import dataclass
from typing import Mapping

from app.verification.claims import normalize_reference
from app.verification.enums import Severity, ViolationKind
from app.verification.models import (
    Claim,
    EvidenceReference,
    Reference,
    SuppliedEvidence,
    Violation,
)

__all__ = [
    "FORBIDDEN_INFERENCES",
    "UNUSABLE_EVIDENCE_STATES",
    "VIOLATION_SEVERITY",
    "WEAK_EVIDENCE_STATES",
    "ForbiddenInference",
    "check_claim",
    "references_supported",
    "requires_evidence",
    "severity_for",
    "violation",
]

# ------------------------------------------------------------- severities ---

VIOLATION_SEVERITY: Mapping[ViolationKind, Severity] = {
    ViolationKind.EMPTY_DRAFT: Severity.REJECT,
    ViolationKind.NO_CITATION: Severity.REVISABLE,
    ViolationKind.CITATION_NOT_IN_CONTEXT: Severity.REJECT,
    ViolationKind.EVIDENCE_INSUFFICIENT: Severity.REJECT,
    ViolationKind.GUIDANCE_AS_EVIDENCE: Severity.REVISABLE,
    ViolationKind.EVIDENCE_STATE_TOO_WEAK: Severity.REJECT,
    ViolationKind.FORBIDDEN_INFERENCE: Severity.REJECT,
    ViolationKind.UNSUPPORTED_REFERENCE: Severity.REJECT,
    ViolationKind.UNCITED_REFERENCE: Severity.REVISABLE,
    ViolationKind.ADVISORY_UNSUPPORTED: Severity.REVISABLE,
}
"""Every kind, once. :func:`severity_for` is total over the enum, and a test
asserts it — a kind that reaches a call site without a severity would be a
gate that silently does not gate."""


def severity_for(kind: ViolationKind) -> Severity:
    """The severity declared for ``kind``.

    Raises:
        KeyError: ``kind`` is not in the table. Deliberately loud: defaulting
            an unknown kind to ``REVISABLE`` would let a future check be added
            without anyone deciding whether it gates.
    """
    return VIOLATION_SEVERITY[kind]


def violation(kind: ViolationKind, detail: str, *,
              claim_index: int | None = None,
              advisory: bool = False) -> Violation:
    """Build a finding with the severity its kind declares."""
    return Violation(
        kind=kind,
        severity=severity_for(kind),
        detail=detail,
        claim_index=claim_index,
        advisory=advisory,
    )


# ----------------------------------------------------------- what's a claim ---

_REFERENCE_BEARING = re.compile(r"\d")

_FIRST_PERSON = re.compile(
    r"\b(?:i|i'm|i've|i'd|i'll|my|mine|myself|me|we|we're|we've|our|ours)\b",
    re.IGNORECASE,
)

#: Verbs of doing. Deliberately a vocabulary rather than a heuristic: a claim
#: that something was built, led, shipped or measured is a claim about
#: personal capability, and every one of them is something the corpus either
#: records or does not.
_ACHIEVEMENT = re.compile(
    r"\b(?:built|build|building|designed|designing|developed|developing|"
    r"implemented|implementing|shipped|shipping|deployed|deploying|created|"
    r"created|led|leading|managed|managing|launched|launching|migrated|"
    r"automated|automating|reduced|reducing|improved|improving|increased|"
    r"achieved|achieving|delivered|delivering|architected|integrated|"
    r"optimised|optimized|scaled|wrote|writing|published|contributed|"
    r"contributes|responsible|experience|experienced|expertise|skilled|"
    r"proficient|mastered|certified|certification|completed|completing|"
    r"finished|earned|production|client|clients|"
    r"customer|customers)\b",
    re.IGNORECASE,
)


def requires_evidence(claim: Claim) -> bool:
    """Whether this sentence asserts something the corpus has to support.

    The gate needs this because most of a post is not a factual claim. "The
    takeaway matters more than the tool" asserts nothing about the author and
    does not need a citation; "I built a retrieval pipeline with Chroma" does.
    Without the distinction, a gate that demanded evidence for every sentence
    would return ``REVISION_REQUIRED`` for every post ever written, which is
    indistinguishable from a gate that returns nothing at all.

    A claim requires evidence when it carries an exact factual reference, or
    speaks in the first person, or uses a verb of doing. A question requires
    none: it asserts nothing, so there is nothing to support.
    """
    text = claim.text.strip()
    if not text or text.endswith("?"):
        return False
    if claim.references:
        return True
    return bool(_FIRST_PERSON.search(text) or _ACHIEVEMENT.search(text))


# -------------------------------------------------------------- overlap ---

def _collapse(text: str) -> str:
    """Lowercased, commas removed, whitespace collapsed to single spaces."""
    return re.sub(r"\s+", " ", (text or "").lower().replace(",", ""))


def references_supported(references: tuple[Reference, ...],
                         contents: tuple[str, ...]) -> bool:
    """Whether every reference occurs in at least one of ``contents``.

    The exact-string check ``PLAN.md`` asks for, in both of the forms a
    reference is written in. The plain form (``2024``, ``40%``) is searched in
    the comma-stripped, whitespace-collapsed text, so ``40 %`` matches ``40%``
    and ``2024`` does not match across a boundary. The loose form (``1,000
    ms``, ``12.5 %``) additionally searches the fully stripped text, because a
    reference carrying its own separator cannot be found otherwise.

    Its limit, stated rather than hidden: this sees strings, not meanings. A
    paraphrase (``2× faster`` for ``200% of the previous throughput``) is not
    matched, and in that direction a fabricated-looking figure passes. That is
    the advisory judge's question, and where it cannot answer, the gate says
    so rather than pretending the check was stronger than it is.
    """
    if not references:
        return True
    collapsed = tuple(_collapse(content) for content in contents)
    stripped = tuple(normalize_reference(content) for content in contents)
    for reference in references:
        loose = reference.raw != reference.normalized
        if any(reference.normalized in text for text in collapsed):
            continue
        if loose and any(reference.normalized in text for text in stripped):
            continue
        return False
    return True


# ------------------------------------------------------- evidence states ---

WEAK_EVIDENCE_STATES = frozenset({"ASPIRATIONAL", "LEARNING"})
"""States that declare the thing they describe is *not* demonstrated.

``ASPIRATIONAL`` is the corpus's own wording for "wanted/future capability,
not yet demonstrated"; ``LEARNING`` for "no substantial implementation
demonstrated". A claim that asserts the capability anyway is the exact upgrade
``data/audit/README.md`` §3 forbids — *unless the claim makes the same
admission*, which is what :data:`_HEDGED_CLAIM` is for.
"""

UNUSABLE_EVIDENCE_STATES = frozenset({"UNVERIFIED", "STALE"})
"""States nothing can rest on. No hedge exempts them: ``UNVERIFIED`` means the
evidence is insufficient and ``STALE`` means it was superseded. A claim that
leans on either is unsupported whatever its wording, because there is no fact
underneath it to word."""

_HEDGED_CLAIM = re.compile(
    r"\b(?:plan(?:ning|s)?|goal|aim|aiming|hope|hoping|want(?:ing)?|intend|"
    r"intending|exploring|explored|learning|learn(?:ed|ing)?|studying|studied|"
    r"practis(?:e|ing)|practic(?:e|ing)|currently|starting|began|beginner|"
    r"next|future|soon|towards|toward|working on|getting started)\b",
    re.IGNORECASE,
)
"""Vocabulary that turns a claim into a statement of intent or study.

"I'm learning X" is not a claim that X is demonstrated, and evidence which
says exactly that is what supports it. This is the corpus's own distinction —
``data/evidence/README.md`` defines ``LEARNING`` and ``ASPIRATIONAL`` as
legitimate states, not as findings — applied to the draft side of the
comparison.

Deliberately *not* including words like "course": having taken a course is a
claim about what was done, and mentioning one is not an admission that the
skill is undemonstrated. That inference is the one the audit forbids in the
other direction, and admitting its vocabulary here would let it through.
"""


def _state_violations(claim: Claim,
                      supporting: tuple[SuppliedEvidence, ...]
                      ) -> tuple[Violation, ...]:
    """Findings about the *declared strength* of the evidence behind a claim."""
    hedged = bool(_HEDGED_CLAIM.search(claim.text))
    found: list[Violation] = []
    seen: set[str] = set()
    for evidence in supporting:
        state = (evidence.reference.evidence_state or "").upper()
        unusable = state in UNUSABLE_EVIDENCE_STATES
        declared_weak = state in WEAK_EVIDENCE_STATES and not hedged
        if not (unusable or declared_weak) or state in seen:
            continue
        seen.add(state)
        found.append(violation(
            ViolationKind.EVIDENCE_STATE_TOO_WEAK,
            f"the evidence behind this claim declares itself {state} "
            f"({evidence.reference.source}); the claim states it as "
            f"demonstrated",
            claim_index=claim.index,
        ))
    return tuple(found)


# --------------------------------------------------- forbidden inferences ---

@dataclass(frozen=True)
class ForbiddenInference:
    """One rule from ``data/audit/README.md`` §3, as a check.

    Three parts: the *assertion* the draft makes (``claim_pattern``), the
    sections that could even in principle carry it (``strong_sections``) and
    the words evidence must contain to count as carrying it
    (``strong_pattern``). A claim that makes the assertion, is attributed to
    evidence, and has no evidence that qualifies as strong, is the inference
    the audit forbids — and it is forbidden because the weaker source and the
    stronger claim are both visible here, not because a model guessed.
    """

    key: str
    basis: str
    """Verbatim from ``data/audit/README.md`` §3, so the rule can be checked
    against the policy it operationalizes without leaving the code."""

    claim_pattern: re.Pattern[str]
    strong_sections: frozenset[str]
    strong_pattern: re.Pattern[str]
    detail: str
    weak_source_pattern: re.Pattern[str] | None = None
    """Evidence whose *source path* matches this can never be strong for this
    rule, whatever its text says.

    Only the deployment rule uses it, and it is what makes that rule mean what
    the audit says: ``deployment.yaml`` is configuration, and a configuration
    file is not evidence that anything ran. Text alone could not draw that
    line — the file would pass by mentioning the word ``deployment``.
    """


#: Source paths that describe *how something would be run* rather than what
#: happened. Matched against ``ContextItem.source``, which the context layer
#: preserves verbatim for exactly this kind of question.
_CONFIGURATION_SOURCE = re.compile(
    r"\.(?:ya?ml|toml|ini|conf|cfg|json|env|lock|properties)$"
    r"|(?:^|/)(?:docker-?compose|dockerfile|makefile|procfile|jenkinsfile)"
    r"(?:\.|$)",
    re.IGNORECASE,
)


_COURSEWORK = frozenset({"in_progress_courses", "certificates"})
"""The sections that record *taking* something rather than *doing* it."""

_ALL_EVIDENCE_BUT_COURSEWORK = frozenset({
    "repository_evidence", "evidence", "completed_projects",
    "in_progress_projects", "stories_lessons", "audit", "unclassified",
})

FORBIDDEN_INFERENCES: tuple[ForbiddenInference, ...] = (
    ForbiddenInference(
        key="coursework_as_professional_experience",
        basis="never infer professional experience from coursework",
        claim_pattern=re.compile(
            r"\b(?:professional|industry|commercial|hands[- ]on)\s+"
            r"experience\b|\bprofessionally\b|\bon[- ]the[- ]job\b",
            re.IGNORECASE,
        ),
        strong_sections=_ALL_EVIDENCE_BUT_COURSEWORK,
        strong_pattern=re.compile(
            r"\b(?:worked|working|employment|employed|role|position|"
            r"engineer at|developer at|internship|professional experience)\b",
            re.IGNORECASE,
        ),
        detail=(
            "the claim states professional experience, and the only evidence "
            "behind it records coursework rather than work"
        ),
    ),
    ForbiddenInference(
        key="local_project_as_production",
        basis="never infer production experience from a local project",
        claim_pattern=re.compile(r"\bproduction\b", re.IGNORECASE),
        strong_sections=_ALL_EVIDENCE_BUT_COURSEWORK,
        strong_pattern=re.compile(
            r"\b(?:production|deployed|deployment|shipped to prod)\b",
            re.IGNORECASE,
        ),
        detail=(
            "the claim states production experience, and the evidence behind "
            "it describes a local project that no supplied source places in "
            "production"
        ),
    ),
    ForbiddenInference(
        key="configuration_as_deployment",
        basis="never infer deployment from configuration alone",
        claim_pattern=re.compile(
            r"\b(?:deployed|deploying|deployment|hosted|hosting|live at|"
            r"available at|shipped to)\b",
            re.IGNORECASE,
        ),
        strong_sections=_ALL_EVIDENCE_BUT_COURSEWORK,
        strong_pattern=re.compile(
            r"\b(?:deployed|deploying|deployment|hosted|hosting)\b",
            re.IGNORECASE,
        ),
        detail=(
            "the claim states a deployment, and nothing behind it says the "
            "thing was deployed — configuration is not evidence of it running"
        ),
        weak_source_pattern=_CONFIGURATION_SOURCE,
    ),
    ForbiddenInference(
        key="course_completion_as_mastery",
        basis="never infer mastery from course completion",
        claim_pattern=re.compile(
            r"\b(?:mastery|mastered|master|expert|expertise|proficient|"
            r"proficiency|advanced)\b",
            re.IGNORECASE,
        ),
        strong_sections=_ALL_EVIDENCE_BUT_COURSEWORK,
        strong_pattern=re.compile(
            r"\b(?:mastery|mastered|master|expert|expertise|proficient|"
            r"proficiency|advanced|years of)\b",
            re.IGNORECASE,
        ),
        detail=(
            "the claim states mastery, and the evidence behind it records "
            "completing a course rather than demonstrating the skill"
        ),
    ),
    ForbiddenInference(
        key="portfolio_as_employment",
        basis=(
            "never infer employment from a portfolio entry without supporting "
            "evidence"
        ),
        claim_pattern=re.compile(
            r"\b(?:worked at|working at|employed (?:at|by)|my (?:role|job|"
            r"position) at|employment at|full[- ]time (?:role|position))\b",
            re.IGNORECASE,
        ),
        strong_sections=frozenset({"evidence", "stories_lessons"}),
        strong_pattern=re.compile(
            r"\b(?:employed|employment|worked at|full[- ]time|contract|"
            r"position at|role at|my (?:role|job|position))\b",
            re.IGNORECASE,
        ),
        detail=(
            "the claim states employment, and the evidence behind it is a "
            "portfolio entry with nothing that establishes a position"
        ),
    ),
)
"""The five rules of ``data/audit/README.md`` §3 that have the shape *weaker
source → stronger claim*.

The sixth line of that list — *"never invent dates, metrics, technologies,
responsibilities, or outcomes"* — is not here, because it is not an inference
from a source; it is assertion without one. Dates, metrics and version numbers
are caught by :func:`references_supported`, which is exact and shows the
missing string. Technologies, responsibilities and outcomes are not
string-checkable at all, and they are the advisory judge's question — which is
why the judge may not be trusted to invent and why its findings are reported.
"""


def forbidden_inference(claim: Claim,
                        supporting: tuple[SuppliedEvidence, ...]
                        ) -> ForbiddenInference | None:
    """The first rule this claim breaks, or ``None``.

    Only fires for a claim that *is* attributed to evidence. An unattributed
    claim is :attr:`~app.verification.enums.ViolationKind.NO_CITATION`'s
    business, and rejecting it here would turn "you did not cite this" into
    "this can never be said" — which is a different, and false, statement.
    """
    if not supporting:
        return None
    for rule in FORBIDDEN_INFERENCES:
        if not rule.claim_pattern.search(claim.text):
            continue
        strong = any(
            evidence.reference.section in rule.strong_sections
            and rule.strong_pattern.search(evidence.content)
            and not (
                rule.weak_source_pattern is not None
                and rule.weak_source_pattern.search(evidence.reference.source)
            )
            for evidence in supporting
        )
        if not strong:
            return rule
    return None


# ------------------------------------------------------------- the check ---

def check_claim(
    claim: Claim,
    *,
    cited: tuple[SuppliedEvidence, ...],
    supporting: tuple[SuppliedEvidence, ...],
    uncited: tuple[SuppliedEvidence, ...],
    guidance: tuple[EvidenceReference, ...],
) -> tuple[Violation, ...]:
    """Every deterministic finding about one claim.

    Args:
        claim: the sentence, as split by
            :func:`app.verification.claims.split_claims`.
        cited: every piece of supplied evidence the *draft* cited. The reference
            check runs against all of it, not against the part that overlaps
            this claim: a figure is fabricated relative to what the draft
            attributed, and a claim whose vocabulary does not overlap the
            citation it needed is exactly the case a gate must not let through
            by looking at too narrow a set.
        supporting: supplied evidence the draft cited *and* which shares
            content with this claim — what the claim is attributed to.
        uncited: supplied evidence that shares content with this claim but
            which the draft did not cite. Used only to tell an under-cited
            claim from an unsupported one, because the repair differs.
        guidance: positioning/vision/voice references that share content with
            this claim. They are not evidence and cannot support anything;
            they are here to *identify* a claim that came from them.

    Returns:
        Findings in a stable order, empty when the claim is clean. The verdict
        for the claim is derived from their severities, not from their count.
    """
    violations: list[Violation] = []

    # 1. exact factual references, against the evidence the draft cited.
    cited_contents = tuple(evidence.content for evidence in cited)
    if claim.references and cited_contents:
        if not references_supported(claim.references, cited_contents):
            missing = [
                reference for reference in claim.references
                if not references_supported((reference,), cited_contents)
            ]
            shown = ", ".join(reference.raw for reference in missing)
            uncited_contents = tuple(evidence.content for evidence in uncited)
            if uncited_contents and references_supported(missing, uncited_contents):
                sources = ", ".join(sorted({
                    evidence.reference.source for evidence in uncited
                    if references_supported(missing, (evidence.content,))
                }))
                violations.append(violation(
                    ViolationKind.UNCITED_REFERENCE,
                    f"the claim states {shown}, which the supplied evidence "
                    f"carries in {sources} — evidence this draft did not cite",
                    claim_index=claim.index,
                ))
            else:
                violations.append(violation(
                    ViolationKind.UNSUPPORTED_REFERENCE,
                    f"the claim states {shown}, which appears in none of the "
                    f"evidence this draft cited",
                    claim_index=claim.index,
                ))

    # 2. the audit's forbidden inferences, when the claim is attributed.
    rule = forbidden_inference(claim, supporting)
    if rule is not None:
        violations.append(violation(
            ViolationKind.FORBIDDEN_INFERENCE,
            f"{rule.detail} (data/audit/README.md §3: \"{rule.basis}\")",
            claim_index=claim.index,
        ))

    # 3. the declared strength of the evidence behind the claim.
    violations.extend(_state_violations(claim, supporting))

    # 4. attribution: is this claim grounded in evidence at all?
    if requires_evidence(claim) and not supporting:
        if guidance and not uncited:
            sources = ", ".join(sorted({ref.source for ref in guidance}))
            violations.append(violation(
                ViolationKind.GUIDANCE_AS_EVIDENCE,
                f"the claim's material is in {sources}, which is "
                f"communication guidance — it says how a supported fact is "
                f"communicated, not that this one is true",
                claim_index=claim.index,
            ))
        else:
            hint = (
                f"; {len(uncited)} supplied evidence item(s) share its "
                f"vocabulary but the draft cited none of them"
                if uncited else ""
            )
            violations.append(violation(
                ViolationKind.NO_CITATION,
                f"the claim asserts something the supplied evidence does not "
                f"support, and the draft attributes it to nothing{hint}",
                claim_index=claim.index,
            ))

    return tuple(violations)
