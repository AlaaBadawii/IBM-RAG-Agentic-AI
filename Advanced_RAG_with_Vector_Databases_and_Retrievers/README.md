# Course 4 — Advanced RAG with Vector Databases and Retrievers

**Course status: Completed as of November 9, 2026 · Estimated duration: 8 hours**

[← Certificate overview](../README.md)

## Overview

The course studies vector-database mechanics, FAISS/Chroma, indexing concepts
such as HNSW, and advanced retrieval patterns in LangChain and LlamaIndex. The
retained implementation is a YouTube transcript summarizer and retrieval-based
Q&A application; it is not a repository implementation of every studied retriever.

## Main Learning Objectives

- Separate whole-document summarization from retrieval-based question answering.
- Choose chunk sizes and overlap for different tasks.
- Build a FAISS index and retrieve relevant transcript context.
- Understand how embeddings, indexing, and prompt grounding affect answer quality.
- Handle missing transcripts and model failures through an interactive UI.

## Project and Lab Index

| Project | State and relationship to the course | Documentation |
|---|---|---|
| YouTube RAG Summarizer & QA | Implemented single-file IBM-stack lab baseline; layered provider-independent rebuild remains planned | [README](youtube-rag-summarizer/README.md) |

The project also retains [lab instructions](youtube-rag-summarizer/lab-instructions.md)
and a [rebuild plan](youtube-rag-summarizer/PLAN.md). The plan is not evidence that
its proposed provider abstraction, timestamp metadata, or evaluation is implemented.

## Technologies and Implementation Details

- **LangChain:** `RecursiveCharacterTextSplitter`, `PromptTemplate`, and model invocation.
- **FAISS:** transcript indexing through `langchain-community`.
- **IBM watsonx.ai:** `WatsonxLLM` with `ibm/granite-4-h-small` and
  `WatsonxEmbeddings` with `ibm/granite-embedding-278m-multilingual`.
- **YouTube Transcript API:** English manual captions preferred, generated captions used as fallback.
- **Gradio:** `Blocks` UI with summary and question-answering actions.

[`ytbot.py`](youtube-rag-summarizer/ytbot.py) uses 800-character Q&A chunks with
100-character overlap and retrieves up to five chunks. Summarization uses
5,000-character chunks with 200-character overlap: each chunk is summarized, then
multiple partial summaries are combined in one final call. This is a hand-written
map-reduce-style workflow, not a LangChain `map_reduce` chain factory.

## Setup and Execution

The tracked source fixes the watsonx URL and `project_id="skills-network"` in
code. It does not read application environment variables or provide a local
API-key setup. A compatible IBM Skills Network runtime is needed for that baseline.

No `requirements.txt` or `.env.example` is tracked in the project. Required imports
come from `gradio`, `ibm-watsonx-ai`, `langchain`, `langchain-community`,
`langchain-ibm`, `youtube-transcript-api`, and a FAISS distribution such as
`faiss-cpu`. The legacy `langchain.prompts` and `langchain.text_splitter` imports
need a compatible pre-1.0 LangChain stack; an unqualified latest-version install
is not a verified setup.

From the repository root, after preparing a compatible runtime:

```bash
cd Advanced_RAG_with_Vector_Databases_and_Retrievers/youtube-rag-summarizer
python ytbot.py
```

The source binds Gradio to `0.0.0.0:7860`. This invocation is checked against the
entry point, not reported as an executed application run.

## Engineering Lessons and Limitations

- Summary chunks and retrieval chunks serve different context-budget requirements.
- A grounded prompt asks the model to decline unsupported answers, but is not an independent factual verifier.
- Timestamps are embedded in transcript text, not stored as structured chunk metadata or linked citations.
- The FAISS index is rebuilt for each Q&A action; persistence and cross-question caching are not implemented.
- No automated tests or measured retrieval evaluation are tracked. The separate rebuild plan describes future engineering work.
