"""Evidence verification — the gate between a draft and anything downstream.

``PLAN.md`` Step 9:

```text
DRAFT → VERIFY → PASS
               → REVISE
               → REJECT
```

The package is layered the way the gate is:

``enums`` / ``models``
    The vocabulary and the shape of an answer. ``VerificationResult`` refuses
    to be constructed as a ``PASS`` that carries a finding, so "it passed" and
    "here is what was wrong with it" cannot both be true of one object.

``claims``
    Turning a draft into numbered sentences and exact factual references.
    Deterministic, no model, and no import from the retrieval layer.

``policy``
    The deterministic checks and the severity each finding carries. This is
    where ``data/audit/README.md`` §3's forbidden inferences live, transcribed
    with the line each one came from.

``support`` / ``judge``
    The advisory half: a protocol, and the OpenRouter-backed implementation of
    it. Consulted only after the deterministic checks pass, reported rather
    than trusted, and never a gate.

``verifier``
    The gate itself — :func:`verify`, a function, as ``PLAN.md`` describes it.

``revision``
    The stopping rule. ``PLAN.md`` requires the revision loop to be bounded and
    terminating and leaves the loop to Step 10; the bound and the decision are
    here, so no caller has to invent them.

What this package does not do: it does not retrieve, it does not write
anything, and it does not publish. There is no store handle and no path to the
corpus anywhere in it — the evidence that exists is the evidence it was handed.
"""
from app.verification.enums import (
    ClaimVerdict,
    RevisionDecision,
    Severity,
    VerificationFailureCategory,
    VerificationOutcome,
    ViolationKind,
)
from app.verification.errors import SupportJudgeUnavailable, VerificationError
from app.verification.judge import JUDGE_PROMPT_VERSION, LlmSupportJudge
from app.verification.models import (
    Claim,
    ClaimVerification,
    EvidenceReference,
    Reference,
    SuppliedEvidence,
    VerificationRequest,
    VerificationResult,
    Violation,
)
from app.verification.revision import (
    MAX_REVISION_ATTEMPTS,
    revision_decision,
)
from app.verification.support import (
    JudgeVerdict,
    JudgedClaim,
    JudgementRequest,
    SupportJudge,
)
from app.verification.verifier import EvidenceVerifier, verify

__all__ = [
    "JUDGE_PROMPT_VERSION",
    "MAX_REVISION_ATTEMPTS",
    "Claim",
    "ClaimVerdict",
    "ClaimVerification",
    "EvidenceReference",
    "EvidenceVerifier",
    "JudgeVerdict",
    "JudgedClaim",
    "JudgementRequest",
    "LlmSupportJudge",
    "Reference",
    "RevisionDecision",
    "Severity",
    "SuppliedEvidence",
    "SupportJudge",
    "SupportJudgeUnavailable",
    "VerificationError",
    "VerificationFailureCategory",
    "VerificationOutcome",
    "VerificationRequest",
    "VerificationResult",
    "Violation",
    "ViolationKind",
    "revision_decision",
    "verify",
]
