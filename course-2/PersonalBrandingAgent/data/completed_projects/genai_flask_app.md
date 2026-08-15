# GenAI Flask App — LangChain playground (IBM course rebuild)

## Status
COMPLETED (implemented, run locally). Source:
`/home/alaabadawii/LLMs/IBM/course-1/GenAI_Flask_App/`.

## What this is
A Flask web app where you type a message, pick one of three LLMs (Llama, Granite,
Mistral), and get a structured JSON response (summary + sentiment score +
suggested reply), validated against a schema. Rebuild of the IBM "Develop
Generative AI Applications: Get Started" guided project, with IBM watsonx.ai
replaced by OpenRouter.

## What's actually there (evidence)
- `app.py` — Flask routes `GET /`, `POST /generate`.
- `model.py` — LangChain LCEL chain: one shared `ChatPromptTemplate` →
  model (`ChatOpenAI` against OpenRouter) → `JsonOutputParser`, piped via `|`.
- `config.py` — env vars, model IDs, generation params.
- `llm_test.py` — CLI sanity check calling all 3 models (no Flask).
- `templates/index.html`, `static/script.js`, `static/styles.css`.
- `.env.example`.

## Why it matters (technical decision documented)
- Original course used watsonx token-heavy per-model templates (Llama
  `<|begin_of_text|>`, Mistral `[INST]`, Granite `<|system|>`). Because
  OpenRouter/OpenAI expose chat-completions (`{role, content}` messages), the
  project removed three per-model templates and used one shared
  `ChatPromptTemplate` — the provider applies the model template server-side.
- Structured output via Pydantic `AIResponse` + `JsonOutputParser`; the
  chain's parser raises on invalid JSON -> 500 handler.

## Skills exercised (from course, applied here)
- Prompt templates, LCEL chains, structured output, Pydantic, etc.

## Technologies
Python 3.10+, Flask, LangChain LCEL, langchain-openai, Pydantic, OpenRouter,
HTML/CSS/JS.

## Provenance
`/home/alaabadawii/LLMs/IBM/course-1/GenAI_Flask_App/README.md` (documents the
course-to-OpenRouter changes file by file)