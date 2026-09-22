# Evidence Policy & Quality Gates

What a post must survive before it may publish (`PLAN.md` Steps 4, 8, 9).
This is the operator-visible contract of the deterministic gates: what they
check, what each outcome means, and where the corpus's own audit rules live.
Model behavior is instructed, never trusted — every gate below is code.

---

## 1. Authority

- The corpus's audit rules live in `data/audit/README.md` (§3, quoted
  verbatim in code) and the evidence vocabulary in `data/evidence/README.md`.
- The gates live in `app/verification/` (deterministic, authoritative) with
  one advisory exception: the LLM support judge, consulted only after the
  deterministic checks pass, reported rather than trusted, and never a gate.
- Generation (`app/generation/`) has no opinion on truth. A plausible draft
  and a supported draft are indistinguishable until Step 9 runs.

## 2. The five forbidden inferences

From `data/audit/README.md` §3, enforced as named rules — each fires only
for a claim attributed to evidence, and only when nothing behind it
qualifies as strong:

| # | Weaker source may never claim | Forbidden upgrade |
|---|---|---|
| 1 | coursework | professional experience |
| 2 | local/practice project | production system |
| 3 | configuration | deployment |
| 4 | course completion | mastery |
| 5 | portfolio entry | employment |

The sixth audit line — never invent dates, metrics, technologies,
responsibilities, or outcomes — is enforced by the exact-reference check
plus the advisory judge instead.

## 3. Evidence states

Evidence declares its own strength (`UNVERIFIED`, `STALE`, `ASPIRATIONAL`,
`LEARNING`, plus strong states such as `VERIFIED`, `DOCUMENTED`):

- `UNVERIFIED` / `STALE`: nothing may rest on them, no exceptions.
- `ASPIRATIONAL` / `LEARNING`: legitimate states, usable only when the
  claim makes the same admission ("I'm learning X" supported by evidence
  that says exactly that is not an upgrade).
- Undeclared evidence is usable and keeps its absent state.
- Context assembly orders deterministically by the corpus's evidence
  hierarchy (concrete repository evidence first, inference last) and keeps
  evidence separate from guidance: positioning, vision, and writing style
  shape how something is said and can never support that it is true (a claim
  resting only on guidance is `GUIDANCE_AS_EVIDENCE`).

## 4. Claim-level gates

Every non-empty sentence of a draft becomes a numbered claim; each carries
its own verdict (`SUPPORTED` / `UNSUPPORTED` / `REJECTED`) and its
supporting evidence by provenance. Exact references — numbers, percentages,
dates, versions, quantities — are string-matched against the cited evidence
(`40 %` matches `40%`; a plain reference may not match across a word
boundary):

- figure in no cited evidence → `UNSUPPORTED_REFERENCE` (reject);
- figure present in evidence the draft did not cite → `UNCITED_REFERENCE`
  (revise — under-attribution, fixed by citing).

Severity is a declared table, not a judgement: wording findings
(`NO_CITATION`, `UNCITED_REFERENCE`, `GUIDANCE_AS_EVIDENCE`,
advisory objections) are `REVISABLE`; evidence/provenance findings
(`CITATION_NOT_IN_CONTEXT`, `EVIDENCE_INSUFFICIENT`,
`EVIDENCE_STATE_TOO_WEAK`, `FORBIDDEN_INFERENCE`,
`UNSUPPORTED_REFERENCE`, empty draft) are `REJECT`. Any `REJECT` finding
rejects the draft; revisable findings require revision.

## 5. Outcomes and what they do

| Gate outcome | Meaning | System effect |
|---|---|---|
| `PASS` | every claim supported | the only value that permits a publish; unconstructible while carrying a finding |
| `REVISION_REQUIRED` | repairable by rewriting | Step 10's bounded loop re-drives generation with the verdict's own revision notes, at most `revision_limit + 1` attempts |
| `REJECTED` | unrepairable from this evidence | `DO_NOT_PUBLISH` (`GATE_REJECTED`) — a decision, not a dead end; `REVISION_EXHAUSTED` is reported separately ("stopped trying" vs "could never pass") |

Insufficient evidence is a first-class outcome, not an empty result: a
context with no evidence produces an explicit `INSUFFICIENT` state, the
generator declines without calling the model, and the run ends as a normal
`DO_NOT_PUBLISH`. A verifier that cannot reach a verdict raises
`VerificationError` instead — "the gate could not decide" fails the run
(`WORKFLOW_FAILED`), never a quiet no-op. An unavailable advisory judge
degrades (`degraded=True`) and lets the deterministic gates stand; any other
judge malfunction fails closed.

## 6. Related

| Document | Role |
|---|---|
| `data/audit/README.md` | The audit rules, in the corpus's own words |
| `data/evidence/README.md` | The evidence-state vocabulary |
| [`autonomous-evaluation.md`](autonomous-evaluation.md) | Scenarios 8–10 proving the gates end to end |
| [`../architecture/rag-architecture.md`](../architecture/rag-architecture.md) | Retrieval-side evidence handling |
