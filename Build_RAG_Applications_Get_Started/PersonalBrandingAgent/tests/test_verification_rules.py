"""Step 9: the rules a draft is held to, and the severities that gate them.

``PLAN.md`` calls the deterministic checks authoritative, which makes this file
the contract for what "authoritative" means. Every test here is a string in and
a verdict out: no context, no gate, no model. What the gate does with these
findings is ``tests/test_verification_verifier.py``.

The corpus's own policy is what is under test. ``data/audit/README.md`` §3
names five inferences an audit must never make, and the milestone for this step
is that the documented ones are caught by fixtures — so each rule gets a case
that fires it and a case that shows it does not fire on evidence that *does*
carry the claim.
"""
import pytest

from app.retrieval.bm25 import tokenize as retrieval_tokenize
from app.verification import (
    MAX_REVISION_ATTEMPTS,
    Claim,
    ClaimVerdict,
    EvidenceReference,
    RevisionDecision,
    Severity,
    SuppliedEvidence,
    VerificationResult,
    Violation,
    ViolationKind,
)
from app.verification.claims import (
    content_terms,
    extract_references,
    normalize_reference,
    split_claims,
    tokenize,
)
from app.verification.enums import VerificationOutcome
from app.verification.policy import (
    FORBIDDEN_INFERENCES,
    UNUSABLE_EVIDENCE_STATES,
    VIOLATION_SEVERITY,
    WEAK_EVIDENCE_STATES,
    check_claim,
    forbidden_inference,
    references_supported,
    requires_evidence,
    severity_for,
)
from app.verification.revision import revision_decision as decide

# --------------------------------------------------------------- fixtures ---

FIXTURE_TEXT = "Built a shipment API with FastAPI and SQLAlchemy."


def reference(source: str = "evidence/backend/fastapi.md",
              chunk_id: str = "a1b2c3:0",
              state: str | None = "VERIFIED",
              section: str = "evidence",
              label: str | None = None) -> EvidenceReference:
    return EvidenceReference(
        source=source, chunk_id=chunk_id, evidence_state=state,
        section=section, category=section, label=label,
    )


def supplied(content: str, **kwargs) -> SuppliedEvidence:
    return SuppliedEvidence(reference=reference(**kwargs), content=content)


def claim(text: str) -> Claim:
    claims = split_claims(text)
    assert len(claims) == 1, f"expected one claim from {text!r}"
    return claims[0]


def kinds(violations) -> set[ViolationKind]:
    return {v.kind for v in violations}


def check(text: str, *, cited=(), supporting=(), uncited=(), guidance=()):
    """Run every deterministic check on one sentence.

    ``cited`` defaults to whatever was passed as ``supporting``, because most
    cases here are about one claim and one piece of evidence; the reference
    check's wider view has its own tests.
    """
    return check_claim(
        claim(text),
        cited=tuple(cited) or tuple(supporting),
        supporting=tuple(supporting),
        uncited=tuple(uncited),
        guidance=tuple(guidance),
    )


# ------------------------------------------------------------- splitting ---

def test_every_non_empty_sentence_becomes_a_numbered_claim():
    claims = split_claims("First sentence. Second sentence! Third one?")

    assert [c.index for c in claims] == [1, 2, 3]
    assert claims[1].text == "Second sentence!"


def test_newlines_and_list_markers_split_claims():
    claims = split_claims("- Built the API\n- Wrote the migrations")

    assert [c.text for c in claims] == ["Built the API", "Wrote the migrations"]


def test_an_empty_draft_has_no_claims():
    assert split_claims("") == ()
    assert split_claims("   \n\n  ") == ()


def test_claim_numbering_is_complete_so_no_sentence_can_be_skipped():
    claims = split_claims("One. Two. Three. Four.")

    assert [c.index for c in claims] == [1, 2, 3, 4]


# ----------------------------------------------------------- references ---

