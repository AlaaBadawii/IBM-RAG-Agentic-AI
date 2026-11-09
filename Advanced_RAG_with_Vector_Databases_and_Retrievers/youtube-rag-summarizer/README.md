# YouTube RAG Summarizer & QA

A hands-on **Retrieval-Augmented Generation (RAG)** application that extracts YouTube video transcripts, summarizes them, and answers questions based on the video's content.

This project is part of my practical work while studying **RAG and Agentic AI** through the IBM learning program.

**Status: Implemented single-file lab baseline; provider-independent rebuild planned.** [Course 4](../README.md) · [Certificate](../../README.md)

## Overview

The application takes a YouTube video URL and uses its transcript as the knowledge source.

For summarization, the transcript is split into larger chunks, each chunk is summarized by an IBM watsonx LLM, and multiple partial summaries are reduced into one final summary.

For question answering, the transcript is processed, split into chunks, embedded, indexed with FAISS, and retrieved based on the user's question before being passed to the LLM.

### Architecture

```text
                    YouTube Video
                          │
                          ▼
                 YouTube Transcript API
                          │
                          ▼
                Transcript Processing
                          │
              ┌───────────┴───────────┐
              │                       │
              ▼                       ▼
         Summarization             Chunking
              │                       │
              ▼                       ▼
       IBM watsonx LLM        IBM Granite Embeddings
                                      │
                                      ▼
                                  FAISS Index
                                      │
                                      ▼
                              Similarity Search
                                      │
                                      ▼
                              Relevant Context
                                      │
                                      ▼
                              Q&A Prompt + LLM
                                      │
                                      ▼
                                   Answer
```

## Features

- Extract transcripts from YouTube videos
- Preserve start times as text (`Text: ... Start: ...`), not structured citation metadata
- Split transcripts into smaller chunks
- Generate embeddings using **`ibm/granite-embedding-278m-multilingual`**
- Store and search embeddings using **FAISS**
- Retrieve relevant transcript chunks for user questions
- Generate video summaries using an IBM watsonx LLM
- Answer questions using retrieved video context
- Interact with the application through a **Gradio** interface

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python |
| LLM | IBM watsonx `ibm/granite-4-h-small` |
| Embeddings | IBM watsonx `ibm/granite-embedding-278m-multilingual` |
| Vector Store | FAISS |
| RAG Framework | LangChain |
| Transcript Extraction | YouTube Transcript API |
| UI | Gradio |

## RAG Pipeline

The question-answering workflow follows these steps:

1. **Extract** the YouTube video ID from the URL.
2. **Fetch** the video's English transcript.
3. **Process** the transcript into readable text while preserving start times.
4. **Chunk** the processed transcript using `RecursiveCharacterTextSplitter`.
5. **Embed** each chunk using `ibm/granite-embedding-278m-multilingual`.
6. **Index** the embeddings using FAISS.
7. **Retrieve** the most relevant chunks using similarity search.
8. **Pass** the retrieved context and question to the LLM.
9. **Generate** an answer grounded in the retrieved video content.

The source uses 800-character chunks with 100-character overlap and retrieves up to five chunks (`min(RETRIEVAL_K, len(chunks))`). The FAISS index is recreated for each question.

## Summarization Pipeline

Summarization uses a hand-written chunked map-reduce-style path:

```text
YouTube URL
    ↓
Transcript
    ↓
Processed Transcript → 5,000-character chunks (200 overlap)
    ↓
Per-chunk Summary Prompt
    ↓
IBM watsonx LLM
    ↓
Partial Summaries → Final combination call (when there is more than one chunk)
```

For a single chunk, its summary is returned without another call. For multiple chunks, a final prompt combines the partial summaries and removes repetition. Prompts ask for clear, concise paragraphs grounded in the transcript and omit timestamps. This is not a LangChain summarization-chain factory.

## Key Concepts Practiced

This project provides hands-on practice with:

- YouTube transcript extraction
- Text preprocessing
- Text chunking
- Chunk overlap
- Embeddings
- Vector similarity search
- FAISS vector indexing
- Retrievers
- Prompt templates
- LLM chains
- Retrieval-Augmented Generation
- LLM-based summarization
- Building an AI application interface

## Project Structure

```text
youtube-rag-summarizer/
│
├── ytbot.py
├── PLAN.md                 # Proposed layered rebuild, not implemented
├── lab-instructions.md     # Original guided lab reference
└── README.md
```

No dependency manifest, `.env.example`, or automated test suite is tracked.

## Running the Application

The baseline targets IBM Skills Network authentication: `ytbot.py` fixes the URL
and `project_id="skills-network"` and does not read application environment
variables. There is no normal local API-key configuration path in the script.

Required packages are `gradio`, `ibm-watsonx-ai`, `langchain`,
`langchain-community`, `langchain-ibm`, `youtube-transcript-api`, and FAISS
(commonly `faiss-cpu`). The legacy LangChain imports require a compatible pre-1.0
stack; no reproducible pinned installation is provided here.

From the repository root, in a compatible runtime:

```bash
cd Advanced_RAG_with_Vector_Databases_and_Retrievers/youtube-rag-summarizer
python ytbot.py
```

The lab serves the Gradio application on port `7860`.

## Example

The lab provides a sample RAG video for testing:

```text
https://www.youtube.com/watch?v=T-D1OfcDW1M
```

Example questions include:

- How does one reduce hallucinations?
- Which problems does RAG solve, according to the video?

These questions demonstrate how the application retrieves relevant transcript context before generating an answer.

## What I Learned

Through this implementation, I am practicing how to build a RAG application from the ground up:

```text
Unstructured Content
        ↓
Document Processing
        ↓
Chunking
        ↓
Embeddings
        ↓
Vector Database
        ↓
Retrieval
        ↓
Context + Question
        ↓
LLM
        ↓
Grounded Response
```

The main takeaway is understanding **how retrieval connects external knowledge to an LLM**, rather than treating the LLM itself as the knowledge source.

## Status

The IBM-stack baseline is implemented. [`PLAN.md`](PLAN.md) describes a future
layered rebuild with provider seams, timestamp-aware metadata, and evaluation;
those additions are not implemented. No execution or test-pass result is claimed
by this documentation update.

## Source

Based on the **AI-Powered YouTube Summarizer, QA Tool with RAG, LangChain, FAISS** hands-on lab from IBM Skills Network.

The original lab covers transcript extraction, preprocessing, chunking, watsonx models, FAISS retrieval, summarization, Q&A, and Gradio. SLATE appears as a commented legacy ID in `ytbot.py`; the active embedding model is Granite multilingual.
