# RAG — Learning vs Applied Evidence

Distinguishes "I studied RAG" from "I used RAG to build something".

## Evidence state

- RAG **learning**: LEARNING (IBM RAG & Agentic AI specialization in progress).
- RAG **application**: IN_PROGRESS (Personal Branding Agent RAG over `data/`).

Sources: `../in_progress_courses/ibm_rag_and_agentic_ai.md`,
`../in_progress_projects/personal_branding_agent.md`, `../in_progress_courses/ibm_genai_llm_rag.md`.

## What RAG learning covers (course material — learning, not ability proof)

IBM RAG & Agentic AI specialization (currently Course 2 "Build RAG Applications:
Get Started" at 67%): retrieval concepts, LlamaIndex (cheat sheet seen), vector
databases for RAG, advanced retrievers, agents. **Progression is course exposure.**

## What RAG practice exists (application evidence)

- **Personal Branding Agent** (IN PROGRESS): RAG over personal markdown
  (`data/`) with chunk+embed → Chroma vector store → index → retrieve → generate
  (LLM via OpenRouter) → human review → publish (LinkedIn OAuth). Currently the
  corpus/KB + LinkedIn OAuth exist; the ingest/retrieve/generate/publish pipeline
  is still to be built (per `PLAN.md`).
- Historical RAG lab (`../in_progress_courses/ibm_genai_llm_rag.md`): load →
  split → embed/ingest to Chroma → retrieve → LLM (watsonx) → RetrievalQA,
  memory, "make it an agent". Practical course-lab application of retrieval concepts.

## Publicly safe claim

- "I'm learning RAG and applying retrieval concepts in a personal RAG project
  that generates content from my own knowledge base."

## Avoid

- "I'm a RAG expert / proficient in RAG." (Course in progress; application incomplete.)

## Relationship

- RAG learning → Personal Branding Agent (this project) → supports the writing /
  content generation pipeline.