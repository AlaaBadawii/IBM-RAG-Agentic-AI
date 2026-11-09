# Course 1 — Develop Generative AI Applications: Get Started

**Course status: Completed as of November 9, 2026 · Estimated duration: 10 hours**

[← Certificate overview](../README.md)

Three Flask + LangChain applications built as practice for IBM's "Develop Generative AI Applications: Get Started" course. All three replace IBM's watsonx.ai with **OpenRouter** (an OpenAI-compatible chat-completions API) and guide JSON output using Pydantic schemas and LangChain's `JsonOutputParser`.

Every backend chain follows the same LCEL pattern — `prompt | llm | parser` — and returns parsed Python dicts instead of raw text. The schemas supply format instructions; these apps do not separately validate the returned dicts with Pydantic. The projects differ in domain and in whether they offer single-model or multi-model comparison.

## Learning Objectives

- Compose prompts, model clients, and output parsers as reusable LCEL chains.
- Compare model behavior while keeping application inputs and output formats consistent.
- Integrate a model-backed JSON endpoint with a Flask frontend.
- Distinguish prompt-level constraints from deterministic output validation.

---

## Projects

| Project | Relationship to the course | Documentation |
|---|---|---|
| GenAI Flask App | Guided-project rebuild with a different provider | [README](GenAI_Flask_App/README.md) |
| AI Email Assistant | Independent practice extension with parallel comparison | [README](AI_Email_Assistant/README.md) |
| Book/Movie Advisor | Independent practice extension with a nested output schema | [README](Book_Movie_Advisor/README.md) |

### GenAI Flask App (`GenAI_Flask_App/`)

The course guided project rebuilt with OpenRouter. Pick one of three configured models (Llama, DeepSeek R1, Mistral) and request JSON containing `summary`, `sentiment` (intended range 0–100), and `response`. The legacy `granite` UI/function name and `GRANITE_MODEL_ID` actually select `deepseek/deepseek-r1`; no Granite model is currently configured. Includes a CLI sanity-check script (`llm_test.py`) that calls all three models without starting Flask.

- Single `ChatPromptTemplate` with system + human messages replaces the course's three per-model raw-text templates with model-specific special tokens
- LCEL chain: `prompt_template | model | json_parser`
- Dark-themed chat UI with message bubbles, sentiment bar, and a model selector
- Pinned dependencies in `requirements.txt` (`langchain-openai==0.2.6`, `langchain-core==0.3.15`, etc.)

### AI Email Assistant (`AI_Email_Assistant/`)

Generates polished emails — subject line, body, tone, and improvement suggestions — as structured JSON. Adds a **Compare All** mode that fires the same prompt at four models in parallel (frontend `Promise.all`) and renders per-model cards with latency, character length, and a subject-quality heuristic score (0–10).

- 4 OpenRouter models: `deepseek/deepseek-v4-flash`, `meta-llama/llama-3.1-8b-instruct`, `mistralai/mistral-7b-instruct`, `qwen/qwen3-8b`
- Modular layout: `config.py` / `model.py` / `parser.py` / `prompts.py` / `services/ai_service.py`
- XSS-safe rendering via `escapeHtml()` on all dynamic output in the frontend
- `plan.md` documents real bugs encountered: wrong OpenRouter base URL (`api.openrouter.ai` DNS failure), intermittent `OutputParserException` on markdown-wrapped JSON, dependency drift between langchain versions

### Book/Movie Advisor (`Book_Movie_Advisor/`)

Takes a free-text mood and requests 3 book/movie recommendation cards using a nested Pydantic `RecommendationList` schema as format guidance. There are 9 configured OpenRouter models; the dropdown is maintained separately in `templates/index.html`.

- `Recommendation` schema: `title`, `type` (`Literal["book", "movie"]`), `genre`, `why_you_ll_love_it`, `mood_match` (0–10), `where_to_find_it`
- Single-shot prompt with one few-shot example; `Literal` describes the allowed book/movie values in the schema, but returned values and list length are not independently validated
- CSS-grid frontend with book/movie cards, a mood-match progress bar, and escaping for generated text fields; the numeric score is assumed to have the expected type
- Includes `pyrightconfig.json` for static type-checker configuration

---

## Tech Stack

Only libraries actually imported in source code:

- **Python** 3.10+
- **Flask** — web framework (all three projects)
- **langchain-core**, **langchain-openai** — LCEL chains, `ChatPromptTemplate`, `JsonOutputParser`, `ChatOpenAI`
- **Pydantic** — structured output schemas (`BaseModel`, `Field`, `Literal`)
- **python-dotenv** — environment variable loading
- **OpenRouter** — LLM provider via OpenAI-compatible chat-completions API (`ChatOpenAI` with `base_url="https://openrouter.ai/api/v1"`)

---

## What's Built

