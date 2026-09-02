# AI Email Assistant — Project Plan

Built as practice for the IBM course **"Develop Generative AI Applications: Get Started"** (IBM RAG and Agentic AI specialization).

## Top-Level Overview

Build a Flask web application called **AI Email Assistant**.

The user provides:

- What they want to write (`topic`)
- Writing tone (`tone`): casual, friendly, professional, formal
- Email type (`email_type`): apology, complaint, follow-up, thank-you, etc.
- Preferred LLM (`model`): pick one model, or **Compare All**

The application generates a fully structured email using **LangChain** and **OpenRouter**.

Instead of returning plain text, the backend returns **structured JSON** parsed through LangChain's `JsonOutputParser`:

```json
{
  "subject": "...",
  "email": "...",
  "tone": "formal",
  "improvements": ["...", "...", "..."]
}
```

The application also allows users to **compare multiple LLMs side-by-side** to evaluate response quality. For each model it shows generation time, email length, and a simple "subject quality" score.

This project intentionally practices every important concept introduced in IBM Course 1 while replacing WatsonX with **OpenRouter**.

---

## Prerequisites (what you need before starting)

- **Python 3.10+** installed (`python3 --version`).
- An **OpenRouter** account and API key. Create one at https://openrouter.ai (you can use free-tier models).
- A working internet connection. OpenRouter must resolve — see the Troubleshooting section (this bit us!).

---

## Architecture

```
                Browser
                   │
                   ▼
             Flask Backend
                   │
             PromptTemplate
                   │
          LangChain LCEL Chain
                   │
      ChatOpenAI (OpenRouter)
                   │
         JsonOutputParser
                   │
            Pydantic Model
                   │
             JSON Response
                   │
               Frontend
```

The backend chain is a one-liner LCEL pipe:

```
prompt | llm | parser
```

You call it with `chain.invoke({...})` and get back a parsed Python `dict`.

---

## Project Structure (the final, actual layout)

```
ai_email_assistant/                  # the project folder (renamed AI_Email_Assistant here)
│
├── app.py             # Flask app: GET / and POST /generate
├── config.py          # API key, base URL, model IDs, temperature, max tokens
├── model.py           # LLM factory (create_llm) — NOT "models.py"!
├── parser.py          # Pydantic schema + JsonOutputParser
├── prompts.py         # system prompt + PromptTemplate with few-shot example
├── services/
│   │
│   ├── ai_service.py  # build_chain() + generate_email()
│   └── __pycache__/   # generated, ignore
│
├── templates/
│   └── index.html     # the page
│
├── static/
│   ├── style.css      # page styling
│   └── script.js      # frontend logic (fetch, "Compare All", rendering)
│
├── .env               # REAL key — never commit this
├── .env.example       # template of what .env should look like
├── .gitignore         # ignores .env and __pycache__
├── requirements.txt   # pinned package list
├── venv/              # your virtual environment (created by you)
├── plan.md            # this file
└── (README.md optional)
```

> **Mismatch note:** the original plan said `models.py`; the real file is `model.py`. Keep the name consistent everywhere you import it.

---

## Skills Covered

| IBM Course Topic | Where You'll Practice It |
|---|---|
| Prompt Engineering | `PromptTemplate` in `prompts.py` |
| Prompt Variables | `email_type`, `tone`, `topic`, `system_prompt` |
| Few-shot Learning | Example IN/OUT block inside the prompt |
| LangChain | Entire backend |
| LCEL | `prompt \| llm \| parser` |
| JsonOutputParser | Output parsing in `parser.py` |
| Pydantic | `EmailResponse` schema |
| Flask | API routes in `app.py` |
| Model Evaluation | Subject-quality score + length (frontend) |
| OpenRouter | LLM provider (OpenAI-compatible API) |
| Modular Design | config / model / parser / prompts / services split |

---

## Setup Cheat Sheet (do this once)

```bash
# 1. create + activate a virtual environment
python3 -m venv venv
source venv/bin/activate          # Linux/macOS
# venv\Scripts\activate          # Windows

# 2. install dependencies
pip install flask langchain langchain-openai langchain-core python-dotenv pydantic

# 3. create .env with your real key (copy from .env.example)
#    OPENROUTER_API_KEY=sk-or-v1-...

# 4. freeze versions so the project is reproducible
pip freeze > requirements.txt
```

