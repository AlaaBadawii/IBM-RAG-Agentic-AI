# DocChat — Multi-Agent RAG

DocChat is a local Gradio application that answers questions over uploaded
documents with a multi-agent RAG workflow. It combines document conversion,
hybrid retrieval, grounded answer generation, and a separate verification step.

The project was built as an IBM certification learning project to explore how
retrieval, agent orchestration, and answer verification fit together in a
practical RAG application. It is intended for learning and experimentation, not
as a production service.

## Learning outcomes

Building the project provided hands-on practice with:

- Modelling an agent workflow as an explicit, testable LangGraph state machine.
- Separating retrieval, answer generation, and verification instead of treating
  a single model response as trustworthy.
- Designing bounded retry behaviour and explicit failure states.
- Testing LLM-backed systems offline with deterministic fakes.
- Handling document conversion, caching, and upload validation as separate
  concerns from retrieval.

## What this project demonstrates

- Converting PDF, DOCX, Markdown, and text uploads into chunked documents.
- Combining lexical retrieval (BM25) with dense retrieval (watsonx embeddings +
  Chroma) in an ensemble retriever.
- Coordinating specialised agents with a LangGraph state machine.
- Rejecting irrelevant questions before answer generation.
- Verifying a draft answer against the same retrieved evidence.
- Bounding retries and returning an explicit "unverified" result instead of
  presenting an unverified answer as successful.
- Testing the agent workflow and document processor with offline fakes, without
  making live watsonx calls.

## Architecture

```text
                    Gradio UI (app.py)
                           |
                           v
              DocumentProcessor (Docling)
        validate -> convert -> split -> cache chunks
                           |
                           v
                 RetrieverBuilder
        Watsonx embeddings + Chroma  +  BM25
                           |
                    EnsembleRetriever
                           |
                           v
             AgentWorkflow (LangGraph)
                           |
          +----------------+----------------+
          |                                 |
          v                                 v
  RelevanceChecker                    ResearchAgent
  CAN_ANSWER / PARTIAL / NO_MATCH     draft answer from context
          |                                 |
          |                                 v
          |                         VerificationAgent
          |                    Supported / Relevant report
          |                                 |
          +---------- retry / accept / unverified ----------+
```

### Document processing

`document_processor/file_handler.py` validates uploads and converts them to
Markdown with Docling. Uploads are limited to 50 MB per file and 200 MB total.
Markdown is split on `#` and `##` headings, and each chunk keeps its source
filename. Converted chunks are cached locally under `document_cache/` for
24 hours.

The PDF pipeline is configured through environment variables:

- `DOCLING_DO_OCR` (default `false`)
- `DOCLING_DO_TABLE_STRUCTURE` (default `false`)
- `DOCLING_DOCUMENT_TIMEOUT` (default `300.0` seconds)

OCR and table-structure extraction are disabled by default because the primary
learning examples are text-based PDFs. Enable them for scanned documents or when
table structure matters. The processor rejects failed or partially converted
documents, as well as conversions that produce no readable text, rather than
caching an incomplete result.

### Hybrid retrieval

`retriever/builder.py` builds two retrievers over the same chunks:

1. **BM25** for lexical matching.
2. **Chroma** with the `ibm/slate-125m-english-rtrvr-v2` embedding model for
   semantic similarity.

An `EnsembleRetriever` combines them using `HYBRID_RETRIEVER_WEIGHTS`
(default `[0.4, 0.6]`). The workflow retrieves once and passes that same
document set to relevance checking, research, and verification.

### Multi-agent workflow

`agents/workflow.py` implements a LangGraph state machine:

1. **Relevance checking** — `RelevanceChecker` classifies the retrieved
   documents as `CAN_ANSWER`, `PARTIAL`, or `NO_MATCH`. `NO_MATCH` stops the
   workflow without calling the research model.
2. **Research** — `ResearchAgent` drafts an answer using only the retrieved
   context. The prompt instructs the model not to follow instructions found in
   documents or invent citations.
3. **Verification** — `VerificationAgent` checks whether the draft is supported
   by the retrieved context and returns a structured report containing
   `Supported` and `Relevant` decisions.
4. **Accept, retry, or fail** — a verified answer ends the workflow. Failed
   verification triggers another research attempt, up to
   `MAX_RESEARCH_ATTEMPTS` (3). If all attempts fail, the workflow returns an
   explicit unverified message.

The retrieved documents are shared across all stages. Retries use the same
question and document set because the research agent does not currently accept
verifier feedback.

## Technologies

- Python 3.12
- Gradio 5 for the local UI
- IBM watsonx.ai (`ModelInference`) for relevance, research, and verification
- `langchain-ibm` / `WatsonxEmbeddings` for embeddings
- LangChain, LangGraph, and `langchain-community`
- Chroma and BM25 (`rank-bm25`) for hybrid retrieval
- Docling for document conversion
- `pydantic-settings` for environment configuration
- Loguru for application logging
- pytest for tests

The pinned versions are in `requirements.txt`; development dependencies are in
`requirements-dev.txt`.

## Prerequisites

- Python 3.12
- An IBM watsonx.ai account, project, and API key
- Access to a chat model supported by your watsonx project
- A supported operating system for the pinned dependencies

`requirements.txt` was generated from a Linux environment and includes CUDA
runtime packages pulled in by PyTorch. Installation can therefore be large even
when the application runs on CPU. The Docling layout model falls back to a
pure-PyTorch path if an optional custom CUDA kernel is unavailable.

## Setup

