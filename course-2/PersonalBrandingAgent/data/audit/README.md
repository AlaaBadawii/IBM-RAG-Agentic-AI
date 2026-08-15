# Audit Process

Operational documentation for auditing the Personal-Branding Knowledge Base.
This directory contains **analysis of the KB's consistency and evidence
quality**. It is NOT a source of personal facts.

The primary examples of intended scope and depth are the existing
`cross_source_audit.md` and the story-level audit `stories_evidence_audit.md`
(verifies each story in `data/stories_lessons/` against the actual sources).

---

## 1. Audit Purpose

The audit exists to detect:

- contradictions
- stale claims
- missing source coverage
- duplicate or ambiguous project identities
- incorrect statuses
- unsupported public claims
- missing evidence
- inconsistent dates
- incorrect relationships between projects
- gaps in the engineering journey
- claims that are stronger than the underlying evidence

The audit protects the KB from becoming more confident than the evidence
supports.

---

## 2. Source of Truth

Use this evidence hierarchy (highest first):

1. Actual project/source files and repository evidence
2. Evidence files under `data/evidence/`
3. Specific project/course/certificate records
4. Stories and lessons
5. Public positioning / portfolio claims
6. Audit conclusions

The audit must **never** become the source of truth for personal facts.

If an audit says something is true but the underlying source does not support
it, the audit finding itself is not sufficient evidence.

---

## 3. Audit Principles

Always:

- inspect the actual KB before making conclusions
- distinguish facts from interpretations
- distinguish completed, in-progress, planned, and aspirational work
- preserve uncertainty when evidence is incomplete
- never upgrade a claim because it sounds better for personal branding
- never infer professional experience from coursework
- never infer production experience from a local project
- never infer deployment from configuration alone
- never infer mastery from course completion
- never infer employment from a portfolio entry without supporting evidence
- never invent dates, metrics, technologies, responsibilities, or outcomes

When sources disagree, identify the conflict instead of silently choosing a
convenient value.

---

## 4. What to Check

Run a repeatable audit covering:

- **A. Source coverage** — is every known source represented in the KB?
- **B. Contradictions** — do files disagree on the same fact?
- **C. Naming and duplicate projects** — same project under multiple names, or
  distinct projects that look merged.
- **D. Dates** — conflicting or implausible dates.
- **E. Status consistency** — completed vs in-progress vs planned vs
  aspirational, per file.
- **F. Evidence coverage** — does evidence exist for major claims?
- **G. Unsupported public claims** — claims with no backing evidence.
- **H. Skills and competency claims** — are claimed skills supported?
- **I. Project relationships** — correct and explicit links between projects.
- **J. Engineering-journey progression** — is the learning arc coherent and
  complete?
- **K. Portfolio/public-positioning consistency** — do public claims match the
  KB?

Use the existing `cross_source_audit.md` categories as the baseline; expand
when necessary.

---

## 5. Evidence Audit

Distinguish:

- evidence exists
- evidence is weak
- evidence is indirect
- evidence is missing
- claim is unsupported
- claim is contradicted

A project file existing is not automatically proof of every claim made about
that project.

For important public claims, ask:

> What concrete source would allow another agent to verify this claim?

---

## 6. Stories Audit

Stories under `data/stories_lessons/` must be grounded in actual events,
decisions, bugs, discoveries, or documented learning.

Do not create stories merely because a technology appears in the KB.

A strong story should have:

- a concrete situation
- something that happened
- a decision/problem/discovery
- an engineering lesson
- supporting evidence

Avoid converting generic course knowledge into personal stories.

---

## 7. Certificate Audit

Certificates should not be treated as verified merely because they are listed
in `portfolio.md`.

Check:

- certificate file exists
- issuer
- certificate/program name
- completion/issue date
- evidence/reference
- whether the status is completed or in progress

If evidence is missing, mark it unverified rather than inventing validation.

---

## 8. Public Positioning Audit

Compare `public_positioning/` against the rest of the KB.

Flag claims that are:

- stronger than the evidence
- stale
- unsupported
- inconsistent with current project status
- using technologies that are planned rather than implemented
- presenting learning as professional experience
- presenting experimental work as production experience

The goal is not to make the branding weaker. The goal is to make it maximally
credible.

---

## 9. Correction Policy

Separate findings into:

- CRITICAL
- HIGH
- MEDIUM
- LOW
- INFORMATIONAL

For every actionable finding include:

- problem
- affected files
- evidence/source
- why it matters
- recommended correction

Do not automatically modify source files during an audit unless explicitly
instructed to perform remediation. An audit is primarily a diagnostic
operation.

---

## 10. Remediation

After remediation, a later audit should verify whether the finding was actually
resolved.

Do not mark an item ACTIONED merely because someone intended to fix it.

An item is ACTIONED only when the relevant source file has actually been updated
and the resulting state is consistent.

If evidence is still missing, the finding remains unresolved.

---

## 11. Audit History

Preserve previous audit reports rather than overwriting historical reports.

Recommended filename pattern:

```
cross_source_audit_YYYY-MM-DD.md
```

The current `cross_source_audit.md` remains the latest/current audit.

Do not create historical reports unless explicitly asked.

---

## 12. Output Format

A future full audit should contain:

```
# Cross-Source Consistency Audit

## Resolution Status
## Scope
## A. Critical — Missing Source Coverage
## B. Conflicts
## C. Naming / Duplicate Projects
## D. Dates
## E. Evidence Gaps
## F. Unsupported Claims
## G. Completed vs In-Progress Consistency
## H. Important Relationships
## I. Engineering Journey Progression
## J. Recommended Corrections
## K. Summary
```

The exact sections can expand when necessary, but the audit should remain
structured and easy for another agent to consume.

> Note: the current `cross_source_audit.md` predates this format and uses
> slightly different section letters (A–J) and a "Summary Score" section. It
> remains valid as the current audit; future audits should follow the format
> above.

---

## 13. Important Boundary

Do NOT use the audit to generate marketing copy.

The audit determines whether the KB is internally consistent and evidence-
backed. Writing style and public positioning determine how supported facts are
communicated.

---

## 14. Final Rule

The audit should answer:

> Can this Knowledge Base support the claims we are making?

not:

> How can we make the profile sound better?