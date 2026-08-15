# Build the Mechanics Yourself Before Reaching for a Framework

## Type

Learning

## Context

Built three AI engineering agents deliberately **without** frameworks (no
LangChain, no CrewAI) in `/home/alaabadawii/LLMs/AI-Agents/` — the README Agent,
an Agent Assistant, and a Multi-Agent orchestrator.

## Problem

Frameworks abstract away the crucial mechanics of agents. Using one first would
have left the core concepts as a black box.

## What I Did

Built the agent loop and supporting pieces from scratch in plain Python:
the agent loop, memory, tool calling as a structured protocol, explicit
termination, a registry/decorator-based tool registration, and multi-agent
routing.

## Decision / Insight

The key realizations (from the project's own README):
- The agent loop is ~50 lines: call LLM → parse → execute tools → repeat.
- Memory is just a list of `{role, content}` dicts; LLMs have no memory — you
  pass context every call.
- Tool calling is a structured protocol; the LLM never runs code directly.
- Termination is explicit — the agent stops only because you give it a terminate
  tool.
- "Frameworks become tools you choose, not black boxes you depend on."

## Result

Three working agents with a shared `litellm` + OpenRouter setup plus Docker
support (per-agent Dockerfiles + compose). The folder's README was written by the
README agent itself. This is experimental/local work — not a production system.

## Engineering Lesson

Learn the mechanics before adopting the abstraction. When you can build the
"framework" behavior yourself, later frameworks become informed choices instead
of opaque dependencies.

## Why This Matters

This is learning-by-building in action and supports the AI-systems direction. It
also connects forward: the later **Evaluator Core** is a separate, later build in
the same folder that continues into Quizey Phase 3 AI grading (see
`evidence/ai/evaluator_core.md`).

## Evidence

- `/home/alaabadawii/LLMs/AI-Agents/README.md` ("What I Learned")
- `/home/alaabadawii/LLMs/AI-Agents/Readme_Agent/`,
  `Agent_Assistant/`, `Multi_Agents/`
- `/home/alaabadawii/LLMs/AI-Agents/docker-compose.yml`
- KB: `completed_projects/ai_agents_from_scratch.md`,
  `evidence/ai/ai_agents_from_scratch.md`

## Content Potential

- Learning-by-building post ("I built AI agents from scratch")
- Architecture / "how the agent loop actually works" insight
- Contrast with framework-based development

Story strength:
STRONG

Reason:
A deliberate engineering decision (build without frameworks) with concrete
artifacts and a clear, generalizable lesson about learning mechanics first. It
reveals Alaa's learning process and deep understanding, not just tool knowledge.