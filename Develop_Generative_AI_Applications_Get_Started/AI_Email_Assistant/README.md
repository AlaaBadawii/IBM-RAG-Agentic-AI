# AI Email Assistant

Generate polished, structured emails with LangChain + OpenRouter. Built as practice for the IBM course **"Develop Generative AI Applications: Get Started"** (IBM RAG and Agentic AI specialization).

Pick a topic, a tone, and an email type, then let an LLM draft a complete email — with a subject line, the body, and improvement suggestions. Or choose **Compare All** to see the same email generated side-by-side by every configured model, with response time, length, and a subject-quality score.

## Features

- Structured JSON output via `JsonOutputParser` + Pydantic (subject, email, tone, improvements)
- Multiple LLMs through OpenRouter (DeepSeek, Llama, Mistral, Qwen)
- **Compare All** mode — parallel generation across models with per-model metrics
- Clean, dependency-free UI (vanilla HTML/CSS/JS)
- Modular architecture: config / model / parser / prompts / services / app

## How It Works

```
Browser ─▶ Flask ─▶ PromptTemplate ─▶ ChatOpenAI (OpenRouter) ─▶ JsonOutputParser ─▶ JSON
```

The backend chain is a single LCEL pipe: `prompt | llm | parser`. See `plan.md` for a full build-along guide.

## Project Structure

```
AI_Email_Assistant/
├── app.py             # Flask routes: GET / and POST /generate
├── config.py          # API key, base URL, model IDs, temperature, max tokens
├── model.py           # ChatOpenAI factory for OpenRouter
├── parser.py          # Pydantic schema + JsonOutputParser
├── prompts.py         # system prompt + few-shot PromptTemplate
├── services/
│   └── ai_service.py  # build_chain() + generate_email()
├── templates/
│   └── index.html
├── static/
│   ├── style.css
│   └── script.js
├── .env.example
├── requirements.txt
└── plan.md
```

## Prerequisites

- Python 3.10+
- An [OpenRouter](https://openrouter.ai) account and API key (free-tier models supported)

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env            # then edit .env and paste your key
# OPENROUTER_API_KEY=sk-or-v1-...
```

## Run

```bash
python3 app.py
```

Open http://127.0.0.1:5000, describe what to write about, pick a tone, email type and model — or choose **Compare All** — and hit Generate.

## API

`POST /generate`

```json
{
  "topic": "thanks for the interview",
  "tone": "friendly",
  "email_type": "thank-you",
  "model": "deepseek"
}
```

Response:

```json
{
  "subject": "Thank You for the Interview",
  "email": "Dear [Recipient], ...",
  "tone": "friendly",
  "improvements": ["...", "...", "..."],
  "duration_ms": 1234.5
}
```

Returns `400` for missing/unknown fields, `500` if generation fails.

## Adding a Model

Add one entry to `MODELS` in `config.py` — the dropdown updates automatically:

```python
MODELS = {
    "deepseek": "deepseek/deepseek-v4-flash",
    "laguna": "meta-llama/llama-3.1-8b-instruct",
    "mistral": "mistralai/mistral-7b-instruct",
    "qwen": "qwen/qwen3-8b",
}
```

Keys are internal names; values are OpenRouter model slugs.

## Troubleshooting

- **`ConnectError: Name or service not known`** — wrong base URL. Use `https://openrouter.ai/api/v1` in `config.py`, not `https://api.openrouter.ai/v1`.
- **`OutputParserException: Invalid json output`** — the model occasionally wraps the JSON in markdown fences. The strict "JSON only" system prompt handles most cases; see `plan.md` for a tolerant parsing fallback.
- **Key not found / not loaded** — `.env` missing or `OPENROUTER_API_KEY` empty.

## Docs

- `plan.md` — detailed build-along plan with per-file code, verification steps, and pitfalls (for learners/juniors)