> **Pinning versions matters.** This project was built with `langchain-openai` 1.4.x and `langchain-core` 1.5.x. A fresh `pip install` may upgrade to langchain-openai 2.x, where parameter names changed (`max_tokens` → `max_completion_tokens`, `openai_api_base` → `base_url`). Freeze your requirements.

---

## Subtask 1 — Project Setup & Configuration

**Status:** ✅ Completed

### Intent
Create the project skeleton, a virtual environment, pull in dependencies, and centralise every configuration value (API key, base URL, model IDs, generation parameters) in one `config.py`.

### Expected Outcomes
- `venv/` exists and opens correctly (you can `venv/bin/python -c "print('hi')"`).
- `requirements.txt` lists Flask, langchain, langchain-openai, langchain-core, python-dotenv, pydantic.
- `.env` contains a real key and is ignored by git.
- `config.py` exposes `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `MODELS`, `TEMPERATURE`, `MAX_TOKENS`.

### Files

**`requirements.txt`**
```
flask
langchain
langchain-openai
langchain-core
python-dotenv
pydantic
```

**`.env.example`**
```
OPENROUTER_API_KEY=""
```

**`.env`** (create locally, add your real key; never commit)
```
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxx...
```

**`.gitignore`**
```
.env
__pycache__
```

**`config.py`**
```python
import os

from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

MODELS = {
    "deepseek": "deepseek/deepseek-v4-flash",
    "laguna": "meta-llama/llama-3.1-8b-instruct",
    "mistral": "mistralai/mistral-7b-instruct",
    "qwen": "qwen/qwen3-8b",
}

TEMPERATURE = 0.7
MAX_TOKENS = 2000
```

### How to verify
```bash
python3 -c "from config import MODELS, OPENROUTER_BASE_URL; print(MODELS); print(OPENROUTER_BASE_URL)"
```

### Pitfalls
- **The dict keys in `MODELS` are your internal names** ("deepseek", "laguna", ...). The **values** are the real OpenRouter model slugs. The frontend dropdown uses the keys; the API call uses the values.
- **`OPENROUTER_BASE_URL` is critical.** Use `https://openrouter.ai/api/v1`. The similar-looking `https://api.openrouter.ai/v1` does **not** resolve in many environments (DNS failure) and breaks every request. This was a real bug that took a while to find — see Troubleshooting.
- If `OPENROUTER_API_KEY` is `None`, your `.env` is missing or not loaded. Verify the key prints a long value.

---

## Subtask 2 — Response Schema (parser.py)

**Status:** ✅ Completed

### Intent
Define the exact JSON shape the LLM must return, using Pydantic, and create a `JsonOutputParser` that validates it.

### Expected Outcomes
- `EmailResponse(BaseModel)` with `subject`, `email`, `tone`, `improvements`.
- A module-level `parser` exported for reuse in `prompts.py` and `services/ai_service.py`.

### File

**`parser.py`**
```python
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field


class EmailResponse(BaseModel):
    subject: str = Field(..., description="The subject of the email")
    email: str = Field(..., description="The body of the email")
    tone: str = Field(..., description="The tone of the email (e.g., formal, casual, friendly)")
    improvements: list[str] = Field(..., description="Suggestions for improving the email")


parser = JsonOutputParser(pydantic_object=EmailResponse)
```

### How to verify
```bash
python3 -c "from parser import parser; print(parser.get_format_instructions()[:200])"
```
You should see the JSON schema formatting instructions the parser injects into the prompt.

### Pitfalls
- Keep the field names in `EmailResponse` exactly aligned with what your frontend expects (`data.subject`, `data.email`, `data.tone`, `data.improvements`).
- If the model returns extra or missing keys, the parser may fail — see the tolerant-parsing tip in the chain subtask.

---

## Subtask 3 — Prompt Engineering (prompts.py)

**Status:** ✅ Completed

### Intent
Write a system prompt that locks the model into returning pure JSON, plus a reusable `PromptTemplate` with a few-shot example and the parser's format instructions.