@pytest.mark.parametrize("text, expected", [
    ("Reduced latency by 40%.", {"40%"}),
    ("Shipped v1.4.2 of the tool.", {"1.4.2"}),
    ("Started in 2024.", {"2024"}),
    ("Waited 3 months.", {"3months"}),
    ("Uses 10x fewer tokens.", {"10x"}),
    ("No numbers here at all.", set()),
])
def test_exact_factual_references_are_extracted(text, expected):
    found = {r.normalized for r in extract_references(text)}

    assert expected <= found


def test_a_reference_is_kept_as_written_and_as_compared():
    (found,) = extract_references("Improved throughput by 40 %.")

    assert found.raw == "40 %"
    assert found.normalized == "40%"


def test_references_are_deduplicated_by_their_comparable_form():
    found = extract_references("In 2024, and again in 2024.")

    assert len(found) == 1


@pytest.mark.parametrize("raw, normalized", [
    ("40 %", "40%"),
    ("1,000 ms", "1000ms"),
    ("2024", "2024"),
])
def test_normalization_is_lowercase_without_spaces_or_commas(raw, normalized):
    assert normalize_reference(raw) == normalized


def test_a_reference_present_in_the_evidence_is_supported():
    references = extract_references("Cut latency by 40%.")

    assert references_supported(references, ("We cut latency by 40% overall.",))


def test_a_reference_absent_from_the_evidence_is_not_supported():
    references = extract_references("Cut latency by 40%.")

    assert not references_supported(references, ("We cut latency considerably.",))


def test_a_reference_does_not_match_across_a_word_boundary():
    references = extract_references("Started in 2024.")

    assert not references_supported(references, ("Released in 2023, 40% faster.",))


def test_a_reference_written_with_its_own_separator_still_matches():
    references = extract_references("Waited 1,000 ms for a response.")

    assert references_supported(references, ("The trace shows 1,000 ms.",))
    assert not references_supported(references, ("The trace shows 2000 ms.",))


# ------------------------------------------------------------ requires ---

@pytest.mark.parametrize("text", [
    "I built a retrieval pipeline.",
    "My team shipped the migration.",
    "Reduced latency by 40%.",
    "Completed the IBM RAG course.",
])
def test_personal_and_factual_sentences_require_evidence(text):
    assert requires_evidence(claim(text))


@pytest.mark.parametrize("text", [
    "What if the tooling changed?",
    "The takeaway matters more than the tool.",
])
def test_a_question_or_an_impersonal_sentence_requires_nothing(text):
    assert not requires_evidence(claim(text))


# ------------------------------------------------------------ severities ---

def test_every_violation_kind_declares_a_severity():
    missing = [kind for kind in ViolationKind if kind not in VIOLATION_SEVERITY]

    assert not missing, f"kinds without a severity: {missing}"
    assert severity_for(ViolationKind.CITATION_NOT_IN_CONTEXT) is Severity.REJECT


def test_an_undeclared_severity_is_a_loud_failure_not_a_default():
    VIOLATION_SEVERITY.pop(ViolationKind.EMPTY_DRAFT, None)
    try:
        with pytest.raises(KeyError):
            severity_for(ViolationKind.EMPTY_DRAFT)
    finally:
        VIOLATION_SEVERITY[ViolationKind.EMPTY_DRAFT] = Severity.REJECT


# ------------------------------------------------- what a clean claim is ---

def test_a_supported_claim_produces_no_finding():
    assert check(
        "Built a shipment API with FastAPI and SQLAlchemy.",
        supporting=[supplied(FIXTURE_TEXT)],
    ) == ()


def test_a_sentence_that_asserts_nothing_about_the_author_passes_uncited():
    assert check("Here is what changed.", supporting=[]) == ()


# ------------------------------------------------------------ citations ---

def test_a_claim_attributed_to_nothing_is_uncited():
    found = check("I built a shipment API with FastAPI and SQLAlchemy.")

    assert kinds(found) == {ViolationKind.NO_CITATION}
    assert found[0].severity is Severity.REVISABLE
    assert found[0].claim_index == 1


