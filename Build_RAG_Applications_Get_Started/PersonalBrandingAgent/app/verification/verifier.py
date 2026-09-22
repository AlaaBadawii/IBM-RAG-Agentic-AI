"""The gate itself: one draft, one context, one verdict with its evidence.

``PLAN.md`` Step 9 places this deliberately: *"not a pipeline stage — a
function called by both the decision path and the revision loop."* So there is
:func:`verify`, and there is a class for the case where a caller wants to hold
a judge across calls. Neither reads a clock, a store, a network, or anything
the caller did not hand it.

**Order is the contract.** Deterministic checks run first and are
authoritative; the advisory judge is consulted only when they found nothing.
That is not an optimization — it is what makes the judge advisory. A draft
that cites a source the context does not hold is rejected by a string
comparison, and no model's opinion can change that.

**Nothing is looked up.** The only evidence that exists here is
``request.context``. There is no retrieval call, no store handle, no path to
the corpus. "The verifier cannot invent evidence" is therefore not a promise
this module keeps — it is a property of what it is able to do. Labels resolve
against the context's own items, so a label the context never offered is a
finding rather than a lookup that might succeed.

**Failure is not a verdict.** A context that contradicts itself raises
:class:`~app.verification.errors.VerificationError`; it does not return
``PASS`` and it does not return ``REJECTED``. ``PLAN.md`` says verification
failure must never publish, and the distinction between "the gate decided
against this draft" and "the gate could not decide" is one a run's alert has
to be able to make.
"""
from dataclasses import dataclass

from app.context.enums import EvidenceStatus
from app.context.models import ContextItem, PersonalBrandingContext
from app.generation.models import GeneratedPost
from app.logging_config import get_logger, redact
from app.verification.claims import content_terms, split_claims
from app.verification.enums import (
    ClaimVerdict,
    Severity,
    VerificationFailureCategory,
    VerificationOutcome,
    ViolationKind,
)
from app.verification.errors import SupportJudgeUnavailable, VerificationError
from app.verification.models import (
    Claim,
    ClaimVerification,
    EvidenceReference,
    SuppliedEvidence,
    VerificationRequest,
    VerificationResult,
    Violation,
)
from app.verification.policy import check_claim, requires_evidence, violation
from app.verification.support import JudgedClaim, JudgementRequest, map_verdicts

__all__ = ["EvidenceVerifier", "verify"]

logger = get_logger(__name__)


@dataclass(frozen=True)
class _Candidate:
    """A piece of supplied evidence, with its content terms precomputed.

    The terms are what a claim is matched against, and computing them once per
    item rather than once per (claim, item) pair is the only reason this
    exists. It never escapes this module: the checks receive
    :class:`~app.verification.models.SuppliedEvidence`.
    """

    evidence: SuppliedEvidence
    terms: frozenset[str]


