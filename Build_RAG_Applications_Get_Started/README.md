# Course 2 — Build RAG Applications: Get Started

**Course status: Completed as of November 9, 2026 · Estimated duration: 7 hours**

[← Certificate overview](../README.md)

## Overview and Learning Objectives

The course introduces retrieval-augmented generation: loading documents, splitting
them into chunks, creating embeddings, indexing, retrieving relevant context, and
generating grounded answers. It compares LangChain and LlamaIndex and uses Gradio
to expose model-backed workflows through interactive interfaces.

- Understand the difference between an LLM's prior knowledge and retrieved context.
- Follow the load → split → embed → index → retrieve → generate pipeline.
- Compare query-engine abstractions with explicit retrieval steps.
- Build Gradio interfaces from functions and input/output components.

Course completion is separate from the availability and maturity of the retained projects.

## Project and Lab Index

| Entry | Actual repository state | Documentation |
|---|---|---|
| Gradio UI Experiments | Implemented sentence builder; experimental image script with an incompatible model/classifier flow | [README](Gradio/README.md) |
| LinkedIn Icebreaker Bot (`icebreaker`) | Unavailable gitlink; source is not tracked by this repository | Historical context below |
| Personal Branding Agent | Extracted independent project, maintained in its own repository | [Standalone repository](https://github.com/AlaaBadawii/PersonalBrandingAgent) |

### Gradio UI Experiments

[`Gradio/app.py`](Gradio/app.py) builds a deterministic sentence from sliders,
dropdowns, checkboxes, and radio buttons. It runs on `127.0.0.1:7860` and needs no
LLM API key.

[`Gradio/main.py`](Gradio/main.py) retains an image-interface experiment using
`Salesforce/blip-image-captioning-base`, torchvision preprocessing, and an
ImageNet label list. BLIP captioning output is not ImageNet classification output;
the current inference flow needs a code correction before it can be described as
a working captioner or classifier. See the project README for details.

### Icebreaker Availability

The Git index records `icebreaker` as mode `160000`, pointing to commit
`9b8a9da7b0381686874d71740e74c72a71b7f74f`. No `.gitmodules` configuration is
tracked and the referenced commit is unavailable in the parent repository.
A fresh clone therefore does not provide runnable Icebreaker source. Any local
files under that path are not GitHub-visible evidence for this portfolio.

Historically, this was an Icebreaker RAG lab/rebuild associated with LlamaIndex,
profile retrieval, and provider substitution. Its current commands, dependencies,
ports, API requirements, and implementation status cannot be verified from this
repository. Mock profile data alone would not remove the need for an API key when
a workflow still calls a hosted LLM.

### Extracted Personal Branding Agent

[PersonalBrandingAgent — Abu Prompt](https://github.com/AlaaBadawii/PersonalBrandingAgent)
grew into an independent implementation of evidence-grounded LinkedIn content
generation and publishing. Its engineering work includes a curated knowledge
base, hybrid retrieval, deterministic verification, duplicate-safe publishing,
and workflow state. Setup, test results, operational status, and remaining work
belong to that standalone repository.

## Technologies Actually Retained Here

- Python and Gradio (`Interface`, input/output components, launch configuration).
- `transformers`, PyTorch, torchvision, Pillow, and `requests` in the image experiment.
- LangChain, LlamaIndex, embeddings, and vector-store workflows are course concepts;
  the missing Icebreaker and extracted agent do not supply runnable RAG source in this directory.

## Setup and Execution

From the repository root, for the sentence-builder lab:

```bash
cd Build_RAG_Applications_Get_Started/Gradio
python3 -m venv venv
source venv/bin/activate
python -m pip install gradio
python app.py
```

Open <http://127.0.0.1:7860>. No `requirements.txt` or `.env.example` is tracked for
these demos. The image experiment imports additional packages and is documented
as experimental in the [project README](Gradio/README.md).

## Engineering Lessons

- Retrieval quality and chunk boundaries determine the context available to generation.
- A query engine can hide several steps; understanding those steps helps debug grounding.
- A model's output contract must match preprocessing and UI output types.
- A gitlink is not a copy of a project's source; repository availability must be verified separately.
- Independent extensions can outgrow a course folder and need their own documentation and lifecycle.
