# Personal Branding Agent

A production-oriented agent that generates, evaluates, and publishes authentic LinkedIn posts grounded in a personal knowledge base. Built as an extension of the IBM course **"Build RAG Applications: Get Started"**, applying RAG concepts to a real-world project.

The project is currently in progress: the **knowledge base** (a structured `data/` corpus) and the **LinkedIn OAuth integration** are complete; the ingest → retrieve → generate → evaluate → publish pipeline is defined in `PLAN.md` (10 phases) and being built incrementally.

---

## 1. What this project does

The Personal Branding Agent bridges RAG and real-world application:

- **Knowledge base** — a structured `data/` corpus containing completed/in-progress projects, courses, certificates, evidence (with evidence states), stories/lessons, vision/goals, writing style, and public positioning.
- **LinkedIn OAuth** — full OAuth 2.0 flow with token refresh, and the ability to publish posts via the LinkedIn REST API (`/rest/posts`, `w_member_social` scope).
- **RAG pipeline** (planned) — ingest the knowledge base into ChromaDB, retrieve relevant context, generate a LinkedIn post via an LLM, evaluate it against quality gates (PASS / REVISE / REJECT), and optionally publish it.

The architecture separates concerns to keep each component evolvable:

```
knowledge base (data/) → retrieve → generate → evaluate → publish (Auth_handling/)
```

---

## 2. Project structure

```
PersonalBrandingAgent/
├── config.py                  # Config: API keys, model, embedding, ChromaDB settings
├── PLAN.md                    # 10-phase roadmap for the full pipeline
├── RAG_Lab.ipynb              # Completed IBM course RAG notebook (reference)
├── requirements.txt
├── .env.example
├── .gitignore
├── data/                      # Structured personal knowledge base
│   ├── completed_projects/
│   ├── in_progress_projects/
│   ├── in_progress_courses/
│   ├── certificates/
│   ├── evidence/
│   ├── stories_lessons/
│   ├── vision_goals/
│   ├── writing_style/
│   ├── public_positioning/
│   └── audit/
├── Auth_handling/             # LinkedIn OAuth + publish scripts
└── docs/                      # Architecture docs, phase docs, ADRs
    ├── decisions/ADRs/        # Architecture Decision Records
    └── ...
```

---

## 3. Configuration

`config.py` exposes the following configuration:

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | OpenRouter API key (via OpenAI-compatible endpoint) |
| `LINKEDIN_CLIENT_ID` | LinkedIn OAuth application client ID |
| `LINKEDIN_CLIENT_SECRET` | LinkedIn OAuth application client secret |
| `MODEL_ID` | LLM model slug (default: `deepseek/deepseek-v4-flash`) |
| `GEN_PARAMS` | Generation parameters (`max_new_tokens`, `temperature`) |
| `OPENROUTE_BASE_URL` | OpenRouter API base URL |
| `EMBEDDING_MODEL` | SentenceTransformer model (`all-MiniLM-L6-v2`) |
| `CHROMA_DIR` | Persistent ChromaDB directory |
| `CHUNK_SIZE` | Chunk size for document splitting |
| `CHUNK_OVERLAP` | Chunk overlap for document splitting |
| `TOP_K` | Number of retrieval results |

---

## 4. Knowledge Base (`data/`)

The `data/` directory is the core asset of this project. Each subdirectory contains a specific category of personal information:

| Directory | Contents |
|---|---|
| `completed_projects/` | Finished projects with descriptions, outcomes, and evidence |
| `in_progress_projects/` | Projects currently being worked on |
| `in_progress_courses/` | Courses in progress (with status tracking) |
| `certificates/` | Earned certificates with issue dates and credential IDs |
| `evidence/` | Evidence items for each claim, with state tracking (pending/verified/accepted) |
| `stories_lessons/` | Professional stories and lessons learned |
| `vision_goals/` | Career vision and professional goals |
| `writing_style/` | Preferred writing style, tone guidelines, and format preferences |
| `public_positioning/` | How you want to be perceived professionally |
| `audit/` | Audit trail for data changes |

This structured corpus serves as the retrieval source for the RAG pipeline — the agent can look up relevant projects, certificates, or stories when generating a LinkedIn post.

---

## 5. LinkedIn OAuth

The `Auth_handling/` directory contains the LinkedIn OAuth 2.0 integration:

- **OAuth 2.0 flow** — authorization code → tokens, with refresh token handling
- **Token management** — persistent storage and automatic refresh of expired tokens
- **Post publishing** — scripts to publish posts via the LinkedIn REST API (`/rest/posts`, `userinfo`, `w_member_social` scope)

### Setup

1. Create a LinkedIn Developer Application at <https://www.linkedin.com/developers/>
2. Set the redirect URI to match your local environment
3. Add `LINKEDIN_CLIENT_ID` and `LINKEDIN_CLIENT_SECRET` to `.env`
4. Run the OAuth setup script to authorize your account

---

## 6. RAG Lab (Reference)

`RAG_Lab.ipynb` is the completed IBM course notebook **"Summarize Private Documents Using RAG, LangChain, and LLMs"**. It covers:

- `TextLoader` → `CharacterTextSplitter` (chunk_size=1000) → `HuggingFaceEmbeddings` + Chroma
- `RetrievalQA`, `ConversationBufferMemory`, `ConversationalRetrievalChain`
- A "wrap it into an agent" function
- Source-return and model-swap exercises

This notebook is retained as a reference and does not require IBM credentials to run the core concepts.

---

## 7. Setup

**Requirements:** Python 3.10+, an OpenRouter account and API key, a LinkedIn Developer application.

```bash
cd PersonalBrandingAgent
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your keys:

```
OPENAI_API_KEY=sk-or-v1-...
LINKEDIN_CLIENT_ID=your-linkedin-client-id
LINKEDIN_CLIENT_SECRET=your-linkedin-client-secret
```

---

## 8. Current status

| Component | Status |
|---|---|
| Knowledge base (`data/`) | Complete — structured corpus with evidence states |
| LinkedIn OAuth (`Auth_handling/`) | Complete — full OAuth flow + publish capability |
| RAG pipeline (ingest → retrieve → generate → evaluate → publish) | In progress — defined in `PLAN.md` (10 phases) |
| Evaluation and quality gates | Planned |
| Publishing pipeline | Partially built (OAuth + publish scripts exist) |

See `PLAN.md` for the full 10-phase roadmap.

---

## 9. Skills demonstrated

- RAG concepts applied to a real project (not just the course lab)
- Evidence-grounded generation with quality gates
- OAuth 2.0 integration with refresh token handling
- Modular architecture separating knowledge, reasoning, generation, evaluation, and tools
- LinkedIn REST API integration
- ChromaDB for vector storage
- SentenceTransformer embeddings for semantic retrieval

---

## 10. Notes

- The `.env` file must be created by the developer and should never be committed. It is already in `.gitignore`.
- The ChromaDB directory (`chroma_db/`) is excluded via `.gitignore`.
- The RAG pipeline is the main work in progress — follow `PLAN.md` for implementation phases.
- The knowledge base format (structured data with evidence states) is designed to support deterministic agent workflows with human-in-the-loop publishing.
