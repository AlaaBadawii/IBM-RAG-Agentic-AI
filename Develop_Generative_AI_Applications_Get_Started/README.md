# Course 1 — Develop Generative AI Applications: Get Started

**Status: Completed**

Three Flask + LangChain applications built as practice for IBM's "Develop Generative AI Applications: Get Started" course. All three replace IBM's watsonx.ai with **OpenRouter** (an OpenAI-compatible chat-completions API) and enforce structured JSON output using Pydantic models and LangChain's `JsonOutputParser`.

Every backend chain follows the same LCEL pattern — `prompt | llm | parser` — and every project returns validated Python dicts instead of raw text. The projects differ in domain (general AI response, email generation, entertainment recommendations) and in whether they offer single-model or multi-model comparison.

---

## Projects

### GenAI Flask App (`GenAI_Flask_App/`)

The course guided project rebuilt with OpenRouter. Type a message, pick one of three models (Llama, Granite, Mistral), and receive a validated JSON response: `summary`, `sentiment` (0–100), and `response`. Includes a CLI sanity-check script (`llm_test.py`) that calls all three models without starting Flask.

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

Takes a free-text mood and returns exactly 3 recommendation cards — each typed as book or movie — via a nested Pydantic `RecommendationList` schema. Selectable among 9 configurable OpenRouter models.

- `Recommendation` schema: `title`, `type` (`Literal["book", "movie"]`), `genre`, `why_you_ll_love_it`, `mood_match` (0–10), `where_to_find_it`
- Single-shot prompt with one few-shot example; `Literal` type constrains book vs. movie
- CSS-grid frontend with book cards (warm left border) and movie cards (cool left border), mood-match progress bar, and HTML-escaped output
- Includes `pyrightconfig.json` for static type checking

---

## Tech Stack

Only libraries actually imported in source code:

- **Python** 3.10+
- **Flask** — web framework (all three projects)
- **langchain**, **langchain-core**, **langchain-openai** — LCEL chains, `ChatPromptTemplate`, `JsonOutputParser`, `ChatOpenAI`
- **Pydantic** — structured output schemas (`BaseModel`, `Field`, `Literal`)
- **python-dotenv** — environment variable loading
- **OpenRouter** — LLM provider via OpenAI-compatible chat-completions API (`ChatOpenAI` with `base_url="https://openrouter.ai/api/v1"`)

---

## What's Built

- Three runnable Flask apps, each with `GET /` and a `POST` endpoint
- Structured JSON output via `JsonOutputParser` + Pydantic in every project
- LCEL chains (`prompt | llm | parser`) in all three projects
- Multi-model selection via OpenRouter: 3 models (GenAI Flask App), 4 models (AI Email Assistant), 9 models (Book/Movie Advisor)
- **Compare All** mode in AI Email Assistant — parallel frontend fan-out with per-model latency, length, and subject-quality metrics
- CLI sanity-check script (`llm_test.py`) in GenAI Flask App
- XSS-safe rendering (HTML escaping on all dynamic output) in all frontends
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

```bash
cd Develop_Generative_AI_Applications_Get_Started/<project>
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set OPENROUTER_API_KEY
python app.py
```

### Run commands

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