### Expected Outcomes
- `SYSTEM_PROMPT` states the role and the "JSON only, no markdown" rule.
- `EMAIL_PROMPT` renders with variables `system_prompt`, `email_type`, `tone`, `topic` and the injected `format_instructions`.
- The JSON sample in the prompt is **escaped** (`{{` and `}}`) so prompt rendering does not mangle it.

### File

**`prompts.py`**
```python
from langchain_core.prompts import PromptTemplate

from parser import parser

SYSTEM_PROMPT = """You are an expert communication coach. You help users write professional, effective and well-structured emails. For every request you produce a polished email together with a clear subject line and actionable improvement suggestions.

You MUST always respond with a plain JSON object and nothing else. Never include markdown code fences, commentary or extra text around the JSON."""

EMAIL_PROMPT_TEMPLATE = """{system_prompt}

Here is an example of what we expect:

Example INPUT:

Topic:
Interview apology

Example OUTPUT:

{{
  "subject": "Apology for Missing the Interview",
  "email": "Dear [Hiring Manager],\n\nI am writing to sincerely apologize for missing my interview on [date]. The meeting was unfortunately lost due to a family emergency. I remain very interested in the position and would be grateful for the chance to reschedule at your earliest convenience.\n\nBest regards,\n[Your Name]",
  "tone": "formal",
  "improvements": [
    "Provide a specific new date and time for the rescheduled interview",
    "Apologize earlier in the email to acknowledge the impact on the interviewer",
    "Add a line expressing continued enthusiasm for the role"
  ]
}}

Now write the email.

Email type: {email_type}
Tone: {tone}
Topic:
{topic}

{format_instructions}"""

EMAIL_PROMPT = PromptTemplate(
    template=EMAIL_PROMPT_TEMPLATE,
    input_variables=["system_prompt", "email_type", "tone", "topic"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)
```

### How to verify
```bash
python3 -c "
from prompts import EMAIL_PROMPT
p = EMAIL_PROMPT.format(system_prompt='Coach', email_type='apology', tone='formal', topic='missed a meeting')
print(p[:400])
"
```
You should see the full prompt with `{format_instructions}` replaced by the parser instructions.

### Pitfalls
- **Escaping**: inside a f-string-like `PromptTemplate`, literal `{` and `}` must be doubled (`{{`, `}}`). If you write single braces in the example, the prompt render throws `KeyError`/`ValueError` about an unknown input variable.
- `format_instructions` is passed as a **partial variable** (fixed, not per-request) while the four others are per-request **input variables**. Getting this split wrong makes `.invoke(...)` fail complaining about missing keys.

---

## Subtask 4 — OpenRouter Integration (model.py)

**Status:** ✅ Completed

### Intent
Create a single function that returns a `ChatOpenAI` instance wired to OpenRouter, so the rest of the app never cares where the LLM lives. Models can be swapped by changing `config.MODELS`.

### Expected Outcomes
- `create_llm(model_name: str) -> ChatOpenAI` uses the OpenRouter base URL, the API key, a fixed temperature, and a max-token cap.
- Any model slug in `MODELS` can be instantiated.

### File

**`model.py`**
```python
from langchain_openai import ChatOpenAI

from config import MAX_TOKENS, OPENROUTER_API_KEY, OPENROUTER_BASE_URL, TEMPERATURE


def create_llm(model_name: str) -> ChatOpenAI:
    """
    Create a ChatOpenAI instance with the specified model name, temperature, and max tokens.
    """
    return ChatOpenAI(
        model=model_name,
        api_key=OPENROUTER_API_KEY, # type: ignore
        base_url=OPENROUTER_BASE_URL,
        temperature=TEMPERATURE,
        max_completion_tokens=MAX_TOKENS,
    )
```

### How to verify
```bash
python3 -c "from model import create_llm; print(create_llm('deepseek/deepseek-v4-flash').model_name)"
```
You should get the model slug back without any import error.

### Pitfalls
- **File name is `model.py`, not `models.py`.** A typo here breaks every `from model import ...`.
- **`max_completion_tokens` vs `max_tokens`**: langchain-openai 1.4.x accepts `max_completion_tokens`. On older versions you may need `max_tokens` (like the Book/Movie Advisor uses `**GEN_PARAMS` with `max_tokens=600`). Match your parameter name to the installed version.
- Passing `api_key=None` (missing `.env`) does not raise at construction time — it only fails when you actually call the model. Check your env var early.

