# GenAI Playground — Flask + LangChain + OpenRouter

A small web app that lets you send a message to one of three configured LLMs
(Llama, DeepSeek R1, or Mistral) and get back a **schema-guided JSON response**:
a summary, a sentiment score, and a suggested reply.

**Status: Implemented guided-project rebuild.** [Course 1](../README.md) · [Certificate](../../README.md)

The UI and function names retain a `granite` slot, but `GRANITE_MODEL_ID` in
[`config.py`](config.py) is `deepseek/deepseek-r1`. This slot does not call IBM Granite.

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
4. LangChain's `JsonOutputParser` parses the reply into a Python dict. The Pydantic
   schema provides format instructions; there is no separate Pydantic validation call.
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
| `config.py` | `Credentials(url=..., project_id=...)` | `OPENROUTER_API_KEY` read from `.env`; base URL is a code constant; optional `OPENROUTER_SITE_URL`/`OPENROUTER_SITE_NAME` supply attribution headers |
| `model.py` | `ChatWatsonx(...)` | `ChatOpenAI(base_url="https://openrouter.ai/api/v1", ...)` |
| `model.py` prompts | 3 separate raw-text templates, one per model, each hand-written with that model's special tokens (`<\|begin_of_text\|>` for Llama, `[INST]` for Mistral, `<\|system\|>` for Granite) | **1 shared `ChatPromptTemplate`** with normal `system`/`human` roles |
| `app.py` | unchanged | unchanged |
| Frontend | CSS/JS pulled from a GitHub Gist | written from scratch (the Gist's host wasn't reachable in the build sandbox) |

### Why the per-model prompt templates disappeared

This is the part worth actually understanding, not just copying.

The course's raw-text `ModelInference` examples use a **text-completion**
interface: you hand it one long string, and if you
want the model to behave like a chat assistant, *you* have to wrap your message in
that model's special tokens so it recognizes "this is the system prompt" vs "this
is the user turn." That's why the lab had you memorize `<|start_header_id|>` for
Llama, `[INST]...[/INST]` for Mistral, and `<|system|>` for Granite — three
different formats for the same idea.

`ChatWatsonx` also supports chat messages; manual special-token wrapping is a
property of those raw-text lab examples, not a requirement of every watsonx client.

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
GenAI_Flask_App/
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

Read as: format the prompt → send it to the model → parse JSON. JSON parsing
errors are caught by `app.py` and returned as `500`. The current code does not
independently enforce required fields, field types, or the sentiment range;
`Field(description=...)` describes a range but does not validate it.

---

## 5. Setup

**Requirements:** Python 3.10+, an OpenRouter API key and access to the configured models. The configured IDs are not all `:free` models; availability and pricing depend on the provider.

From the repository root:

```bash
cd Develop_Generative_AI_Applications_Get_Started/GenAI_Flask_App
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
python -m pip install -r requirements.txt
cp .env.example .env
```

1. Go to <https://openrouter.ai/keys>, sign up (no credit card needed), and
   create a key.
2. Paste it into `.env` as `OPENROUTER_API_KEY`.

The API base URL is fixed in `config.py`; setting `OPENROUTER_BASE_URL` in `.env`
does not change it. Optional `OPENROUTER_SITE_URL` and `OPENROUTER_SITE_NAME` are read.

### Sanity check (no Flask, no browser)

```bash
python llm_test.py
```

This calls all three models directly and prints their parsed JSON responses. The
"Granite Response" heading is a legacy label for the DeepSeek R1 call. It is a
live-API smoke check, not an automated test suite. Failures can originate in
credentials, model availability, network access, dependencies, or JSON parsing.

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
