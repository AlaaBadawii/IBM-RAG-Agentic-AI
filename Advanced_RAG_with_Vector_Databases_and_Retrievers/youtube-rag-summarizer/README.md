# YouTube RAG Summarizer & QA

A hands-on **Retrieval-Augmented Generation (RAG)** application that extracts YouTube video transcripts, summarizes them, and answers questions based on the video's content.

This project is part of my practical work while studying **RAG and Agentic AI** through the IBM learning program.

## Overview

The application takes a YouTube video URL and uses its transcript as the knowledge source.

For summarization, the transcript is passed directly to an IBM watsonx LLM.

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
       IBM watsonx LLM        IBM SLATE Embeddings
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
- Process transcript text and preserve timestamps
- Split transcripts into smaller chunks
- Generate embeddings using **IBM SLATE-30M**
- Store and search embeddings using **FAISS**
- Retrieve relevant transcript chunks for user questions
- Generate video summaries using an IBM watsonx LLM
- Answer questions using retrieved video context
- Interact with the application through a **Gradio** interface

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python |
| LLM | IBM watsonx |
| Embeddings | IBM SLATE-30M English |
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
5. **Embed** each chunk using IBM SLATE-30M.
6. **Index** the embeddings using FAISS.
7. **Retrieve** the most relevant chunks using similarity search.
8. **Pass** the retrieved context and question to the LLM.
9. **Generate** an answer grounded in the retrieved video content.

The lab retrieves the top relevant chunks from FAISS before generating the answer.

## Summarization Pipeline

Summarization follows a simpler path:

```text
YouTube URL
    ↓
Transcript
    ↓
Processed Transcript
    ↓
Summary Prompt
    ↓
IBM watsonx LLM
    ↓
Video Summary
```

The lab's summary prompt instructs the model to produce a concise paragraph, ignore timestamps, and focus on the spoken content.

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
├── requirements.txt
├── README.md
└── .env.example
```

> The structure may evolve as the implementation develops.

## Running the Application

Install the required dependencies and run:

```bash
python3.11 ytbot.py
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

🚧 **In Progress**

This repository documents my implementation and experimentation with the concepts covered in the lab.

## Source

Based on the **AI-Powered YouTube Summarizer, QA Tool with RAG, LangChain, FAISS** hands-on lab from IBM Skills Network.

The original lab covers transcript extraction, preprocessing, chunking, IBM watsonx models, IBM SLATE embeddings, FAISS similarity search, summarization, Q&A, and the Gradio interface.