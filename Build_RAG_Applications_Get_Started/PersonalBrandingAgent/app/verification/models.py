"""The shape of a verification result (``PLAN.md`` Step 9).

``PLAN.md`` requires the gate to produce ``PASS``, ``REVISE`` or ``REJECT``,
and it requires the deterministic checks to be claim-level. A single boolean
satisfies neither: "the post is not supported" cannot tell Step 10's revision
loop *what* to change, and it cannot tell an audit which sentence was the
problem. So the result is a structure, and the assertion that makes it
trustworthy is in :meth:`VerificationResult.__post_init__` — **a passing result
that carries a finding cannot be constructed at all.**

Three absences are deliberate:

* **No evidence content.** :class:`EvidenceReference` carries provenance —
  source, chunk id, evidence state, section — and not the text. A reference is
  a pointer back into the corpus; copying the corpus here would create a second
  copy of the evidence, and the one thing that must never happen is generated
  text being read back as evidence. The advisory judge is given the text it
  needs (:class:`SuppliedEvidence`) and nothing here is built from what it
  returns.
* **No confidence score.** ``PLAN.md`` Step 9's deterministic checks either
  pass or fail, and the advisory layer answers a boolean with a reason. A score
  would be a precise-looking number nothing can verify.
* **No clock and no secrets.** ``to_record()`` is what gets persisted with the
  publication record, so it holds only what the checks produced and the judge
  that produced them. Nothing in it is read from the environment.
"""
from dataclasses import dataclass
from typing import Any

from app.context.enums import EvidenceStatus
from app.context.models import ContextItem, PersonalBrandingContext
from app.generation.models import GeneratedPost
from app.verification.enums import (
    ClaimVerdict,
    Severity,
    VerificationOutcome,
    ViolationKind,
)

__all__ = [
    "Claim",
    "ClaimVerification",
    "EvidenceReference",
    "Reference",
    "SuppliedEvidence",
    "VerificationRequest",
    "VerificationResult",
    "Violation",
]


@dataclass(frozen=True)
class Reference:
    """One exact factual token in a claim.

    ``raw`` is what the draft printed and ``normalized`` is what the evidence
    is searched for; both are kept because a report has to show the first and a
    check has to use the second.
    """

    raw: str
    normalized: str


@dataclass(frozen=True)
class Claim:
    """One sentence of the draft, numbered, with its exact references.

    Built by :func:`app.verification.claims.split_claims`, which is also what
    guarantees the numbering is complete: every non-empty sentence is a claim,
    so no sentence can be skipped by accident.
    """

    index: int
    text: str
    references: tuple[Reference, ...] = ()


@dataclass(frozen=True)
class EvidenceReference:
    """A pointer back to one piece of supplied evidence.

    The fields the roadmap requires a verified claim to remain attributable
    through — ``source``, ``chunk_id``, ``evidence_state`` — plus the section
    and category the context placed it in, because the policy checks ask
    *where* evidence came from as much as *how strong* it is.

    ``content`` is deliberately absent: this is a reference, not a copy. See
    the module docstring.
    """

    source: str
    chunk_id: str
    evidence_state: str | None
    section: str
    category: str = ""
    document_type: str | None = None
    label: str | None = None
    """The label the draft used for this evidence, when the draft cited it.
    ``None`` for evidence that is available but uncited."""

    @classmethod
    def from_item(cls, item: ContextItem, *, section: str,
                  label: str | None = None) -> "EvidenceReference":
        return cls(
            source=item.source,
            chunk_id=item.chunk_id,
            evidence_state=item.evidence_state,
            section=section,
            category=item.category,
            document_type=item.document_type,
            label=label,
        )

    @property
    def identity(self) -> tuple[str, str]:
        """``(source, chunk_id)`` — how a citation is resolved against the
        context, and how two references to the same chunk are recognised."""
        return (self.source, self.chunk_id)