def test_an_uncited_claim_says_when_the_evidence_was_supplied_but_unused():
    found = check(
        "I built a shipment API with FastAPI and SQLAlchemy.",
        uncited=[supplied(FIXTURE_TEXT)],
    )

    assert kinds(found) == {ViolationKind.NO_CITATION}
    assert "cited none of them" in found[0].detail


# ------------------------------------------------- guidance is not evidence ---

def test_positioning_cannot_satisfy_evidence():
    found = check(
        "I am positioned as a backend engineer who ships.",
        guidance=[reference(source="data/public_positioning/portfolio.md",
                            section="public_positioning")],
    )

    assert kinds(found) == {ViolationKind.GUIDANCE_AS_EVIDENCE}
    assert found[0].severity is Severity.REVISABLE


def test_guidance_does_not_get_blamed_when_evidence_is_also_uncited():
    found = check(
        "I built a shipment API with FastAPI.",
        uncited=[supplied(FIXTURE_TEXT)],
        guidance=[reference(source="data/public_positioning/portfolio.md",
                            section="public_positioning")],
    )

    assert kinds(found) == {ViolationKind.NO_CITATION}


def test_a_claim_grounded_in_evidence_is_not_blamed_on_guidance():
    found = check(
        "Built a shipment API with FastAPI and SQLAlchemy.",
        supporting=[supplied(FIXTURE_TEXT)],
        guidance=[reference(source="data/writing_style/style.md",
                            section="writing_style")],
    )

    assert found == ()


# ---------------------------------------------------------- evidence state ---

@pytest.mark.parametrize("state", sorted(UNUSABLE_EVIDENCE_STATES))
def test_evidence_that_declares_itself_unusable_cannot_carry_a_claim(state):
    found = check(
        "Built a shipment API with FastAPI and SQLAlchemy.",
        supporting=[supplied(FIXTURE_TEXT, state=state)],
    )

    assert kinds(found) == {ViolationKind.EVIDENCE_STATE_TOO_WEAK}
    assert found[0].severity is Severity.REJECT


def test_evidence_of_learning_cannot_carry_a_claim_that_it_happened():
    found = check(
        "Built a shipment API with FastAPI and SQLAlchemy.",
        supporting=[supplied(FIXTURE_TEXT, state="LEARNING")],
    )

    assert kinds(found) == {ViolationKind.EVIDENCE_STATE_TOO_WEAK}
    assert "LEARNING" in found[0].detail


def test_a_claim_that_admits_learning_may_rest_on_learning_evidence():
    found = check(
        "I am learning FastAPI and SQLAlchemy by building a shipment API.",
        supporting=[supplied(FIXTURE_TEXT, state="LEARNING")],
    )

    assert found == ()


def test_an_aspiration_may_rest_on_aspirational_evidence():
    found = check(
        "My next goal is to build a shipment API.",
        supporting=[supplied(FIXTURE_TEXT, state="ASPIRATIONAL")],
    )

    assert found == ()


def test_undeclared_evidence_is_usable_and_keeps_its_absent_state():
    found = check(
        "Built a shipment API with FastAPI and SQLAlchemy.",
        supporting=[supplied(FIXTURE_TEXT, state=None)],
    )

    assert found == ()


def test_weak_and_unusable_states_do_not_overlap():
    assert not (WEAK_EVIDENCE_STATES & UNUSABLE_EVIDENCE_STATES)


# ------------------------------------------------------ exact references ---

def test_a_fabricated_reference_is_rejected():
    found = check(
        "I cut API latency by 40% with caching.",
        supporting=[supplied("The API returns shipments. Latency was not "
                             "measured.")],
    )

    assert ViolationKind.UNSUPPORTED_REFERENCE in kinds(found)
    assert severity_for(ViolationKind.UNSUPPORTED_REFERENCE) is Severity.REJECT
    assert "40%" in found[0].detail


