# Book/Movie Advisor — Project Plan

## Top-Level Overview

Build a small Flask web app called **Book/Movie Advisor**. The user types a free-text
description of their current mood or interests, chooses one of two LLM models from a
dropdown, and receives **3 structured recommendation cards** — each with:

- `title`
- `type` (book or movie)
- `genre`
- `why_you_ll_love_it`
- `mood_match` (0–10)
- `where_to_find_it`

The AI backend uses **LangChain LCEL** (prompt → LLM → `JsonOutputParser`) and
connects to **OpenRouter** (free-tier). Two models are offered:
`meta-llama/llama-3.1-8b-instruct:free` and `mistralai/mistral-7b-instruct:free`.

### File structure

```
book_movie_advisor/
├── config.py           # API key, model IDs, generation params
├── model.py            # LLM factory + LCEL chain builder
├── app.py              # Flask app (2 routes: GET / and POST /recommend)
├── templates/
│   └── index.html      # Single-page UI: form + 3 result cards + model selector
└── requirements.txt
```

### Skills exercised from the IBM course

| Course topic | Where it appears |
|---|---|
| `PromptTemplate` + few-shot examples | `model.py` prompt with 1 baked-in example |
| LCEL pipe chain (`|`) | `prompt \| llm \| JsonOutputParser` in `model.py` |
| `JsonOutputParser` + Pydantic schema | `Recommendation` + `RecommendationList` Pydantic models |
| Multi-model comparison | Model selector dropdown in the UI |
| Parameter tuning (temperature, max_tokens) | `config.py` |
| Flask routes, `render_template`, JSON responses | `app.py` |
| Modular architecture (config / model / app) | Project layout |
| OpenRouter (replaces IBM Watsonx) | Uses `langchain-openai` with `openai_api_base` override |

---

## Sub-Task 1 — Project Scaffold & Configuration

**Status:** [ ] pending

### Intent
Create the project folder, `requirements.txt`, and `config.py`. This establishes the
foundation every other sub-task builds on.

### Expected Outcomes
- `book_movie_advisor/` folder exists with the full file skeleton (empty stubs).
- `requirements.txt` lists all needed packages.
- `config.py` exposes `OPENROUTER_API_KEY`, `MODELS` dict, and `GEN_PARAMS`.
- A `.env.example` file shows which env var to set (`OPENROUTER_API_KEY=sk-or-...`).

### Todo List
1. Create `book_movie_advisor/` directory and empty stub files.
2. Write `requirements.txt`:
   - `flask`
   - `langchain`
   - `langchain-openai`
   - `langchain-core`
   - `pydantic`
   - `python-dotenv`
3. Write `config.py`:
   - Load `OPENROUTER_API_KEY` from environment (via `python-dotenv`).
   - Define `MODELS` dict:
     ```
     "llama": "meta-llama/llama-3.1-8b-instruct:free"
     "mistral": "mistralai/mistral-7b-instruct:free"
     ```
   - Define `GEN_PARAMS`: `temperature=0.7`, `max_tokens=600`.
   - Define `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`.
4. Write `.env.example`.

### Relevant Context
- Course pattern: `config.py` centralises credentials and model IDs.
- OpenRouter is OpenAI-API-compatible, so `langchain-openai`'s `ChatOpenAI` is used
  with `openai_api_base` set to the OpenRouter URL.

---

## Sub-Task 2 — Pydantic Schema + LangChain Chain (model.py)

**Status:** [ ] pending

### Intent
Define the structured output schema with Pydantic and build the LCEL chain that takes
a user mood string and returns a `RecommendationList` (3 items). This is the core AI
logic of the app.

### Expected Outcomes
- `Recommendation` Pydantic model with all 6 fields typed and described.
- `RecommendationList` Pydantic model wrapping a `list[Recommendation]`.
- `build_chain(model_key: str)` function returns a runnable LCEL chain.
- The prompt includes: system instructions + 1 few-shot example + `{format_instructions}` + `{mood}` placeholder.
- Calling the chain with `{"mood": "I want something cozy for a rainy Sunday"}` returns
  a parsed Python dict with a `recommendations` key containing 3 items.

### Todo List
1. Import `ChatOpenAI` from `langchain_openai`; import config values.
2. Define `Recommendation(BaseModel)` with fields:
   - `title: str`
   - `type: str` — "book" or "movie"
   - `genre: str`
   - `why_you_ll_love_it: str`
   - `mood_match: int` — 0 to 10
   - `where_to_find_it: str`