@dataclass(frozen=True)
class SuppliedEvidence:
    """A reference together with the text it points at.

    Exists for the two checks that need to *read* the evidence: the exact
    reference lookup and the advisory judgement. It is an input to a check,
    never a field of :class:`VerificationResult`, so the text a draft was
    verified against does not travel onward as though it were an output.
    """

    reference: EvidenceReference
    content: str


@dataclass(frozen=True)
class Violation:
    """One finding, attributed to a claim when it belongs to one."""

    kind: ViolationKind
    severity: Severity
    detail: str
    claim_index: int | None = None
    advisory: bool = False
    """True when the finding came from the advisory judge rather than from a
    deterministic check. Both are reported; only one of them is a gate."""

    @property
    def is_rejecting(self) -> bool:
        return self.severity is Severity.REJECT


@dataclass(frozen=True)
class ClaimVerification:
    """What the gate concluded about one sentence, and on what evidence."""

    claim: Claim
    verdict: ClaimVerdict
    violations: tuple[Violation, ...] = ()
    supporting: tuple[EvidenceReference, ...] = ()
    """The supplied evidence this claim's material was found in — the
    references that resolved *and* share content terms with the claim. Empty
    is not proof of unsupportedness on its own; it is what a reader checks
    first, and what the advisory judge is asked about."""

    @property
    def is_supported(self) -> bool:
        return self.verdict is ClaimVerdict.SUPPORTED

    @property
    def is_rejected(self) -> bool:
        return self.verdict is ClaimVerdict.REJECTED

    @property
    def detail(self) -> str:
        """The first finding, for a one-line report. ``""`` when supported."""
        return self.violations[0].detail if self.violations else ""


@dataclass(frozen=True)
class VerificationRequest:
    """One verification: a draft, and the evidence it is to be checked against.

    The context is required and is the only evidence that exists as far as the
    gate is concerned. Nothing is looked up: no retrieval, no store, no
    network. That is what makes "the verifier cannot invent evidence" a
    property of the code rather than a promise — there is nothing here to
    invent it *from*.
    """

    post: GeneratedPost
    context: PersonalBrandingContext


