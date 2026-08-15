# Personal Branding Agent — RAG over personal data for LinkedIn

## Status
IN PROGRESS — actively being built (this folder is the working repo). This is a
course-project application of RAG from the IBM GenAI curriculum.

## What it aims to do
An agent that uses **RAG over personal data** (from `data/` markdown) to generate
authentic LinkedIn posts in the user's voice, then publishes them via the
LinkedIn API, running as a Flask web app with a human-in-the-loop review step.

## Core loop (from PLAN.md)
1. Ingest -> chunk + embed -> Chroma vector store
2. Index -> retrieval on topic
3. Retrieve relevant context
4. Generate LinkedIn post (LLM via OpenRouter, user voice/style)
5. Review (human-in-the-loop edit/approve)
6. Publish (LinkedIn API; OAuth handled in `Auth_handling/`)

## Intended stack
OpenRouter (free-tier Llama), sentence-transformers/all-MiniLM-L6-v2 embeddings,
Chroma (local persistent), LangChain LCEL, Flask + vanilla HTML/JS, existing
LinkedIn OAuth flow.

## What exists so far
- `data/` — the knowledge base (`completed_projects/`, `in_progress_projects/`,
  `in_progress_courses/`, `certificates/`, `evidence/`, `vision_goals/`,
  `writing_style/`, `stories_lessons/`) that will be the RAG corpus.
- `config.py` — app config (API keys, model IDs, paths).
- `Auth_handling/` — working LinkedIn OAuth (linkedin_oauth_setup.py,
  linkedin_tokens.json, test_post.py).
- `requirements.txt`, `.env`, `.gitignore`, `RAG_Lab.ipynb`.

## Not yet built (plan → pending)
`ingest.py`, `retriever.py`, `generator.py`, `app.py`, `templates/index.html`,
`prompts/linkedin_prompt.txt` — the RAG indexing/generation/publish pipeline is
still to be built. PLAN.md lists these as pending steps.

## Provenance
`/home/alaabadawii/LLMs/IBM/course-2/PersonalBrandingAgent/PLAN.md`
`/home/alaabadawii/LLMs/IBM/course-2/PersonalBrandingAgent/requirements.txt`
`/home/alaabadawii/LLMs/IBM/course-2/PersonalBrandingAgent/Auth_handling/`