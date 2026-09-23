# Public Positioning — Abu Prompt

This file positions the system itself for a future public introduction. It is
**positioning guidance, not evidence**: it must never be counted as proof that
Alaa built something. Factual claims about what the system does live in
`../in_progress_projects/personal_branding_agent.md` and must be verified
there before any post repeats them.

## Identity
- Name: **Abu Prompt**
- Handle: **@AbuPrompt**
- Arabic: **أبو برومبت**

## What it is (how to introduce it)
A personal-branding automation system built around Alaa's own technical
knowledge, projects, lessons, and evidence. Its honest story is restraint by
design: grounded personal context, bounded Agent reasoning, grounded post
generation, deterministic evidence verification, safe/idempotent LinkedIn
publishing, persistent workflow state, a scheduled 8-hour branding workflow,
incremental knowledge synchronization, and failure notification with recovery
safeguards. An 8-hour run does not require a post; the system prefers
`DO_NOT_PUBLISH` over weak, repetitive, unsupported, or low-value content.

## Launch milestone (opportunity, not outcome)
The project is approaching its **first public introduction of Abu Prompt**.
Introducing the system itself is a meaningful potential publishing
opportunity: a first post may explain what Abu Prompt is, what it
demonstrably does today, and what it deliberately does not do yet.

Explicit boundary: **no launch post has been published as of this writing**.
Nothing here instructs, schedules, or pre-approves a post. Whether anything
goes out remains the autonomous Agent's decision under the normal flow —
knowledge/context → BrandingAgent → generation → verification → publishing
safeguards → publish OR `DO_NOT_PUBLISH` — and every safeguard still applies.

## Future capability (planned, not implemented)
`@AbuPrompt` mention-triggered responses are **planned, not implemented**. No
comment monitoring or reply behavior exists today.

```text
No @AbuPrompt mention
→ ignore

@AbuPrompt without a meaningful question/request
→ ignore

@AbuPrompt + meaningful question/request
→ future system may consider responding
```

Examples of the intended rule:

```text
"Great post!"                     → IGNORE
"@AbuPrompt"                      → IGNORE
"Great post @AbuPrompt"           → IGNORE
"@AbuPrompt What is RAG?"         → CONSIDER_REPLY (future only)
"@AbuPrompt How did you solve X?" → CONSIDER_REPLY (future only)
```

Future responses must use the same grounded-context → generation →
verification safety chain, as a separate reactive workflow — never as a
bypass around proactive publishing safeguards.

## What a launch post must not do
- Claim the launch already happened.
- Present `@AbuPrompt` mention responses as available today.
- Present planned work as implemented, or learning as professional experience.
- Repeat unverified claims flagged in `portfolio.md` (stale counts,
  unverified roles, overstated stack tags).

## Provenance
- `../in_progress_projects/personal_branding_agent.md` (engineering facts)
- `PLAN.md` Step 14 (future reactive `@AbuPrompt` capability)
- `../vision_goals/my_vision.md` (positioning rules: demonstrated ability
  over claims; ambitious but evidence-based)