---

## Subtask 5 — LCEL Chain (services/ai_service.py)

**Status:** ✅ Completed

### Intent
Compose `prompt | llm | parser` into a runnable chain, and expose one function that takes plain inputs and returns a validated dict.

### Expected Outcomes
- `build_chain(model_name)` returns an LCEL runnable.
- `generate_email(email_type, tone, topic)` invokes the chain and returns the parsed dict.
- Both functions are importable from `services`.

### Files

**`services/` note** — this folder has no `__init__.py` in the actual build; imports like `from services.ai_service import ...` still work because Python 3 treats it as an implicit namespace package. Adding an (empty) `__init__.py` is also valid and makes it an explicit regular package.

**`services/ai_service.py`**
```python
from config import MODELS
from model import create_llm
from parser import parser
from prompts import EMAIL_PROMPT, SYSTEM_PROMPT


def build_chain(model_name: str):
    model = MODELS[model_name]
    llm = create_llm(model_name=model)
    return EMAIL_PROMPT | llm | parser


def generate_email(model_name: str, email_type: str, tone: str, topic: str):
    chain = build_chain(model_name=model_name)
    return chain.invoke(
        {
            "system_prompt": SYSTEM_PROMPT,
            "email_type": email_type,
            "tone": tone,
            "topic": topic,
        }
    )
```

### How to verify (the single most useful test in this project)
Test the chain **directly, without Flask** — this isolates network/parsing errors from HTTP routing:
```bash
python3 -c "
from services.ai_service import generate_email
from pprint import pprint
pprint(generate_email('deepseek', 'apology', 'formal', 'missed a meeting'))
"
```
Expected output: a dict with keys `subject`, `email`, `tone`, `improvements`, plus the actual generated email.

### Pitfalls
- **Invalid JSON output.** The strict `JsonOutputParser` throws `OutputParserException: Invalid json output:` when the model wraps its answer in markdown fences or adds commentary. Some free-tier models do this intermittently. Two options:
  1. Tighten the system prompt (already done: "JSON only, nothing else").
  2. Make parsing tolerant — swap `parser` for `StrOutputParser()` and run the raw text through a small extractor that strips fences before `json.loads`. The Book/Movie Advisor hit this exact exception (see Troubleshooting).
- **Prefer this one-file Python test over clicking the UI** while debugging. It prints the real traceback in seconds.

---

## Subtask 6 — Flask Backend (app.py)

**Status:** ✅ Completed

### Intent
Expose two routes: `GET /` serves the page; `POST /generate` runs the chain and returns JSON with timing.

### Expected Outcomes
- `GET /` renders `templates/index.html`, passing the `MODELS` keys so the dropdown can be generated dynamically.
- `POST /generate` validates `topic`, `tone`, `email_type`, `model`; returns `400` for missing/unknown input and `500` with details if generation fails.
- Response includes the parsed result plus `duration_ms`.

### File

**`app.py`**
```python
import time

from flask import Flask, jsonify, render_template, request

from config import MODELS
from services.ai_service import generate_email

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html", models=MODELS)


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True) or {}
    topic = (data.get("topic") or "").strip()
    tone = (data.get("tone") or "").strip()
    email_type = (data.get("email_type") or "").strip()
    model = (data.get("model") or "").strip()

    if not topic or not tone or not email_type or not model:
        return jsonify({"error": "Missing required fields: topic, tone, email_type, model"}), 400

    if model not in MODELS:
        return jsonify({"error": f"Unknown model '{model}'. Allowed: {', '.join(MODELS)}"}), 400

    start = time.time()
    try:
        result = generate_email(model_name=model, email_type=email_type, tone=tone, topic=topic)
    except Exception as exc:  # pragma: no cover - network/API failures
        app.logger.exception("Generation failed")
        return jsonify({"error": "Email generation failed", "detail": str(exc)}), 500

    duration_ms = round((time.time() - start) * 1000, 1)
    return jsonify({**result, "duration_ms": duration_ms})


if __name__ == "__main__":
    app.run(debug=True)
```

