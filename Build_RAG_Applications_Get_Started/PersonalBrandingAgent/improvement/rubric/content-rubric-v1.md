# Content-Evaluation Rubric — `content-rubric-v1`

This rubric defines the metrics a content-level Abu Prompt experiment is scored
against, and the small set of **hard gates** that can invalidate a run outright.

It is versioned (`content-rubric-v1`) and reviewed. The evaluator reads it and
computes against it; it never writes it. Changing the meaning of a metric, the
denominators, or the gate policy requires a **new version** — an artifact names
the rubric version it was measured under, so a silent redefinition would make
old and new results incomparable.

The rubric is deliberately **not** a single score. Metrics are reported side by
side so an editorial improvement can never be traded against a regression in
factual grounding. A run whose hard gate fails is a **failed run**, regardless
of how good the other numbers look.

---

## The baseline quality gate (`baseline_quality_gate_passed`)

The deterministic evaluator runs the real pipeline over each **scored** case —
building the real evidence context, building the real draft, and calling the
real `app.verification.verifier.verify`. "Publishable" below means
`VerificationResult.is_publishable` is `True` for a candidate.

Selection is deterministic and **independent of the reviewed labels**: the
candidate the pipeline carries forward is the **first offered candidate that
passes verification**. Offered order is therefore part of the frozen input, and
`selection_agreement_rate` checks whether that blind choice happens to land on a
reviewed *preferred* or *acceptable* draft.

`baseline_quality_gate_passed` is the headline Boolean, and it means exactly one
thing: **the evaluated outputs were safe over the scored cases.** Concretely, it
is `true` when none of the following holds for any scored case:

1. an **unacceptable** candidate was selected;
2. a candidate was selected for a case the review marked **not
   publish-appropriate**;
3. the **selected** candidate carries a `FORBIDDEN_INFERENCE` or
   `UNSUPPORTED_REFERENCE` finding.

Each reason is appended to `baseline_quality_gate_notes`, and the offending case
id is added to `unsafe_selection_case_ids`.

### What this Boolean is *not*

`baseline_quality_gate_passed` does **not** mean:

- **"no safety violations exist in the fixtures."** Unsafe drafts are offered on
  purpose. The gate reports how many were *detected*
  (`detected_forbidden_inference_findings`,
  `detected_unsupported_reference_findings`) and how many *escaped onto a
  selected candidate* (`selected_forbidden_inference_findings`,
  `selected_unsupported_reference_findings`). A detected-and-blocked finding is
  a passing outcome; a finding on a selected draft is the failure.
- **"the Lab's isolation held."** Isolation — no reachable store, network or
  model — is a *structural* property asserted by
  `tests/test_improvement_isolation.py`, not by this artifact. The artifact
  records an `isolation_note` pointing there so the two claims are never
  conflated.

In the current baseline there are 3 detected forbidden-inference findings and 3
detected unsupported-reference findings, **0** on a selected candidate, so the
gate passes. Those findings are drafts the gate caught and blocked; they are
evidence the gate works, not evidence it failed.

---

## Metrics

All rates are reported with their numerator, denominator and sample count, so a
reader can re-derive the value rather than trust a rounded float. Each metric
also records its **unit** (the thing counted), its **population** in words, the
exact **fixture ids** that contributed (`population_case_ids`) and any fixtures
deliberately excluded (`excluded_case_ids`, i.e. known-limitation probes). A
metric whose denominator is zero is reported as `value = null` with an
`unavailable_reason` — **missing is never reported as `0.0`**.

| Metric | Unit | Population | Numerator / denominator | Direction |
| --- | --- | --- | --- | --- |
| `decision_schema_valid_rate` | candidate | every offered candidate in scored cases | structured result / offered | higher = more robust |
| `citation_resolution_rate` | candidate that cited | offered candidates that cited any evidence | resolved / cited | higher = better grounding |
| `verification_pass_rate` | candidate | every offered candidate in scored cases | passed / offered | context only |
| `forbidden_inference_rate` | candidate | every offered candidate in scored cases | detected / offered | **lower = better** |
| `unsupported_reference_rate` | candidate | every offered candidate in scored cases | detected / offered | **lower = better** |
| `insufficient_evidence_handling_rate` | case | scored `insufficient_evidence` cases expected not to publish | published nothing / cases | higher = safer restraint |
| `malformed_handling_rate` | case | scored `malformed_reasoner` cases | published nothing / cases | higher = safer containment |
| `selection_agreement_rate` | case | scored cases the review marks publish-appropriate | preferred/acceptable / cases | higher = better alignment |
| `publish_decision_agreement_rate` | case | every scored case | decision matched review / cases | higher = closer to the reviewed publish decision |

### Denominator reconciliation

The dataset holds **23 cases**: **22 scored** cases plus **1 known-limitation
probe**. The probe is excluded from every metric and from the gate, which is why
no denominator is 23.

