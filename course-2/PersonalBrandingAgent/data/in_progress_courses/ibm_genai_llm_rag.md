# IBM Generative AI / LLM+RAG courses — learning & practice

## Status
IN PROGRESS (coursework currently studied). This maps the two IBM "GenAI" course
tracks plus the RAG/LLM/Agent practice found under `/home/alaabadawii/LLMs/IBM/`
and `/home/alaabadawii/LLMs/llm-env/`. Some projects completed (see
completed_projects/) but the course work itself continues.

## Course 1 — "Develop Generative AI Applications: Get Started" (completed practice)
- Guided project rebuilt end-to-end: a Flask + LangChain app with structured
  JSON output (see `completed_projects/genai_flask_app.md`,
  `book_movie_advisor.md`).
- Core topics practiced: prompt templates, LCEL chains (`prompt | llm | parser`),
  `JsonOutputParser` + Pydantic structured output, multi-model selection,
  OpenRouter as an OpenAI-compatible router (why chat-completions absorbs tokens).

## Course 2 — Advanced GenAI / RAG
- Completed RAG guided lab: `RAG_Lab.ipynb` — load -> split
  (`CharacterTextSplitter`, chunk_size=1000) -> embed/ingest to Chroma ->
  retrieval -> LLM (watsonx: granite, llama; FLAN-UL2) -> `RetrievalQA`,
  `ConversationBufferMemory`, `ConversationalRetrieval`, and a "make it an
  agent" wrap-up. Includes exercises (return source docs, swap models).
- Gradio practice (`course-2/Gradio/app.py`): a `gr.Interface` building
  sentences from paired sliders/dropdowns — Gradio UI practice.
- Transformers lab environment: `course-2/Gradio/.venv` with `transformers`,
  `huggingface_hub`, `gradio` — local HF model practice.
- Personal Branding Agent (RAG-aplication of this course) — see
  `in_progress_projects/personal_branding_agent.md`.

## Environment
`/home/alaabadawii/LLMs/llm-env/` is a Python venv with: langchain (0.2.11),
langchain_core, langchain_ibm, langchain_text_splitters, ibm_watsonx_ai,
torch (2.5.1+cu121), torchvision, etc. Confirms the frameworks were installed
and used locally.

## LEARNED vs PRACTICED vs IMPLEMENTED (honest)
- LEARNED/PRACTICED: RAG pipeline (load/split/embed/store/retrieve), LCEL,
  structured output, memory, Gradio, transformers basics, Chroma, watsonx.
- IMPLEMENTED (small, applying them): the course-1 apps, and a `data/` +
  Chroma + LangChain RAG plan for the Personal Branding Agent.
- Do NOT claim these courses = professional expertise.

## Provenance
`/home/alaabadawii/LLMs/IBM/course-1/GenAI_Flask_App/README.md`
`/home/alaabadawii/LLMs/IBM/course-2/PersonalBrandingAgent/RAG_Lab.ipynb`
`/home/alaabadawii/LLMs/IBM/course-2/Gradio/app.py`
`/home/alaabadawii/LLMs/llm-env/lib/python3.10/site-packages/`
`/home/alaabadawii/LLMs/IBM/course-2/PersonalBrandingAgent/PLAN.md`