### How to verify
```bash
python3 app.py                       # serves on http://127.0.0.1:5000
# in another terminal:
curl -s -X POST http://127.0.0.1:5000/generate \
  -H "Content-Type: application/json" \
  -d '{"topic":"thanks for the interview","tone":"friendly","email_type":"thank-you","model":"deepseek"}'
```
Expect a JSON object with `subject`, `email`, `tone`, `improvements`, `duration_ms`.

### Pitfalls
- `request.get_json(silent=True) or {}` keeps the handler from 500-ing on malformed bodies.
- Note the **model validation happens in `app.py` (`model not in MODELS`)** while the chain itself indexes `MODELS[model_name]` — double validation, deliberate: the API rejects bad model names early with a clean 400 instead of a confusing chain `KeyError`.
- "Compare All" is **not sent as `model='all'`** to this route — the frontend calls `/generate` once per model. So `all` never reaches Flask; if it does, it returns the 400 above. Good by design.

---

## Subtask 7 — Frontend (templates/ + static/)

**Status:** ✅ Completed

### Intent
A clean, dependency-free UI: a form with topic, tone, email-type and model dropdowns; a spinner; and result cards rendered from the JSON.

### Expected Outcomes
- Page loads the model options from `models` (passed by Flask), so adding a model to `config.py` updates the dropdown automatically.
- Submitting calls `/generate`; with "Compare All" it fires **one request per model in parallel** (`Promise.all`) and shows a card per model — plus an error block if any model failed.
- Each card shows subject, tone, body, suggestions list, time, length, and a computed subject-quality score (0–10).
- All model output is HTML-escaped before injection (no XSS).

### Files

**`templates/index.html`** — form layout: topic textarea; `field-row` of three selects (tone / email_type / model); the model select loops over `models` and appends a `Compare All` option; hidden spinner; hidden results section.

```html
<div class="field">
    <label for="model">Model</label>
    <select id="model" name="model">
        {% for key in models %}
        <option value="{{ key }}" {% if loop.first %}selected{% endif %}>{{ key|title }}</option>
        {% endfor %}
        <option value="all">Compare All</option>
    </select>
</div>
```

**`static/script.js`** — key logic:
```js
const MODEL_KEYS = Array.from(document.getElementById("model").options)
    .map((o) => o.value)
    .filter((v) => v !== "all");

const targets = model === "all" ? MODEL_KEYS : [model];

const outputs = await Promise.all(
    targets.map((key) =>
        postGenerate(key, payload).catch((err) => ({ error: err.message, model_key: key }))
    )
);
```
- `postGenerate(modelKey, payload)` POSTs `{ ...payload, model: modelKey }` to `/generate` and throws on non-ok responses.
- `renderCard` builds the `<article class="email-card">` DOM with `escapeHtml()` on every dynamic value (subject, tone, email, improvements).
- `subjectQuality(subject)` scores: sensible length (8–90 chars) → +4; starts with a capital letter → +3; no trailing period/question/exclamation → +3; capped at 10.

**`static/style.css`** — CSS custom properties (accent color `#4f46e5`), card grid, spinner keyframes, `.hidden` utility, error styling, responsive `.field-row` collapse under 640px.

### How to verify
1. `python3 app.py`, open `http://127.0.0.1:5000`.
2. Pick a topic + tone + email type + one model → one card appears.
3. Pick **Compare All** → one card per configured model, each with time/length/quality; a red `.error` block appears if any model failed.
4. Inspect the network tab: a `compare all` sends `len(MODELS)` POSTs in parallel.

### Pitfalls
- **Escape before injecting.** Model output is untrusted text; using `innerHTML` with the raw JSON is an XSS risk. Always run values through `escapeHtml()`.
- The "Compare All" UX is forgiving: one slow/failing model renders in its own error block while the others still display. Do not `Promise.all` fail the whole UI.

---

## Subtask 8 — Compare Models

**Status:** ✅ Completed (frontend only)

### Intent
Practice model evaluation by generating the same email with every configured model side-by-side.