```bash
git clone <your-repository-url>
cd DocChat_Multi_Agent_RAG

python3.12 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

For tests, install the development requirements:

```bash
pip install -r requirements-dev.txt
```

### Configuration

Create a local environment file from the example:

```bash
cp .env.example .env
```

Then fill in your own values. Do not commit `.env`.

Required variables:

| Variable | Purpose |
| --- | --- |
| `WATSONX_API_KEY` | IBM Cloud API key used by the agents and embeddings |
| `WATSONX_PROJECT_ID` | watsonx project ID |
| `WATSONX_URL` | watsonx API endpoint for your region |
| `WATSONX_MODEL_ID` | Chat model used by the three agents |

Optional application variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `WATSONX_PROJECT_NAME` | unset | Declared in settings but not used by the application |
| `CHROMA_DB_PATH` | `./chroma_db` | Chroma persistence directory |
| `CHROMA_COLLECTION_NAME` | `documents` | Chroma collection name |
| `VECTOR_SEARCH_K` | `10` | Number of dense-retrieval results |
| `HYBRID_RETRIEVER_WEIGHTS` | `[0.4, 0.6]` | BM25 and vector weights |
| `LOG_LEVEL` | `INFO` | Minimum level for the `app.log` file handler |
| `CACHE_DIR` | `document_cache` | Converted-document cache |
| `CACHE_EXPIRE_DAYS` | `7` | Declared in settings; the processor currently uses a fixed 24-hour cache TTL |
| `DOCLING_DO_OCR` | `false` | Enable OCR for scanned PDFs |
| `DOCLING_DO_TABLE_STRUCTURE` | `false` | Enable table-structure extraction |
| `DOCLING_DOCUMENT_TIMEOUT` | `300.0` | Per-document Docling timeout in seconds |

The model and embedding identifiers are configured in code:
`ibm/slate-125m-english-rtrvr-v2` is used for embeddings, while the chat model
comes from `WATSONX_MODEL_ID`.

## Run the application

```bash
python app.py
```

Open `http://127.0.0.1:5000` in a browser. The app is intentionally bound to
localhost and does not enable Gradio sharing.

Upload one or more supported files, enter a question, and press **Submit**. The
answer and verification report are shown in separate panels.

## Run the tests

```bash
pytest
```

or:

```bash
python -m pytest
```

The suite is designed to run offline: Docling is mocked for PDF-style
conversions, and the watsonx agents are replaced with fakes. One integration
check performs a small real Markdown conversion. The tests do not make live
watsonx API calls.

## Project structure

```text
app.py                         Gradio UI and per-session retriever state
.env.example                   Safe environment-variable template
.gitignore                     Local data, caches, secrets, and artifacts
README.md                      Project documentation
agents/
  relevance_checker.py         Document/question relevance classification
  research_agent.py            Grounded draft-answer generation
  verification_agent.py        Answer-support verification
  workflow.py                  LangGraph orchestration and retry policy
config/
  constants.py                 File-size and file-type limits
  settings.py                  Environment-backed settings
document_processor/
  file_handler.py              Validation, Docling conversion, chunking, cache
retriever/
  builder.py                   BM25 + Chroma hybrid retriever
utils/
  logging.py                   Loguru configuration and app.log output
tests/                         Offline unit and workflow tests
requirements.txt               Pinned runtime dependencies
requirements-dev.txt           Test dependencies
pytest.ini                     Test discovery configuration
```

## Known limitations

- **Live services are required for the full workflow.** The repository does not
  include a recorded end-to-end run against watsonx. You need valid credentials
  and network access to exercise the real agents.
- **Example files are not bundled.** `app.py` refers to PDFs under `examples/`,
  but that directory is not included. Upload your own documents or add files
  locally.
- **The verifier does not receive the original question.** It receives the draft
  answer and the retrieved documents, so its `Relevant` decision is weaker than
  a question-aware relevance check.
- **Retries are not feedback-driven.** Failed verification reruns research with
  the same question and documents because `ResearchAgent.research` has no
  feedback parameter.
- **Chroma is persistent and additive.** Building a retriever with
  `Chroma.from_documents` writes into the configured collection and does not
  clear previous documents. Repeated runs can accumulate stale or duplicate
  vectors unless you manage the collection separately.
- **Citations are document-level.** The Markdown splitter attaches the source
  filename but not page numbers, so page-level citations are not available.
- **PDF extraction is text-first by default.** OCR and table-structure extraction
  are disabled by default; scanned PDFs and table-heavy documents may lose
  content until those options are enabled.
- **Cache semantics are local.** The cache is a local pickle store keyed by
  file content. It is not intended to be portable or shared, and conversion
  settings are not part of the cache key.
- **The cache TTL is fixed.** `CACHE_EXPIRE_DAYS` is declared but not used;
  `DocumentProcessor.CACHE_TTL` is fixed at 24 hours.
- **No authentication or multi-user isolation.** The app is a local learning
  tool and should not be exposed as a public service.
- **The dependency set is large.** The pinned requirements include CUDA-related
  packages; a CPU-only environment may need a tailored installation.

## Future improvements

- Pass the user question to the verification agent and make relevance
  verification question-aware.
- Feed verifier findings back into research retries.
- Add page-level metadata and citations during document conversion.
- Make Chroma collection lifecycle and cleanup explicit, including per-session
  isolation or deduplication.
- Include the conversion configuration in the document-cache key.
- Add a lightweight offline end-to-end demo with recorded model responses.
- Provide an optional CPU-only dependency path and a smaller development
  requirements set.
- Add a license and contribution guidelines before public distribution.

## Data and publication notes

Local PDFs, document caches, Chroma databases, logs, virtual environments, and
`.env` files are excluded by `.gitignore`. Only publish documents you have the
right to redistribute. The example paths in `app.py` are placeholders for
locally supplied, appropriately licensed documents. If you intentionally add a
redistributable example PDF, adjust the ignore rule or use `git add -f` after
confirming its license.
