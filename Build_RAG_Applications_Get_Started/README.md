# Course 2 — Build RAG Applications: Get Started

**Status: In Progress**

Three projects exploring RAG (Retrieval-Augmented Generation) pipelines, Gradio interfaces, and agent architectures using **OpenRouter** (for LLMs), **local Hugging Face embeddings**, and **ChromaDB** for vector storage. All projects swap IBM's proprietary watsonx provider for free, OpenAI-compatible alternatives.

The course progresses from simple Gradio demos through a full RAG application (the LinkedIn Icebreaker Bot) to a production-oriented agent with OAuth integration and a structured knowledge base.

---

## Projects

### LinkedIn Icebreaker Bot (`icebreaker/`)

An AI-powered tool that generates personalized icebreakers and conversation starters based on LinkedIn profiles. Uses **LlamaIndex** for indexing, **OpenRouter** for the LLM, and **local Hugging Face embeddings** (`sentence-transformers/all-MiniLM-L6-v2`) for semantic retrieval.

- Rebuild of the IBM "AI Icebreaker Bot" lab with the proprietary provider swapped for OpenRouter + local embeddings
- Full RAG pipeline: splitting → indexing → retrieval → generation
- Available as both a Gradio web UI and a CLI
- Switch LLM models at runtime (via CLI flag or web UI dropdown)
- Uses mock data by default (no API keys required for testing)
- **Note:** ProxyCurl API (used for LinkedIn profile extraction) was discontinued as of Feb 2025; the project supports mock data and is adapting to alternative data sources

### Gradio UI Experiments (`Gradio/`)

Two hands-on Gradio demonstrations for practicing the Gradio component model before building the LinkedIn Icebreaker Bot UI.

1. **Sentence Builder** — A `gr.Interface` that generates a descriptive sentence from structured inputs (sliders, dropdowns, checkboxes, radio buttons)
2. **Image Captioning** — A `gr.Interface` using **BLIP** (Bootstrapping Language-Image Pre-training) from Salesforce to generate top predicted ImageNet labels with confidence scores

Both demos are single-file applications demonstrating Gradio's `gr.Interface` pattern with diverse component types.

### Personal Branding Agent (`PersonalBrandingAgent/`)

A production-oriented agent that generates, evaluates, and publishes authentic LinkedIn posts grounded in a personal knowledge base. Built as an extension of the IBM course "Build RAG Applications: Get Started."

- **Knowledge base** — structured `data/` corpus with projects, courses, certificates, evidence (with state tracking), stories, writing style, and public positioning
- **LinkedIn OAuth** — full OAuth 2.0 flow with token refresh and post publishing via the LinkedIn REST API
- **RAG pipeline** (in progress) — ingest → retrieve → generate → evaluate → publish, defined in `PLAN.md` (10 phases)
- Modular architecture separating knowledge, reasoning, generation, evaluation, and tools
- **Current status:** knowledge base and OAuth complete; RAG pipeline being built incrementally

---

## Tech Stack

Only libraries actually imported in source code:

- **Python** 3.10+
- **Gradio** — web UI framework (icebreaker, Gradio demos)
- **LlamaIndex** — data indexing and retrieval (icebreaker)
- **LangChain** — LCEL chains, `ChatPromptTemplate`, `JsonOutputParser` (PersonalBrandingAgent)
- **Pydantic** — structured output schemas
- **sentence-transformers** (`all-MiniLM-L6-v2`) — local Hugging Face embeddings for all projects
- **chromadb** — vector database (PersonalBrandingAgent)
- **OpenRouter** — LLM provider via OpenAI-compatible chat-completions API
- **python-dotenv** — environment variable loading
- **transformers**, **torch**, **PIL** — BLIP image captioning (Gradio demos)

---

## What's Built

- A full RAG pipeline in the icebreaker bot (splitting → indexing → retrieval → generation)
- Two Gradio demos demonstrating component variety (sliders, dropdowns, checkboxes, radio, image, label)
- A structured personal knowledge base with 9 data categories and evidence state tracking
- LinkedIn OAuth 2.0 integration with token refresh and post publishing
- Multi-model support across all projects (runtime model switching)
- Both CLI and web UI interfaces where applicable
- XSS-safe rendering via `escapeHtml()` on dynamic output (icebreaker)

---

## Planned / Not Yet Built

### icebreaker
- **ProxyCurl replacement** — the LinkedIn profile extraction API was discontinued; mock data works but real-profile support needs an alternative data source
- **Server-side streaming** — listed as a stretch goal in `plan.md`; not implemented

### PersonalBrandingAgent
- **RAG pipeline** — ingest → retrieve → generate → evaluate → publish is defined in `PLAN.md` (10 phases) and in progress
- **Evaluation and quality gates** — PASS / REVISE / REJECT grading not yet implemented
- **Publishing pipeline** — OAuth + publish scripts exist; the full automated pipeline is not complete
- **Full agent loop** — the agent autonomy layer is the main remaining work

---

## Setup / Run

Each project is self-contained with its own `requirements.txt` and uses environment variables for secrets. **Never commit `.env` files.**

```bash
cd Build_RAG_Applications_Get_Started/<project>
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set OPENROUTER_API_KEY (and LinkedIn keys for PersonalBrandingAgent)
```

### Run commands

```bash
# Icebreaker Bot — CLI with mock data
cd Build_RAG_Applications_Get_Started/icebreaker && python main.py --mock

# Icebreaker Bot — Gradio web UI
cd Build_RAG_Applications_Get_Started/icebreaker && python app.py

# Gradio Sentence Builder
cd Build_RAG_Applications_Get_Started/Gradio && python app.py

# Gradio Image Captioning
cd Build_RAG_Applications_Get_Started/Gradio && python main.py

# Personal Branding Agent — see PLAN.md for pipeline setup
cd Build_RAG_Applications_Get_Started/PersonalBrandingAgent
```

- Icebreaker and Gradio demos serve on `http://127.0.0.1:7860` by default (Gradio default port)
- PersonalBrandingAgent is a library project — run components per `PLAN.md` phases

### Environment variables

| Project | Variables |
|---|---|
| `icebreaker` | `OPENROUTER_API_KEY` (required for real profiles), `PROXYCURL_API_KEY` (discontinued) |
| `Gradio` | None required (uses default model) |
| `PersonalBrandingAgent` | `OPENROUTER_API_KEY`, `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET` |

### Known issues

- **ProxyCurl discontinued** — the icebreaker bot's LinkedIn data extraction relied on ProxyCurl API, which was discontinued in Feb 2025. The project currently uses mock data (`--mock` flag). An alternative data source is needed for real-profile support.
- **Free model rotation** — OpenRouter's free-model lineup changes frequently. If a model ID returns "model not found," check the current free list at [openrouter.ai/models](https://openrouter.ai/models?max_price=0) and update `config.py`.
- **Parameter name drift** — `langchain-openai` major-version bumps rename constructor parameters (`max_tokens` → `max_completion_tokens`, `openai_api_key/openai_api_base` → `api_key/base_url`).
- **Base URL**: All projects use `https://openrouter.ai/api/v1`. A similar-looking `https://api.openrouter.ai/v1` does not resolve in many environments (DNS failure).
