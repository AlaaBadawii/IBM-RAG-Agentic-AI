# Book/Movie Advisor — Structured Recommendation Generation

A small Flask web app that takes a free-text mood description and requests **3 structured recommendation cards** for books or movies. A nested Pydantic schema guides the output format. The AI backend uses **LangChain LCEL** (prompt → LLM → `JsonOutputParser`) and connects to **OpenRouter**.

**Status: Implemented practice extension.** [Course 1](../README.md) · [Certificate](../../README.md)

This project follows the IBM course **"Develop Generative AI Applications: Get Started"** pattern: prompt templates, LCEL chains, and structured output via `JsonOutputParser` + Pydantic, with the proprietary IBM watsonx provider swapped for OpenRouter.

---

## 1. What this project actually does

1. You type a description of your current mood or interests and pick a model from the dropdown.
2. The browser sends `{ mood, model }` to the Flask backend (`POST /recommend`).
3. Flask builds a prompt (system instructions + a few-shot example + format instructions + your mood), sends it through a **LangChain chain**, and asks the model to reply in a specific JSON shape.
4. `JsonOutputParser` converts JSON into a Python dict using `RecommendationList` for format instructions, without a separate schema-validation call.
5. Flask sends the recommendations back as JSON, and the page renders the returned list. Three items are requested by the prompt, not enforced by the backend.

The point of the exercise is to practice:

- **Prompt templates** — reusable prompts with placeholders and a few-shot example, instead of hardcoded strings.
- **Chains** — piping a prompt → a model → an output parser, so each piece is swappable.
- **Structured output** — forcing free-text model output into a predictable schema (`title`, `type`, `genre`, `why_you_ll_love_it`, `mood_match`, `where_to_find_it`) using Pydantic + `JsonOutputParser`.

---

## 2. How the schema works

`model.py` defines two Pydantic models:

```python
class Recommendation(BaseModel):
    title: str
    type: Literal["book", "movie"]
    genre: str
    why_you_ll_love_it: str
    mood_match: int          # 0 to 10
    where_to_find_it: str

class RecommendationList(BaseModel):
    recommendations: list[Recommendation]   # prompt requests 3; no length validator
```

`parser.get_format_instructions()` generates a text block describing this schema, which gets injected into the system prompt as `{format_instructions}` — that's how the model knows what JSON shape to reply in. The chain is:

```python
chain = prompt | llm | parser
```

Malformed JSON or application errors are returned as `500`. The current chain does not separately validate field types, `Literal` values, score bounds, or list length. `mood_match` is an LLM-generated score, not an embedding-similarity calculation.

---

## 3. Why OpenRouter instead of watsonx.ai

The original course used `ibm-watsonx-ai` and `langchain-ibm`, and the Cloud IDE handled authentication for you automatically. Outside that environment, watsonx.ai requires an IBM Cloud account and project setup.

**OpenRouter** is a single API that routes to many providers (Meta, Mistral, Google, etc.) and gives you a free API key with no billing setup required for `:free` models. It's also **OpenAI-API-compatible**, meaning LangChain's `ChatOpenAI` class works against it directly — you just point it at a different `base_url` and use an OpenRouter key instead of an OpenAI one.

---

## 4. Project structure

```
Book_Movie_Advisor/
├── app.py              # Flask routes: GET / and POST /recommend
├── config.py            # API key, model IDs, generation params
├── model.py             # Pydantic schemas + LCEL chain builder
├── Plan.md              # detailed build plan
├── requirements.txt
├── .env.example
└── templates/
    └── index.html       # Single-page UI: mood input, model selector, 3 result cards
```

---

## 5. Configuration

The `config.py` file exposes:

- `MODELS` — a dict of internal names → OpenRouter model slugs (**9 models**: two Llama, one Mistral, two DeepSeek, two Gemma, one Qwen, one Phi)
- `GEN_PARAMS` — `temperature=0.7`, `max_tokens=600`
- `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`

Pick a model key from the `MODELS` dict (e.g., `"llama"`, `"deepseek"`) and pass it in the request body or select it from the UI dropdown. Unknown keys fall back to the Llama model in `build_chain()`. The dropdown is hardcoded in `templates/index.html`: its DeepSeek V3.5 and Phi-4 Reasoning labels are stale; the actual IDs are `deepseek/deepseek-v4-flash` and `microsoft/phi-4`.

---

## 6. Setup

**Requirements:** Python 3.10+, an OpenRouter API key and access to the configured models. Model availability and pricing are provider-dependent.

From the repository root:

```bash
cd Develop_Generative_AI_Applications_Get_Started/Book_Movie_Advisor
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
python -m pip install -r requirements.txt
cp .env.example .env
```

1. Go to <https://openrouter.ai/keys>, sign up (no credit card needed), and create a key.
2. Paste it into `.env` as `OPENROUTER_API_KEY`.

Only `OPENROUTER_API_KEY` is read from the environment. The API base URL, model IDs, and generation parameters are constants in `config.py`.

---

## 7. Run

```bash
python app.py
```

Open <http://localhost:5000>, type a mood (e.g., "I want something funny and light-hearted"), pick a model, and hit submit. The prompt requests 3 cards with title, type, genre, an explanation, a mood-match score (intended range 0–10), and where to find it.

---

## 8. Adding a Model

Add an entry to `MODELS` in `config.py` and a matching option in `templates/index.html`; the dropdown does **not** update automatically:

```python
MODELS = {
    "llama": "meta-llama/llama-3.1-8b-instruct",
    "deepseek": "deepseek/deepseek-v4-flash",
    "gemma": "google/gemma-3-4b-it",
    ...
}
```

Keys are internal names; values are OpenRouter model slugs.

---

## 9. Troubleshooting

- **`ConnectError: Name or service not known`** — wrong base URL. Use `https://openrouter.ai/api/v1` in `config.py`.
- **`OutputParserException: Invalid json output`** — the model occasionally wraps the JSON in markdown fences. The schema's strict format instructions + `JsonOutputParser` handle most cases.
- **Key not found / not loaded** — `.env` missing or `OPENROUTER_API_KEY` empty.
- **Output contract** — generated text fields use `escHtml()`, but `mood_match` is interpolated directly and assumed numeric. The backend does not enforce its type/range; text escaping alone is not complete output validation.

---

## 10. Skills exercised from the IBM course

| Course topic | Where it appears |
|---|---|
| `PromptTemplate` + few-shot examples | `model.py` prompt with 1 baked-in example |
| LCEL pipe chain (`\|`) | `prompt \| llm \| JsonOutputParser` in `model.py` |
| `JsonOutputParser` + Pydantic schema | `Recommendation` + `RecommendationList` Pydantic models |
| Multi-model selection | Model selector dropdown in the UI; no side-by-side comparison |
| Parameter tuning (temperature, max_tokens) | `config.py` |
| Flask routes, `render_template`, JSON responses | `app.py` |
| Modular architecture (config / model / app) | Project layout |
| OpenRouter (replaces IBM Watsonx) | Uses `langchain-openai` with `openai_api_base` override |

---

## 11. Ideas to extend

- Add conversation memory so follow-up recommendations have context.
- Add a response-time or cost comparison view across models.
- Add deterministic validation of recommendation count, fields, and score bounds.
- Explore embedding-based mood matching as a new feature; no embedding model or distance metric is used in the current app.
- Add more recommendation types (e.g., podcasts, music) by extending the `Recommendation` schema.