def test_a_reference_the_evidence_carries_but_the_draft_did_not_cite():
    found = check(
        "I cut API latency by 40% with caching.",
        cited=[supplied("The API returns shipments.")],
        uncited=[supplied("Caching cut API latency by 40%.",
                          chunk_id="b2c3d4:1")],
    )

    assert ViolationKind.UNCITED_REFERENCE in kinds(found)
    assert severity_for(ViolationKind.UNCITED_REFERENCE) is Severity.REVISABLE
    assert "did not cite" in found[0].detail


def test_a_reference_present_in_the_cited_evidence_passes():
    found = check(
        "I cut API latency by 40% with caching.",
        supporting=[supplied("Caching cut API latency by 40% on the API.")],
    )

    assert ViolationKind.UNSUPPORTED_REFERENCE not in kinds(found)
    assert ViolationKind.UNCITED_REFERENCE not in kinds(found)


def test_a_reference_is_not_checked_when_nothing_was_cited():
    found = check("I cut API latency by 40% with caching.")

    assert kinds(found) == {ViolationKind.NO_CITATION}


def test_a_reference_is_checked_against_everything_the_draft_cited():
    found = check(
        "I cut API latency by 40% with caching.",
        cited=[supplied("The API returns shipments.")],
    )

    assert ViolationKind.UNSUPPORTED_REFERENCE in kinds(found)


# ------------------------------------------------- forbidden inferences ---

def test_the_audit_rules_are_transcribed_with_their_source_line():
    bases = {rule.basis for rule in FORBIDDEN_INFERENCES}

    assert "never infer professional experience from coursework" in bases
    assert "never infer production experience from a local project" in bases
    assert "never infer deployment from configuration alone" in bases
    assert "never infer mastery from course completion" in bases
    assert (
        "never infer employment from a portfolio entry without supporting "
        "evidence" in bases
    )


@pytest.mark.parametrize("text, content, source, section", [
    (
        "My professional experience includes RAG applications.",
        "Completed the IBM RAG applications course.",
        "certificates/ibm_rag.md", "certificates",
    ),
    (
        "I run the shipment tracker in production.",
        "Built a shipment tracker locally with FastAPI.",
        "projects/shipments.md", "completed_projects",
    ),
    (
        "The API is deployed on a container host.",
        "services:\n  api:\n    image: shipment-api:latest",
        "projects/shipments/docker-compose.yml", "unclassified",
    ),
    (
        "I have mastery of retrieval augmented generation.",
        "Completed the IBM RAG applications course.",
        "courses/ibm_rag.md", "in_progress_courses",
    ),
    (
        "I worked at a logistics company as a backend engineer.",
        "Portfolio entry: shipment tracker.",
        "evidence/portfolio/shipment_tracker.md", "evidence",
    ),
])
def test_each_documented_inference_is_caught_by_a_fixture(text, content, source,
                                                          section):
    found = check(text, supporting=[supplied(content, source=source,
                                             section=section)])

    assert ViolationKind.FORBIDDEN_INFERENCE in kinds(found)
    assert severity_for(ViolationKind.FORBIDDEN_INFERENCE) is Severity.REJECT


@pytest.mark.parametrize("text, content, source, section", [
    (
        "My professional experience includes RAG applications.",
        "Worked as a backend engineer at a logistics company on RAG systems.",
        "evidence/career/backend.md", "evidence",
    ),
    (
        "I run the shipment tracker in production.",
        "The shipment tracker is deployed in production for 12 users.",
        "evidence/shipments/production.md", "evidence",
    ),
    (
        "The API is deployed on a container host.",
        "The API was deployed to the container host on 2024-03-01.",
        "evidence/deployment/api.md", "evidence",
    ),
    (
        "I have mastery of retrieval augmented generation.",
        "Demonstrated mastery of retrieval augmented generation across three "
        "systems, with years of hands-on work.",
        "evidence/skills/rag.md", "evidence",
    ),
    (
        "I worked at a logistics company as a backend engineer.",
        "Worked at Logistics Co as a backend engineer from 2022 to 2024.",
        "evidence/career/logistics.md", "evidence",
    ),
])
def test_the_same_claim_passes_when_evidence_carries_it(text, content, source,
                                                        section):
    found = check(text, supporting=[supplied(content, source=source,
                                             section=section)])

    assert ViolationKind.FORBIDDEN_INFERENCE not in kinds(found)