### Expected Outcomes
- Dropdown contains each model plus **Compare All**.
- Compare All runs all chains in parallel and displays one card each.
- Each card shows response time, subject quality (0–10) and length — the evaluation metrics.

### Implementation notes
- All the heavy lifting is client-side (`script.js`), so the backend stays simple.
- To add/remove a participant: edit `MODELS` in `config.py` — no other file changes.
- The subject-quality heuristic is intentionally simple (length, capitalization, no trailing punctuation) as a practice stand-in for a real LLM-judge evaluation.

### Pitfalls
- Parallel requests can hit OpenRouter rate limits if you have many models; each failure is shown inline, so this degrades gracefully.
- Do not pass `model="all"` to Flask expecting it to fan out server-side — the frontend already fan-out per model. (Server-side fan-out is a fine stretch goal though.)

---

## Subtask 9 — Testing & Troubleshooting

**Status:** ✅ Completed (see table below)

### Test matrix
Try these through either the direct Python runner (Subtask 5) or the UI:

- Professional email (tone=professional, email_type=general)
- Complaint / apology (email_type=complaint / apology)
- Follow-up / meeting request
- Internship application
- Thank-you email
- Switch models, including Compare All
- Submit with empty topic → expect HTTP 400

Verify:
- JSON parsing succeeds (fields `subject`, `email`, `tone`, `improvements`)
- Prompt variables all render (no `Input variables ... not provided` errors)
- Model switching changes the model slug actually called
- Parser validation rejects broken JSON gracefully

### Real bugs that were fixed in this project (read these!)

**1. Wrong OpenRouter base URL → every request fails.**
Symptom: calling the chain raises `httpx.ConnectError: [Errno -2] Name or service not known` (DNS failure), or the API returns empty output.
Cause: `OPENROUTER_BASE_URL = "https://api.openrouter.ai/v1"` — that host does not resolve everywhere.
Fix: use `https://openrouter.ai/api/v1` (the same URL the working Book_Movie_Advisor uses).
```bash
# quick check:
curl -s -o /dev/null -w "%{http_code}\n" https://openrouter.ai/api/v1/models
#   ^ 200 = reachable ; 000 = DNS/network problem — fix the URL, not the code
```

**2. `OutputParserException: Invalid json output:` (500 / intermittent 200).**
Symptom: the model occasionally wraps the JSON in markdown fences or adds extra text; `JsonOutputParser` then throws `JSONDecodeError: Expecting value: line 1 column 1 (char 0)` on the empty/mangled content.
Why it looks random: small free-tier models are non-deterministic — the same input can succeed once and fail the next time.
Fixes:
- Keep the strict "JSON only, no fences" rule in the system prompt (already present).
- If it still happens, switch the tail of the chain to `StrOutputParser()` and clean the text before parsing:

```python
import json
import re
from langchain_core.output_parsers import StrOutputParser

def extract_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    return json.loads(text)
```

**3. `requirements` drift.**
`langchain-openai` major-version bumps rename parameters (`max_tokens` → `max_completion_tokens`; `openai_api_key/openai_api_base` → `api_key/base_url`). Pin with `pip freeze > requirements.txt` right after a known-good install.

**4. Debugging order that works.**
1. `python3 -c "from config import OPENROUTER_API_KEY; print(bool(OPENROUTER_API_KEY))"` → key present?
2. `curl .../models` → network up?
3. Direct chain call (Subtask 5) → chain works?
4. `python3 app.py` + `curl /generate` → Flask works?
5. UI last. This order turns "it doesn't work" into "exactly which layer is broken".

---

## Stretch Goals (Optional)

If you finish early, these are great extensions that prepare you for later courses:

- **Retry/Fallback Logic (recommended)**: if one OpenRouter model fails or returns invalid JSON, automatically retry with the next model in `MODELS` before surfacing an error. This removes the intermittent 500s from Testing bug #2.
- **Conversation Memory**: add LangChain memory so the assistant remembers prior emails in the session.
- **Streaming Responses**: stream the email token-by-token to the frontend.
- **Prompt Version Selector**: let users switch prompt styles and compare outputs.
- **Export Features**: download the generated email as `.txt` or copy it with one click.
- **Conversation History**: persist generated emails in a lightweight SQLite database and revisit them.