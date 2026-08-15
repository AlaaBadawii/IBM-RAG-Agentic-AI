# GenAI Playground — Flask + LangChain + OpenRouter

A small web app that lets you send a message to one of three LLMs (Llama, Granite,
or Mistral) and get back a **structured JSON response** — not just plain text, but
a summary, a sentiment score, and a suggested reply, all validated against a schema.

This is a rebuild of the IBM "Develop Generative AI Applications: Get Started"
guided project, with one change: it calls models through **OpenRouter** instead of
**IBM watsonx.ai**. Everything else — the Flask structure, the LangChain chain
design, the JSON-parsing approach — follows the same ideas taught in the course.

---

## 1. What this project actually does

1. You type a message and pick a model in the browser.
2. The browser sends `{ message, model }` to the Flask backend (`POST /generate`).
3. Flask builds a prompt (a system instruction + your message + formatting
   instructions), sends it through a **LangChain chain**, and asks the model to
   reply in a specific JSON shape.
4. LangChain's `JsonOutputParser` checks the model's reply against that shape and
   converts it into a Python dict.
5. Flask sends that dict back to the browser as JSON, and the page renders it.

The point of the exercise (from the course) is to practice three things:

- **Prompt templates** — reusable prompts with placeholders, instead of hardcoded strings.
- **Chains** — piping a prompt → a model → an output parser, so each piece is swappable.
- **Structured output** — forcing free-text model output into a predictable schema
  (`summary`, `sentiment`, `response`) using Pydantic + `JsonOutputParser`.

---

## 2. Why OpenRouter instead of watsonx.ai

The original course used `ibm-watsonx-ai` and `langchain-ibm`, and the Cloud IDE
handled authentication for you automatically — no API key needed. Outside that
environment, watsonx.ai requires an IBM Cloud account and project setup.

**OpenRouter** is a single API that routes to many providers (Meta, Mistral, IBM
Granite, and others) and gives you a free API key with no billing setup required
for `:free` models. It's also **OpenAI-API-compatible**, meaning LangChain's
`ChatOpenAI` class works against it directly — you just point it at a different
`base_url` and use an OpenRouter key instead of an OpenAI one.

### What changed, file by file

| File | Course (watsonx) | This project (OpenRouter) |
|---|---|---|
| `config.py` | `Credentials(url=..., project_id=...)` | `OPENROUTER_API_KEY` + `OPENROUTER_BASE_URL` read from `.env` |
| `model.py` | `ChatWatsonx(...)` | `ChatOpenAI(base_url="https://openrouter.ai/api/v1", ...)` |
| `model.py` prompts | 3 separate raw-text templates, one per model, each hand-written with that model's special tokens (`<\|begin_of_text\|>` for Llama, `[INST]` for Mistral, `<\|system\|>` for Granite) | **1 shared `ChatPromptTemplate`** with normal `system`/`human` roles |
| `app.py` | unchanged | unchanged |
| Frontend | CSS/JS pulled from a GitHub Gist | written from scratch (the Gist's host wasn't reachable in the build sandbox) |

### Why the per-model prompt templates disappeared

This is the part worth actually understanding, not just copying.

watsonx's `ModelInference`/`ChatWatsonx` (in the course's raw-text examples) is
close to a **text-completion** interface: you hand it one long string, and if you
want the model to behave like a chat assistant, *you* have to wrap your message in
that model's special tokens so it recognizes "this is the system prompt" vs "this
is the user turn." That's why the lab had you memorize `<|start_header_id|>` for
Llama, `[INST]...[/INST]` for Mistral, and `<|system|>` for Granite — three
different formats for the same idea.

OpenRouter (like OpenAI) exposes a real **chat-completions** API: you send
structured messages —
```json
[{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
```
— and the provider applies the correct template server-side, whichever model you
picked. So instead of three prompt templates, `model.py` has one:

```python
prompt_template = ChatPromptTemplate.from_messages([
    ("system", "{system_prompt}\n\n{format_prompt}"),
    ("human", "{user_prompt}"),
])
```

and all three model-specific response functions (`llama_response`,
`granite_response`, `mistral_response`) reuse it.

---

## 3. Project structure

```
genai_flask_app/
├── app.py              # Flask routes: GET / and POST /generate
├── config.py            # Env vars, model IDs, generation params
├── model.py              # LangChain: prompt template, models, JSON schema, chain
├── llm_test.py           # CLI sanity check — calls all 3 models directly, no Flask
├── requirements.txt
├── .env.example          # Copy to .env and fill in your key
├── templates/
│   └── index.html        # Chat page
└── static/
    ├── styles.css
    └── script.js          # Fetches /generate, renders the JSON response
```

---

## 4. How the JSON schema works

`model.py` defines the shape every response must follow:

```python
class AIResponse(BaseModel):
    summary: str = Field(description="Summary of the user's message")
    sentiment: int = Field(description="Sentiment score from 0 (negative) to 100 (positive)")
    response: str = Field(description="Suggested response to the user")

json_parser = JsonOutputParser(pydantic_object=AIResponse)
```

`json_parser.get_format_instructions()` generates a text block describing this
schema, which gets injected into the system prompt (`{format_prompt}`) — that's
how the model knows what JSON shape to reply in. The chain is:

```python
chain = prompt_template | model | json_parser
```

Read as: format the prompt → send it to the model → parse the model's reply into
the schema. If the model doesn't return valid JSON matching the schema, this step
raises an error, which `app.py`'s `try/except` catches and returns as a `500`.

---

## 5. Setup

**Requirements:** Python 3.10+, a free OpenRouter account.

```bash
cd genai_flask_app
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

1. Go to <https://openrouter.ai/keys>, sign up (no credit card needed), and
   create a key.
2. Paste it into `.env` as `OPENROUTER_API_KEY`.

### Sanity check (no Flask, no browser)

```bash
python llm_test.py
```

This calls all three models directly and prints their parsed JSON responses. If
this fails, the problem is in your key or model IDs — fix it here before touching
Flask.

### Run the app

```bash
python app.py
```

Open <http://localhost:5000>, pick a model, and send a message.

---

## 6. If a model ID stops working

OpenRouter's free-model lineup changes often — providers add and remove `:free`
models without much notice. If you get a `404` or "model not found" error:

1. Check the current free list: <https://openrouter.ai/models?max_price=0>
2. Swap the broken ID in `config.py` (`LLAMA_MODEL_ID`, `GRANITE_MODEL_ID`, or
   `MISTRAL_MODEL_ID`) for a currently-available one.
3. Re-run `python llm_test.py` to confirm.

---

## 7. Ideas to extend it (same spirit as the course's "Next Steps")

- Add a 4th field to `AIResponse` (e.g. `category`) and update the system prompt
  and frontend to display it — this is the exact exercise the course lab had you
  do.
- Add conversation memory so follow-up messages have context.
- Add a response-time or cost comparison view across the three models.
- Swap `openrouter/free`-style auto-routing in for one of the models, to see how
  routing behaves versus a pinned model ID.