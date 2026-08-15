# Book/Movie Advisor — mood-based recommender (IBM COMPLETED)

## Status
COMPLETED (implemented, run locally). Source:
`/home/alaabadawii/LLMs/IBM/course-1/Book_Movie_Advisor/`.

## What this is
A Flask web app: user types a mood, picks Llama or Mistral, and gets 3 structured
recommendation cards (title, type book/movie, genre, why you'll love it,
mood_match 0-10, where to find it). Uses LangChain LCEL + OpenRouter (free tier).

## Actually implemented (evidence)
- `model.py` (85 LOC) — `Recommendation`/`RecommendationList` Pydantic models,
  `build_chain()` returns `prompt | llm | JsonOutputParser`.
- `app.py` (41 LOC) — `GET /` and `POST /recommend` with 400/500 handling and
  `duration_ms` measurement.
- `config.py` — `OPENROUTER_API_KEY`, `MODELS` dict, `GEN_PARAMS`, base URL.
- `templates/index.html` (354 LOC) — vanilla HTML/CSS/JS, CSS grid card UI,
  model dropdown, loading spinner.
- `model.py` prompt includes 1 few-shot example; `JsonOutputParser` validates
  the response against the Pydantic schema.

## Skills & concepts exercised (from the IBM course)
- `PromptTemplate` + few-shot examples; LCEL pipe (`|`); `JsonOutputParser` +
  Pydantic structured output; multi-model comparison; parameter tuning; Flask
  routes; modular config/model/app architecture.

## Technologies
Flask, LangChain LCEL, langchain-core, langchain-openai, Pydantic, OpenRouter
(meta-llama/llama-3.1-8b-instruct:free, mistralai/mistral-7b-instruct:free),
vanilla HTML/CSS/JS.

## Provenance
`/home/alaabadawii/LLMs/IBM/course-1/Book_Movie_Advisor/Plan.md` (sub-task plan)
`/home/alaabadawii/LLMs/IBM/course-1/Book_Movie_Advisor/model.py`,
`app.py`, `index.html`