def test_configuration_is_never_strong_evidence_of_deployment():
    rule = next(r for r in FORBIDDEN_INFERENCES
                if r.key == "configuration_as_deployment")
    supporting = (supplied(
        "deployment:\n  replicas: 3  # deployed by the pipeline",
        source="projects/shipments/deployment.yaml", section="unclassified",
    ),)

    assert forbidden_inference(claim("The API is deployed."), supporting) is rule


def test_a_deployment_note_in_an_evidence_document_does_count():
    rule = next(r for r in FORBIDDEN_INFERENCES
                if r.key == "configuration_as_deployment")
    supporting = (supplied(
        "The API was deployed to production on 2024-03-01.",
        source="evidence/deployment/api.md", section="evidence",
    ),)

    assert forbidden_inference(claim("The API is deployed."), supporting) is None


def test_an_unattributed_claim_is_not_a_forbidden_inference():
    rule = forbidden_inference(
        claim("My professional experience includes RAG applications."), ()
    )

    assert rule is None


def test_overlap_is_measured_on_content_terms_only():
    assert content_terms("I built the API") & content_terms("The API was built")
    assert not content_terms("I built the API") & content_terms("The team met")


# ---------------------------------------------------- the result's shape ---

REJECTING = Violation(kind=ViolationKind.EVIDENCE_INSUFFICIENT,
                      severity=Severity.REJECT, detail="no evidence")
REVISABLE = Violation(kind=ViolationKind.NO_CITATION,
                      severity=Severity.REVISABLE, detail="uncited")


def test_a_pass_cannot_be_constructed_with_a_finding():
    with pytest.raises(ValueError, match="cannot carry a finding"):
        VerificationResult(outcome=VerificationOutcome.PASS, violations=(REVISABLE,))


def test_a_pass_cannot_be_constructed_with_an_unsupported_claim():
    with pytest.raises(ValueError, match="unsupported claim"):
        VerificationResult(
            outcome=VerificationOutcome.PASS,
            claims=(_claim_result(Claim(index=1, text="Something."),
                                  ClaimVerdict.UNSUPPORTED),),
        )


def test_a_rejection_must_name_an_unrepairable_finding():
    with pytest.raises(ValueError, match="cannot be revised"):
        VerificationResult(outcome=VerificationOutcome.REJECTED,
                           violations=(REVISABLE,))


def test_a_revision_requirement_must_name_what_to_change():
    with pytest.raises(ValueError, match="must name what has to change"):
        VerificationResult(outcome=VerificationOutcome.REVISION_REQUIRED)


def test_a_revision_requirement_cannot_carry_an_unrepairable_finding():
    with pytest.raises(ValueError, match="rejected, not sent back"):
        VerificationResult(outcome=VerificationOutcome.REVISION_REQUIRED,
                           violations=(REJECTING, REVISABLE))


def _claim_result(claim_, verdict):
    from app.verification.models import ClaimVerification
    return ClaimVerification(claim=claim_, verdict=verdict)


def test_revision_notes_say_where_to_look():
    result = VerificationResult(
        outcome=VerificationOutcome.REVISION_REQUIRED,
        claims=(_claim_result(Claim(index=2, text="Uncited."),
                              ClaimVerdict.UNSUPPORTED),),
        violations=(REVISABLE,),
    )

    assert result.revision_notes() == ("the draft: uncited",)
    assert result.is_publishable is False


def test_a_pass_is_constructible_and_publishable():
    result = VerificationResult(outcome=VerificationOutcome.PASS)

    assert result.is_publishable is True
    assert result.fully_verified is True
    assert result.revision_notes() == ()


def test_a_degraded_pass_is_publishable_but_not_fully_verified():
    result = VerificationResult(outcome=VerificationOutcome.PASS, degraded=True)

    assert result.is_publishable is True
    assert result.fully_verified is False