- Three runnable Flask apps, each with `GET /` and a `POST` endpoint
- Schema-guided JSON output via `JsonOutputParser` + Pydantic in every project (JSON parsing, not independent schema validation)
- LCEL chains (`prompt | llm | parser`) in all three projects
- Multi-model selection via OpenRouter: 3 models (GenAI Flask App), 4 models (AI Email Assistant), 9 models (Book/Movie Advisor)
- **Compare All** mode in AI Email Assistant — parallel frontend fan-out with per-model latency, length, and subject-quality metrics
- CLI sanity-check script (`llm_test.py`) in GenAI Flask App
- HTML escaping for generated text fields; the Advisor's numeric score still needs independent type/range validation
- Pinned requirements in GenAI_Flask_App (`requirements.txt` with exact versions)
- `pyrightconfig.json` for static type checking in Book/Movie Advisor
- Correct OpenRouter base URL (`https://openrouter.ai/api/v1`) in all projects

---

## Planned / Not Yet Built

- **Server-side fan-out for Compare All** — the AI Email Assistant's "Compare All" is frontend-only; each model request is fired independently by `script.js`. Server-side fan-out is listed as a stretch goal in `plan.md` but is not implemented.
- **Conversation memory / streaming** — both mentioned as stretch goals in `plan.md`; neither is implemented.
- **Prompt version selector** — ability to switch between different prompt styles; listed in `plan.md` stretch goals, not implemented.
- **Export features** — download generated email as `.txt` or one-click copy; listed in `plan.md` stretch goals, not implemented.
- **Conversation history / SQLite persistence** — listed in `plan.md` stretch goals, not implemented.
- **No `.gitignore` in GenAI_Flask_App** — the other two projects include `.gitignore` files; GenAI_Flask_App does not.
- **`Book_Movie_Advisor/Plan.md` subtasks all marked `[ ] pending`** — the plan file describes intended architecture but all its status markers are unstarted. The actual code in the folder (app, model, config, templates) is implemented and functional; this discrepancy is in the plan file itself, not the code.

---

## Setup / Run

Each project is self-contained with its own `requirements.txt` and uses environment variables for secrets. **Never commit `.env` files.**

For example, from the repository root:

```bash
cd Develop_Generative_AI_Applications_Get_Started/GenAI_Flask_App
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env   # set OPENROUTER_API_KEY
python app.py
```

### Run commands

Each line below is an independent example starting at the repository root. Use a separate environment for each project.

```bash
# GenAI Flask App — sanity check (no Flask)
cd Develop_Generative_AI_Applications_Get_Started/GenAI_Flask_App && python llm_test.py

# GenAI Flask App — chat UI
cd Develop_Generative_AI_Applications_Get_Started/GenAI_Flask_App && python app.py

# AI Email Assistant — email form
cd Develop_Generative_AI_Applications_Get_Started/AI_Email_Assistant && python app.py

# Book/Movie Advisor — recommendation UI
cd Develop_Generative_AI_Applications_Get_Started/Book_Movie_Advisor && python app.py
```

All apps serve on `http://127.0.0.1:5000` by default.

### Environment variables

| Project | Variables |
|---|---|
| `GenAI_Flask_App` | `OPENROUTER_API_KEY` (required), `OPENROUTER_SITE_URL` (optional), `OPENROUTER_SITE_NAME` (optional) |
| `AI_Email_Assistant` | `OPENROUTER_API_KEY` |
| `Book_Movie_Advisor` | `OPENROUTER_API_KEY` |

### Known issues

- **Base URL**: All projects use `https://openrouter.ai/api/v1`. A similar-looking `https://api.openrouter.ai/v1` does not resolve in many environments (DNS failure). This was a real bug encountered in the AI Email Assistant build.
- **Free model rotation**: OpenRouter's free-model lineup changes frequently. If a model ID returns "model not found", check the current free list at [openrouter.ai/models](https://openrouter.ai/models?max_price=0) and update `config.py`.
- **Parameter name drift**: `langchain-openai` major-version bumps rename constructor parameters (`max_tokens` → `max_completion_tokens`, `openai_api_key/openai_api_base` → `api_key/base_url`). GenAI_Flask_App pins exact versions; Book_Movie_Advisor uses the older `openai_api_key`/`openai_api_base` parameter names which may not work with newer `langchain-openai` releases.
- **JSON parsing**: Free-tier models occasionally wrap JSON in markdown fences, causing `JsonOutputParser` to fail. The system prompt in each project enforces "JSON only, no markdown." As a fallback, `plan.md` describes a `StrOutputParser` + regex extractor approach.

## Engineering Lessons

- Debug the model call before adding Flask and browser behavior; `llm_test.py` isolates that layer.
- Provider identifiers and UI labels can drift: the GenAI app's Granite label and the Advisor's DeepSeek/Phi labels are not reliable descriptions of the current configured IDs.
- Parsed JSON is not automatically schema-valid. Numeric ranges, required fields, and the requested three-card count need explicit validation for stronger guarantees.
- No automated test suite is committed for these three apps; the GenAI sanity check calls live APIs.