3. Define `RecommendationList(BaseModel)` with `recommendations: list[Recommendation]`.
4. Instantiate `JsonOutputParser(pydantic_object=RecommendationList)`.
5. Write `PROMPT_TEMPLATE` as a `PromptTemplate` with:
   - System-level instructions (role: expert advisor, always return exactly 3 items).
   - 1 few-shot example (mood → JSON snippet).
   - `{format_instructions}` block.
   - `{mood}` user input.
6. Write `build_chain(model_key)`:
   - Instantiate `ChatOpenAI` pointing at OpenRouter.
   - Return `prompt | llm | parser` as the LCEL chain.

### Relevant Context
- Course lab used `JsonOutputParser` + Pydantic + LCEL pipe operator.
- `ChatOpenAI(openai_api_key=..., openai_api_base=OPENROUTER_BASE_URL, model=model_id)`.
- `parser.get_format_instructions()` is passed into the prompt's partial variables.

---

## Sub-Task 3 — Flask Application (app.py)

**Status:** [ ] pending

### Intent
Wire the chain into a Flask app with two routes: a GET route that serves the HTML page
and a POST route that runs the chain and returns JSON.

### Expected Outcomes
- `GET /` returns `render_template("index.html")`.
- `POST /recommend` accepts JSON body `{"mood": "...", "model": "llama"|"mistral"}`,
  runs the chain, and returns the parsed recommendation list as JSON.
- Returns a `400` if `mood` is missing/empty.
- Returns a `500` with an error message if the chain raises an exception.
- Execution duration is measured and included in the response (`"duration_ms": float`).

### Todo List
1. Create Flask app instance.
2. Import `build_chain` from `model.py`.
3. Implement `GET /` route.
4. Implement `POST /recommend` route:
   a. Parse `mood` and `model` from request JSON.
   b. Validate presence of `mood`; return 400 otherwise.
   c. Default `model` to `"llama"` if not provided or unrecognised.
   d. Record start time.
   e. Call `build_chain(model).invoke({"mood": mood})`.
   f. Record end time, compute `duration_ms`.
   g. Return `jsonify({"recommendations": ..., "duration_ms": ...})`.
   h. Wrap in try/except; return 500 on failure.
5. `if __name__ == "__main__": app.run(debug=True)`.

### Relevant Context
- Course Flask app structure: `config.py` / `model.py` / `app.py` + `templates/`.
- Course used `request.json`, `jsonify`, `render_template`.

---

## Sub-Task 4 — Frontend UI (templates/index.html)

**Status:** [ ] pending

### Intent
Build a clean, self-contained single-page UI: a text area for the mood input, a model
selector dropdown, a submit button, and a 3-card result grid. No external UI framework
is required — vanilla HTML/CSS/JS only.

### Expected Outcomes
- Page loads with a heading, a labelled textarea, a model dropdown (Llama / Mistral),
  and a "Get Recommendations" button.
- Clicking the button shows a loading spinner, then renders 3 cards side by side.
- Each card displays all 6 fields: title (large), type badge, genre badge,
  `why_you_ll_love_it` paragraph, mood match bar/score, `where_to_find_it`.
- The `duration_ms` and selected model name are shown below the cards.
- If the API returns an error the page shows a clear error message.
- No external CSS framework needed — use a simple embedded `<style>` block.

### Todo List
1. Write HTML skeleton: `<head>` with embedded `<style>`, `<body>` with:
   - Header section (app title + subtitle).
   - Input section: `<textarea id="mood">`, `<select id="model">`, `<button id="submit">`.
   - Results section: `<div id="results">` (hidden until response arrives).
   - Loading indicator: spinner shown while fetch is in progress.
2. Write embedded CSS:
   - Clean sans-serif font.
   - Card grid: `display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem`.
   - Book cards with a warm colour accent; movie cards with a cool colour accent.
   - Mood-match displayed as a simple numeric badge.
3. Write `<script>`:
   - On button click: read mood + model, show spinner, hide results.
   - `fetch('/recommend', { method: 'POST', body: JSON.stringify({mood, model}) })`.
   - On response: hide spinner, build card HTML from `recommendations` array, inject
     into `#results`, show duration and model name.
   - On error: display error message inside `#results`.

### Relevant Context
- Course lab HTML used CSS Grid, a model selector, loading indicators, and dynamic
  card injection via `innerHTML` / DOM manipulation.
- Keep JS inline in the HTML file (no separate `.js` file needed at this scale).

---

## Notes for Implementation

- The `.env` file must be created by the developer with their real OpenRouter API key;
  it is never committed to git. Add `.env` to `.gitignore`.
- `build_chain` is called per-request (stateless). No session/memory is needed.
- The few-shot example in the prompt should be concise: one mood → one trimmed JSON
  object (not the full 3-item list) to avoid bloating the context.
- OpenRouter free-tier models may occasionally rate-limit; the 500 error handler covers this.