| Denominator | Counts | Why it differs from 22 |
| --- | --- | --- |
| 22 cases | all scored cases | the baseline population |
| 25 candidates | all offered candidates across the 22 scored cases | 3 cases offer two candidates each |
| 23 citing candidates | offered candidates that cited anything | 2 candidates (malformed/empty drafts) cite nothing, so they are out of the citation-rate unit |
| 11 publish-appropriate cases | scored cases the review marks publish-appropriate | only these have a "preferred candidate" for `selection_agreement_rate` |
| 2 insufficient-evidence cases | scored `insufficient_evidence` cases expected not to publish | category-scoped metric |
| 3 malformed cases | scored `malformed_reasoner` cases | category-scoped metric |

Different denominators are therefore a consequence of the metric *unit*, not an
inconsistency: candidate-unit metrics divide by candidates, case-unit metrics by
cases, and category metrics only by their category's cases. Each observation is
counted once; a case with two candidates contributes two candidate observations
but a single case observation.

### Notes on individual metrics

- **`verification_pass_rate` is context, not a target.** A lower pass rate is
  not automatically worse: the dataset deliberately contains unacceptable drafts
  that *should* fail. It is reported so a change in gate strictness is visible,
  and is never optimised in isolation.
- **`selection_agreement_rate` is scored only where a publish is appropriate.**
  A case that correctly publishes nothing has no "preferred candidate" to agree
  with; scoring it would reward the wrong thing.
- **`publish_decision_agreement_rate` measures agreement with the reviewed
  decision, not the quality of a draft.** It is the share of scored cases where
  the pipeline's publish/no-publish decision equals the reviewer's expected
  `publish_appropriate`. A draft can be weak yet still "agree" if the review also
  said not to publish; conversely a strong draft the pipeline declines still
  disagrees. It was renamed from `publish_appropriateness_rate`, which wrongly
  implied a judgement of the draft's publishing merit.
- **`citation_resolution_rate` counts only candidates that cited something.**
  A draft that cites nothing is a different failure (attribution), tracked by
  `publish_decision_agreement_rate` and the gate, not by dividing this rate down.
- **`forbidden_inference_rate` and `unsupported_reference_rate` measure
  detection, not escape.** A higher value here can reflect a fixture suite that
  surfaces more bad drafts; the safety-relevant number is whether one reached a
  *selected* candidate, which is the gate.

---

## Hard-gate metrics

`HARD_GATE_METRICS` names the two rates that describe factual grounding and may
never be traded against editorial metrics:

```
forbidden_inference_rate
unsupported_reference_rate
```

They are listed in the rubric so the policy is declared in one place, but the
actual enforcement is the per-case quality gate above: a single selected
candidate with either finding fails the run. Metric scores can never offset a
gate failure — `baseline_quality_gate_passed` is evaluated independently of
every rate.

---

## Known limitations (measured, not hidden)

Some weaknesses of the deterministic gate are **known** and are kept visible as
*probes* rather than either ignored or disguised. A probe is a fixture marked
`known_limitation` in the dataset; it is evaluated (so the weakness is
*observed*) but is **excluded from every scored metric and from the quality
gate**, and is reported in the artifact's `known_limitations` list.

| Limitation id | Claim | Expected | Observed |
| --- | --- | --- | --- |
| `bare-count-undetected` | "I hold 5 IBM certificates." | gate rejects (a catalog index states no count) | gate **passes** it — the bare count `5` is not an extracted reference |

The reference extractor matches percentages, versions, years and unit-bearing
quantities. A bare integer produces no reference, so the exact-string reference
check has nothing to fail on. This is a false negative in the lenient direction:
it does **not** mean the claim is supported, only that this gate cannot prove it
isn't. The companion catalog case `ho-catalog-only-dated-claim` uses a *year*
(which the audit explicitly names), so it exercises the same "catalog cannot
carry an exact fact" idea on a reference the gate *does* detect.

Probes must never be recast as desired outcomes: `expected.publish_appropriate`
for a probe records what a correct gate *should* do, while the evaluator records
that the current gate does not do it (`escaped_detection = true`).

---

## What this rubric does not measure

- **Engagement.** The repository's metrics-import facility exists, but no
  engagement data has been collected, and `publication_metrics` is
  decision-free by design. No engagement metric is computed here.
- **Live model quality.** Stage 1 evaluates *frozen* candidate drafts, not live
  model output. It measures the deterministic gate, not the generator.
- **Semantic support.** The gate is a string comparison; a paraphrase
  (`2× faster` for `200% of the previous throughput`) is not matched, and a
  bare count without a unit is not an extracted reference at all. These are
  known, documented limits and are candidates for the advisory judge, not for
  this rubric.
- **Statistical representativeness.** The dataset is small and inspectable; it
  is a reference set, not a sample.

---

## Changing the rubric

1. Edit `app/improvement/rubric.py` (metric names, gate set) **and** this
   document together.
2. Bump `RUBRIC_VERSION` to a new identifier (`content-rubric-v2`).
3. Record the new version in the dataset's `rubric_version` if the dataset's
   expectations change to match.
4. Never edit a published artifact. Old artifacts keep naming the version they
   were measured under.