class EvidenceVerifier:
    """Runs the gate. Holds a judge, and nothing else."""

    def __init__(self, judge=None):
        """
        Args:
            judge: an advisory
                :class:`~app.verification.support.SupportJudge`, or ``None``
                for deterministic-only verification. ``None`` is not a
                failure: ``PLAN.md`` allows the run to proceed on the
                deterministic gates alone, and the result says so
                (``degraded=True``) rather than implying the advisory layer
                agreed.
        """
        self._judge = judge

    # -- the one entry point -------------------------------------------------

    def verify(self, request: VerificationRequest) -> VerificationResult:
        """Verify one draft against one context.

        Raises:
            VerificationError: verification produced no verdict — the supplied
                context is unusable, or the advisory judge misbehaved. Never
                for a draft that merely failed: that is a result, and it says
                which of ``REVISION_REQUIRED`` or ``REJECTED`` it is.
        """
        post = request.post
        context = request.context
        violations: list[Violation] = []

        items = context.evidence_items()
        self._reject_unusable_context(context, items)

        resolved, uncited_pool = self._resolve_citations(post, context, violations)
        if not items:
            violations.append(violation(
                ViolationKind.EVIDENCE_INSUFFICIENT,
                f"the supplied context holds no evidence to verify against "
                f"(evidence status: {context.evidence_status.value})",
            ))
        if not (post.content or "").strip():
            violations.append(violation(
                ViolationKind.EMPTY_DRAFT,
                "the draft carries no text to verify",
            ))

        guidance = self._guidance(context)
        claims = split_claims(post.content)
        per_claim: dict[int, list[Violation]] = {}
        supporting_by_claim: dict[int, tuple[EvidenceReference, ...]] = {}
        for claim in claims:
            supporting = tuple(
                candidate for candidate in resolved
                if self._overlaps(claim, candidate)
            )
            supporting_by_claim[claim.index] = tuple(
                candidate.evidence.reference for candidate in supporting
            )
            per_claim[claim.index] = list(check_claim(
                claim,
                cited=tuple(
                    candidate.evidence for candidate in resolved
                ),
                supporting=tuple(
                    candidate.evidence for candidate in supporting
                ),
                uncited=tuple(
                    candidate.evidence for candidate in uncited_pool
                    if self._overlaps(claim, candidate)
                ),
                guidance=tuple(
                    candidate.evidence.reference for candidate in guidance
                    if self._overlaps(claim, candidate)
                ),
            ))

        post_level = [v for v in violations if v.claim_index is None]
        degraded, note, judge_name, judge_version = self._consult_judge(
            claims, per_claim, resolved
        )

        claim_results = tuple(
            self._claim_result(
                claim,
                per_claim.get(claim.index, []),
                supporting_by_claim.get(claim.index, ()),
            )
            for claim in claims
        )
        outcome = self._outcome(tuple(post_level), claim_results)

        result = VerificationResult(
            outcome=outcome,
            claims=claim_results,
            violations=tuple(post_level),
            evidence=tuple(
                candidate.evidence.reference for candidate in resolved
            ),
            unresolved=tuple(post.unresolved_labels),
            evidence_status=context.evidence_status,
            degraded=degraded,
            advisory_note=note,
            judge=judge_name,
            judge_prompt_version=judge_version,
        )
        logger.info(
            "verified a draft: %s (%d claim(s), %d finding(s), degraded=%s)",
            result.outcome.value, len(claim_results),
            len(result.all_violations), degraded,
        )
        return result

    # -- deterministic checks ------------------------------------------------

    @staticmethod
    def _reject_unusable_context(context: PersonalBrandingContext,
                                 items: tuple[ContextItem, ...]) -> None:
        """Refuse a context that contradicts itself.

        ``SUFFICIENT`` with nothing in it is not "no evidence" — that is
        ``INSUFFICIENT``, and it is a verdict this layer can return. It is a
        context whose own report cannot be true, and verifying against it would
        mean choosing which half to believe.

        Raises:
            VerificationError: category ``CONTEXT_UNUSABLE``.
        """
        if items or context.evidence_status is not EvidenceStatus.SUFFICIENT:
            return
        raise VerificationError(
            "the supplied context reports SUFFICIENT evidence but holds no "
            "evidence items; there is nothing to verify against",
            category=VerificationFailureCategory.CONTEXT_UNUSABLE,
        )

    @staticmethod
    def _resolve_citations(
        post: GeneratedPost,
        context: PersonalBrandingContext,
        violations: list[Violation],
    ) -> tuple[tuple[_Candidate, ...], tuple[_Candidate, ...]]:
        """Match the draft's citations to the context, by identity.

        Resolution is by ``(source, chunk_id)`` and not by label, because a
        label is only meaningful to the prompt that issued it: generation may
        have written from a subset of the context, in which case the same label
        means different items to the draft and to this context. Identity is
        what both sides can agree on, and it is also what makes an invented
        citation impossible to miss — it will not be in the context.

        Returns:
            ``(cited, uncited)`` — the supplied evidence the draft pointed at,
            and the supplied evidence it did not. Both are candidates for the
            per-claim checks, which is how an under-cited claim is told from an
            unsupported one.
        """
        index = EvidenceVerifier._context_index(context)
        cited: list[_Candidate] = []
        cited_ids: set[tuple[str, str]] = set()
        for citation in post.citations:
            identity = (citation.source, citation.chunk_id)
            entry = index.get(identity)
            if entry is None:
                violations.append(violation(
                    ViolationKind.CITATION_NOT_IN_CONTEXT,
                    f"the draft cites {citation.label} ({citation.source}), "
                    f"which the supplied context does not hold",
                ))
                continue
            reference, content = entry
            cited_ids.add(identity)
            cited.append(_Candidate(
                evidence=SuppliedEvidence(
                    reference=EvidenceVerifier._labelled(reference, citation.label),
                    content=content,
                ),
                terms=content_terms(content),
            ))

        for label in post.unresolved_labels:
            violations.append(violation(
                ViolationKind.CITATION_NOT_IN_CONTEXT,
                f"the draft used the label {label}, which the supplied "
                f"evidence never offered",
            ))

        uncited = tuple(
            _Candidate(
                evidence=SuppliedEvidence(reference=reference, content=content),
                terms=content_terms(content),
            )
            for identity, (reference, content) in index.items()
            if identity not in cited_ids
        )
        return tuple(cited), uncited

    @staticmethod
    def _context_index(context: PersonalBrandingContext
                       ) -> dict[tuple[str, str], tuple[EvidenceReference, str]]:
        """``(source, chunk_id)`` → reference and content, for evidence only.

        Guidance is excluded on purpose: it is not evidence, so a citation that
        resolves to it must not resolve at all.
        """
        index: dict[tuple[str, str], tuple[EvidenceReference, str]] = {}
        for section in context.evidence_sections:
            for item in section.items:
                reference = EvidenceReference.from_item(item, section=section.name)
                index.setdefault(reference.identity, (reference, item.content))
        return index

    @staticmethod
    def _labelled(reference: EvidenceReference, label: str) -> EvidenceReference:
        """The same reference, carrying the label the draft used for it."""
        return EvidenceReference(
            source=reference.source,
            chunk_id=reference.chunk_id,
            evidence_state=reference.evidence_state,
            section=reference.section,
            category=reference.category,
            document_type=reference.document_type,
            label=label,
        )

    @staticmethod
    def _guidance(context: PersonalBrandingContext) -> tuple[_Candidate, ...]:
        """Positioning, vision and voice — carried so a claim can be traced to
        them. Never evidence; see :mod:`app.verification.policy`."""
        return tuple(
            _Candidate(
                evidence=SuppliedEvidence(
                    reference=EvidenceReference.from_item(
                        item, section=section.name
                    ),
                    content=item.content,
                ),
                terms=content_terms(item.content),
            )
            for section in context.guidance_sections
            for item in section.items
        )

    @staticmethod
    def _overlaps(claim: Claim, candidate: _Candidate) -> bool:
        """Whether the claim's vocabulary comes from this text at all.

        One shared content term is enough. The alternative — a threshold, a
        score, a ratio — is a number nobody can check, and getting it wrong in
        the strict direction makes every draft fail. This decides only *what a
        claim is attributed to*; whether the attribution is good enough is the
        advisory judge's question, and this module never pretends to answer it.
        """
        return bool(content_terms(claim.text) & candidate.terms)

    # -- the advisory layer --------------------------------------------------

    def _consult_judge(
        self,
        claims: tuple[Claim, ...],
        per_claim: dict[int, list[Violation]],
        resolved: tuple[_Candidate, ...],
    ) -> tuple[bool, str, str, str | None]:
        """Ask the judge about the claims the deterministic checks passed.

        ``PLAN.md`` runs the advisory checks only after the deterministic ones,
        so a claim that already carries a finding is not sent: it would spend a
        model call to learn something a string comparison established. What is
        sent is every claim that asserts something, is attributed to evidence,
        and is otherwise clean — which is exactly the set where a paraphrase or
        an overstatement could still be hiding.

        Returns:
            ``(degraded, note, judge_name, judge_prompt_version)``.
        """
        if self._judge is None:
            return True, "no advisory judge is configured", "none", None

        judge_name = getattr(self._judge, "name", type(self._judge).__name__)
        judge_version = getattr(self._judge, "prompt_version", None)
        subjects = tuple(
            JudgedClaim(
                index=claim.index,
                text=claim.text,
                evidence=tuple(
                    candidate.evidence for candidate in resolved
                    if self._overlaps(claim, candidate)
                ),
            )
            for claim in claims
            if not per_claim.get(claim.index)
            and requires_evidence(claim)
            and any(self._overlaps(claim, candidate) for candidate in resolved)
        )
        if not subjects:
            return (
                False,
                "no claim required the advisory check",
                judge_name,
                judge_version,
            )

        request = JudgementRequest(
            claims=subjects,
            prompt_version=judge_version or "",
        )
        try:
            verdicts = self._judge.judge(request)
        except SupportJudgeUnavailable as exc:
            return True, redact(str(exc)), judge_name, judge_version
        except VerificationError:
            raise
        except Exception as exc:  # noqa: BLE001 - a judge that misbehaved
            # Fail closed. A judge that crashed *while judging* may have had an
            # objection, and reporting a pass in its absence is the one thing
            # that must not happen — which is why this is a failure and the
            # branch above is not.
            raise VerificationError(
                f"the support judge raised {type(exc).__name__} while judging: "
                f"{redact(str(exc))}",
                category=VerificationFailureCategory.JUDGE_FAILURE,
            ) from exc

        # An answer about a claim that was not asked, or two answers about one
        # claim, is a defect rather than an absence: the judge answered, and
        # its answer is unusable. ``map_verdicts`` raises ``VerificationError``
        # and this does not catch it — a model whose numbering is wrong may
        # have had an objection, and dropping it would be failing open.
        mapped = map_verdicts(request, tuple(verdicts))
        for subject in subjects:
            verdict = mapped.get(subject.index)
            if verdict is None or verdict.supported:
                continue
            per_claim[subject.index].append(violation(
                ViolationKind.ADVISORY_UNSUPPORTED,
                verdict.reason or (
                    "the support judge read this claim against its evidence "
                    "and judged it unsupported"
                ),
                claim_index=subject.index,
                advisory=True,
            ))
        return False, "", judge_name, judge_version

    # -- assembling the result ----------------------------------------------

    @staticmethod
    def _claim_result(claim: Claim,
                      violations: list[Violation],
                      supporting: tuple[EvidenceReference, ...],
                      ) -> ClaimVerification:
        """One claim's verdict, derived from the severities of its findings.

        The supporting references are carried onto the claim, not just onto the
        result: "this sentence is supported" is only checkable if a reader can
        see *what* supports it, and a claim whose provenance is only recorded
        at the post level is a claim nothing can be traced back through.
        """
        if any(v.severity is Severity.REJECT for v in violations):
            verdict = ClaimVerdict.REJECTED
        elif violations:
            verdict = ClaimVerdict.UNSUPPORTED
        else:
            verdict = ClaimVerdict.SUPPORTED
        return ClaimVerification(
            claim=claim,
            verdict=verdict,
            violations=tuple(violations),
            supporting=supporting,
        )

    @staticmethod
    def _outcome(post_level: tuple[Violation, ...],
                 claims: tuple[ClaimVerification, ...]) -> VerificationOutcome:
        """The one place an outcome is decided.

        ``PASS`` needs both halves clean, and it is unreachable from a finding
        by construction — :meth:`VerificationResult.__post_init__` refuses to
        build a passing result that carries one, so a bug here is an exception
        rather than a post that publishes itself.
        """
        found = list(post_level) + [
            violation_ for claim in claims for violation_ in claim.violations
        ]
        if any(v.severity is Severity.REJECT for v in found):
            return VerificationOutcome.REJECTED
        if found:
            return VerificationOutcome.REVISION_REQUIRED
        return VerificationOutcome.PASS


def verify(post: GeneratedPost, context: PersonalBrandingContext, *,
           judge=None) -> VerificationResult:
    """Verify one draft against one context.

    ``PLAN.md`` Step 9 calls the gate *a function*, so the ordinary call is a
    function. It is a thin one: the class above holds an injected judge for a
    caller that verifies repeatedly, and this builds one per call for the
    caller that does not.
    """
    return EvidenceVerifier(judge=judge).verify(
        VerificationRequest(post=post, context=context)
    )