def test_the_record_carries_provenance_and_no_evidence_text():
    import json

    result = VerificationResult(
        outcome=VerificationOutcome.REVISION_REQUIRED,
        claims=(_claim_result(Claim(index=1, text="Built an API."),
                              ClaimVerdict.UNSUPPORTED),),
        violations=(REVISABLE,),
        evidence=(reference(label="E1"),),
    )

    record = json.loads(json.dumps(result.to_record()))
    assert record["outcome"] == "REVISION_REQUIRED"
    assert record["evidence"] == [{
        "label": "E1", "source": "evidence/backend/fastapi.md",
        "chunk_id": "a1b2c3:0", "evidence_state": "VERIFIED",
        "section": "evidence",
    }]
    assert "content" not in json.dumps(record)


# --------------------------------------------------------- revision gate ---

def _result(outcome: VerificationOutcome) -> VerificationResult:
    if outcome is VerificationOutcome.REVISION_REQUIRED:
        return VerificationResult(outcome=outcome, violations=(REVISABLE,))
    if outcome is VerificationOutcome.REJECTED:
        return VerificationResult(outcome=outcome, violations=(REJECTING,))
    return VerificationResult(outcome=outcome)


def test_a_pass_publishes():
    assert decide(_result(VerificationOutcome.PASS), 0) is RevisionDecision.PUBLISH


def test_an_unrepairable_result_rejects_without_spending_attempts():
    for attempts in range(MAX_REVISION_ATTEMPTS + 3):
        assert decide(
            _result(VerificationOutcome.REJECTED), attempts
        ) is RevisionDecision.REJECT


def test_a_revisable_result_revises_while_the_budget_lasts():
    result = _result(VerificationOutcome.REVISION_REQUIRED)

    assert decide(result, 0) is RevisionDecision.REVISE
    assert decide(result, MAX_REVISION_ATTEMPTS - 1) is RevisionDecision.REVISE


def test_the_revision_budget_is_exhausted_and_exhaustion_is_terminal():
    result = _result(VerificationOutcome.REVISION_REQUIRED)

    for attempts in range(MAX_REVISION_ATTEMPTS, MAX_REVISION_ATTEMPTS + 5):
        assert decide(result, attempts) is RevisionDecision.EXHAUSTED


def test_the_loop_terminates_for_every_count_and_outcome():
    """The property the step exists for: no sequence of decisions revises
    forever, whatever the caller passes in."""
    revises = 0
    for outcome in VerificationOutcome:
        for attempts in range(0, 25):
            decision = decide(_result(outcome), attempts)
            if decision is RevisionDecision.REVISE:
                revises += 1
            if attempts >= MAX_REVISION_ATTEMPTS:
                assert decision is not RevisionDecision.REVISE

    assert revises == MAX_REVISION_ATTEMPTS


@pytest.mark.parametrize("attempts, limit", [(-1, 2), (0, -1)])
def test_a_negative_budget_is_refused_rather_than_guessed(attempts, limit):
    with pytest.raises(ValueError):
        decide(_result(VerificationOutcome.PASS), attempts, limit=limit)


def test_the_limit_is_injectable_without_reimplementing_the_rule():
    result = _result(VerificationOutcome.REVISION_REQUIRED)

    assert decide(result, 0, limit=0) is RevisionDecision.EXHAUSTED
    assert decide(result, 5, limit=6) is RevisionDecision.REVISE


# ------------------------------------------------------- the tokenizer ---

def test_the_local_tokenizer_agrees_with_the_retrieval_layer():
    """The one rule deliberately stated twice.

    This package may not import ``app.retrieval`` — its import scan asserts
    that — so the three-line tokenizer is restated in
    :mod:`app.verification.claims`. Restating a rule is how two copies drift,
    so this asserts they do not.
    """
    samples = [
        "Built a FastAPI shipment API with SQLAlchemy and Alembic migrations.",
        "40% faster, 1,000 ms — 2024.",
        "Ünïcode and CAPITALS and snake_case",
        "",
    ]

    for sample in samples:
        assert tokenize(sample) == retrieval_tokenize(sample)