@dataclass(frozen=True)
class VerificationResult:
    """The gate's answer: an outcome, and everything behind it.

    Constructed by :class:`app.verification.verifier.EvidenceVerifier`, and
    validated here — the invariants below are what make ``PASS`` mean
    something, because a caller that only reads ``outcome`` cannot be misled by
    a result that disagrees with its own findings.
    """

    outcome: VerificationOutcome
    claims: tuple[ClaimVerification, ...] = ()
    violations: tuple[Violation, ...] = ()
    """Post-level findings: the draft as a whole, rather than one sentence."""

    evidence: tuple[EvidenceReference, ...] = ()
    """Every supplied evidence item the draft cited, resolved against the
    context. Provenance for the audit record; never the evidence itself."""

    unresolved: tuple[str, ...] = ()
    """Labels the draft named that the supplied context does not hold."""

    evidence_status: EvidenceStatus = EvidenceStatus.INSUFFICIENT
    degraded: bool = False
    """True when the advisory layer could not be consulted, so the verdict
    rests on the deterministic checks alone. ``PLAN.md`` Step 9 permits that
    mode; it requires it to be visible, which is what this field is for."""

    advisory_note: str = ""
    judge: str = "none"
    judge_prompt_version: str | None = None

    def __post_init__(self) -> None:
        all_violations = self._all_violations()
        rejecting = [v for v in all_violations if v.is_rejecting]

        if self.outcome is VerificationOutcome.PASS:
            if all_violations:
                raise ValueError(
                    "a passing verification cannot carry a finding: "
                    f"{[v.kind.value for v in all_violations]}"
                )
            unsupported = [
                c for c in self.claims if not c.is_supported
            ]
            if unsupported:
                raise ValueError(
                    "a passing verification cannot carry an unsupported "
                    "claim: " + ", ".join(str(c.claim.index) for c in unsupported)
                )
        elif self.outcome is VerificationOutcome.REJECTED:
            if not rejecting:
                raise ValueError(
                    "a rejection must name a finding that cannot be revised"
                )
        elif self.outcome is VerificationOutcome.REVISION_REQUIRED:
            if not all_violations:
                raise ValueError(
                    "a revision requirement must name what has to change"
                )
            if rejecting:
                raise ValueError(
                    "a draft with an unverifiable finding is rejected, not "
                    "sent back for revision: "
                    f"{[v.kind.value for v in rejecting]}"
                )

    # -- reading it ---------------------------------------------------------

    def _all_violations(self) -> tuple[Violation, ...]:
        return self.violations + tuple(
            v for claim in self.claims for v in claim.violations
        )

    @property
    def is_publishable(self) -> bool:
        """True only for a pass. The one question the publish path asks."""
        return self.outcome is VerificationOutcome.PASS

    @property
    def fully_verified(self) -> bool:
        """A pass with the advisory layer actually consulted.

        Distinct from :attr:`is_publishable` because ``PLAN.md`` Step 9 allows
        a degraded pass to proceed while requiring the mode to be recorded —
        a caller that wants the stronger guarantee can ask for it here, and a
        caller that accepts the weaker one can see exactly what it accepted.
        """
        return self.is_publishable and not self.degraded

    @property
    def all_violations(self) -> tuple[Violation, ...]:
        return self._all_violations()

    @property
    def rejected_claims(self) -> tuple[ClaimVerification, ...]:
        return tuple(c for c in self.claims if c.is_rejected)

    @property
    def unsupported_claims(self) -> tuple[ClaimVerification, ...]:
        return tuple(
            c for c in self.claims if c.verdict is ClaimVerdict.UNSUPPORTED
        )

    def revision_notes(self) -> tuple[str, ...]:
        """What a revision loop has to change, one line per revisable finding.

        Step 9 does not run the loop (that is Step 10) and does not count the
        attempts (that is the loop's limit). What it can do is say precisely
        what is wrong, which is the input the loop needs and the only part of
        it that can be verified here.
        """
        notes = []
        for violation in self.all_violations:
            if violation.is_rejecting:
                continue
            where = (
                f"claim {violation.claim_index}"
                if violation.claim_index is not None else "the draft"
            )
            notes.append(f"{where}: {violation.detail}")
        return tuple(notes)

    def to_record(self) -> dict[str, Any]:
        """The persistable form, for the publication record (Step 11 writes it).

        Plain JSON-compatible values, no clock, no environment, no secret: the
        outcome and every finding behind it, the evidence the draft cited by
        provenance rather than by text, and the judge that produced the
        advisory half.
        """
        return {
            "outcome": self.outcome.value,
            "evidence_status": self.evidence_status.value,
            "degraded": self.degraded,
            "advisory_note": self.advisory_note,
            "judge": self.judge,
            "judge_prompt_version": self.judge_prompt_version,
            "unresolved_labels": list(self.unresolved),
            "violations": [self._violation_record(v) for v in self.violations],
            "evidence": [
                {
                    "label": reference.label,
                    "source": reference.source,
                    "chunk_id": reference.chunk_id,
                    "evidence_state": reference.evidence_state,
                    "section": reference.section,
                }
                for reference in self.evidence
            ],
            "claims": [
                {
                    "index": claim.claim.index,
                    "text": claim.claim.text,
                    "verdict": claim.verdict.value,
                    "references": [r.raw for r in claim.claim.references],
                    "supporting": [
                        {
                            "source": reference.source,
                            "chunk_id": reference.chunk_id,
                            "evidence_state": reference.evidence_state,
                            "section": reference.section,
                        }
                        for reference in claim.supporting
                    ],
                    "violations": [
                        self._violation_record(v) for v in claim.violations
                    ],
                }
                for claim in self.claims
            ],
            "revision_notes": list(self.revision_notes()),
        }

    @staticmethod
    def _violation_record(violation: Violation) -> dict[str, Any]:
        return {
            "kind": violation.kind.value,
            "severity": violation.severity.value,
            "detail": violation.detail,
            "claim_index": violation.claim_index,
            "advisory": violation.advisory,
        }
