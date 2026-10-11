# Tool Calling Agent

A learning project demonstrating **manual tool calling** with LangChain and IBM watsonx.ai.
Instead of using a prebuilt agent executor, this project wires the agent loop by hand:
the model is bound to a set of YouTube tools, its `tool_calls` are executed in plain
Python, and the results are fed back to the model until it produces a final answer.

Course project: **Fundamentals of Building AI Agents** (IBM RAG and Agentic AI).

## Learning objectives

- **Tool binding** — exposing Python functions to the model via `llm.bind_tools(...)`
  (`src/llm.py`).
- **Model-generated tool calls** — reading `response.tool_calls` (name, args, id) from
  the `ChatWatsonx` response.
- **Argument handling** — validating that tool args are a dict before invocation
  (`src/execute_tool.py`).
- **Tool execution** — invoking LangChain `@tool` functions with `tool.invoke(args)`.
- **Conversation history** — accumulating `HumanMessage`, AI responses, and
  `ToolMessage` results in a single `messages` list.
- **Returning tool results** — wrapping each result in a `ToolMessage` linked to its
  `tool_call_id` so the model can correlate calls with outputs.
- **The agent loop** — repeating invoke → execute → append until the model answers
  without tool calls, capped by `MAX_ITERATIONS = 10` (`src/run_agent.py`).

## Features

- Five YouTube tools built with LangChain's `@tool` decorator: `search_youtube`,
  `extract_video_id`, `fetch_transcript`, `get_full_metadata`, `get_thumbnails`.
- Manual agent loop (`run_agent(user_input)`) with a 10-iteration safety cap.
- Structured error handling in the executor: unknown tools, non-dict args, transcript
  failures, and `TypeError`/`ValueError`/`KeyError` are all returned to the model as
  `ToolMessage` content instead of crashing the loop.
- JSON serialization of non-string tool results so complex outputs (metadata,
  thumbnails, search lists) are readable to the model.

## Architecture

```
User input (HumanMessage)
        │
        ▼
┌──────────────────────────────┐
│  ChatWatsonx + bound tools   │  src/llm.py: llm_with_tools
│  (temperature 0.7, max 512   │
│   output tokens)             │
└──────────────┬───────────────┘
               │ response (+ tool_calls)
               ▼
        ┌─────────────┐   no tool calls   ┌────────────────┐
        │ tool_calls? ├──────────────────▶│ Final response │
        └──────┬──────┘                   │ .content       │
               │ yes                      └────────────────┘
               ▼
┌──────────────────────────────┐
│ execute_tools(tool_calls)    │  src/execute_tool.py
│  → tools[name].invoke(args)  │
│  → ToolMessage per result    │
└──────────────┬───────────────┘
               │ results appended to messages
               ▼
        (loop back to LLM, up to MAX_ITERATIONS = 10)
```

The LLM never calls tools directly. It only *requests* them; the Python executor in
`src/execute_tool.py` performs the real work and hands the observations back.

## Project structure

```
Tool_calling_Agent/
├── src/
│   ├── llm.py                  # ChatWatsonx setup + bind_tools
│   ├── run_agent.py            # Manual agent loop (MAX_ITERATIONS = 10)
│   ├── execute_tool.py         # Tool-call executor → ToolMessage list
│   └── tools/
│       ├── __init__.py         # tools registry dict
│       ├── search_youtube.py   # Search videos by query (pytube)
│       ├── extract_video_id.py # Parse video ID from a YouTube URL (regex)
│       ├── fetch_transcript.py # Fetch captions (youtube-transcript-api)
│       ├── get_full_metadata.py# Channel/title/views/likes/etc. (yt-dlp)
│       └── get_thumbnails.py   # Thumbnail URLs + resolutions (yt-dlp)
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Technology stack

- Python (3.12 verified)
- `langchain`, `langchain-core` — messages, `@tool` decorator, tool binding
- `langchain-ibm` (`ChatWatsonx`), `ibm-watsonx-ai` — IBM watsonx.ai model access
- `pydantic` — `SecretStr` handling for credentials
- `python-dotenv` — loading `.env`
- `pytube` — YouTube search
- `yt-dlp` — video metadata and thumbnails
- `youtube-transcript-api` — captions/transcripts
- IBM watsonx.ai — hosted LLM service (API key + project required)

## Prerequisites

- Python 3.10+ (developed and checked with Python 3.12).
- An IBM watsonx.ai account with an API key and a project (to obtain the project ID).

## Installation

```bash
cd Tool_calling_Agent

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# edit .env with your own credentials
```

## Environment configuration

All five variables are required — `src/llm.py` raises an `OSError` at import time if
any of them is missing (see `.env.example` for placeholders):

- `WATSONX_API_KEY` — your IBM watsonx.ai API key.
- `WATSONX_PROJECT_ID` — the watsonx.ai project ID requests are billed/associated to.
- `WATSONX_PROJECT_NAME` — your watsonx.ai project name (validated as present at
  startup; used for configuration clarity).
- `WATSONX_URL` — the watsonx.ai service endpoint for your region.
- `WATSONX_MODEL_ID` — the model deployment ID, e.g. a Llama or Granite chat model
  available in your project.

Never commit real values: `.env` is git-ignored; only `.env.example` (placeholders)
belongs in the repository.

## Usage

There is no CLI entry point — `src/run_agent.py` exposes `run_agent(user_input)`,
and the modules use flat imports (`import tools`, `from llm import ...`), so run
everything from inside `src/`:

```bash
cd src
python -c "from run_agent import run_agent; print(run_agent('Search YouTube for LangChain tutorials and summarize the top result.'))"
```

Example session:

```
> Search YouTube for LangChain tutorials and get the transcript of the first result.
Agent → search_youtube(query="LangChain tutorials")
Tool  → [{"title": "...", "url": "...", "id": "..."}, ...]
Agent → extract_video_id(url="...") → fetch_transcript(video_id="...")
Tool  → "welcome back in this video we will..."
Agent → (final answer summarizing the video for the user)
```

Smoke-test just the model/tool binding without running tools:

```bash
cd src
python llm.py
```

This invokes the bound model once with `"Search YouTube for Python tutorials."` and
prints the resulting `tool_calls` plus the model's text.

## Available tools

| Tool | Input | What it does |
| --- | --- | --- |
| `search_youtube` | `query: str` | Returns a list of `{title, url, id}` dicts via `pytube.Search`. |
| `extract_video_id` | `url: str` | Parses the 11-character video ID out of a `youtube.com/watch?v=` or `youtu.be/` URL with a regex; raises `ValueError` otherwise. |
| `fetch_transcript` | `video_id: str` | Joins the caption segments into a single string; raises `TranscriptFetchError` when captions are unavailable. |
| `get_full_metadata` | `video_url: str` | Returns `{channel, title, duration, views, likes, rating, categories, characters}` via `yt_dlp` (no download). |
| `get_thumbnails` | `video_url: str` | Returns `[{url, resolution}, ...]` for all available thumbnails via `yt_dlp`. |

Each tool also has a `__main__` demo block (e.g. `python tools/search_youtube.py`),
useful for testing a single tool in isolation.

## Execution flow

1. `run_agent` wraps the user prompt in a `HumanMessage` and calls
   `llm_with_tools.invoke(messages)`.
2. If the response contains `tool_calls`, `execute_tools` runs each one:
   `tools[name].invoke(args)`, serializing dict/list results to JSON.
3. Each outcome becomes a `ToolMessage(content=..., tool_call_id=...)` appended to
   `messages`, so the full history (request → result → request → result) is visible
   on the next model call.
4. The loop repeats until a response arrives with no `tool_calls`; its `.content`
   is returned as the final answer.
5. If tool calls are still pending after 10 iterations, the agent stops and returns
   `"Agent stopped because the maximum number of iterations was reached."`

## Lessons learned

- **Binding is not executing.** `llm.bind_tools(...)` in `src/llm.py` only exposes
  the tool schemas to the model so it *can* request them; no Python code runs until
  `src/execute_tool.py` invokes the tool explicitly.
- **Tool calls are data, not answers.** When the model wants a tool, the signal is
  the structured `response.tool_calls` list (each with `id`, `name`, `args`); that
  response carries no final answer, so `run_agent` never returns its `.content`.
- **The executor maps request → result by ID.** `execute_tool` looks up
  `tools[name]`, validates that `args` is a dict, calls `tool.invoke(args)`, and
  wraps the outcome in a `ToolMessage(content=..., tool_call_id=...)` — including
  for the handled failures (unknown tool, non-dict args, `TranscriptFetchError`,
  `TypeError`/`ValueError`/`KeyError`).
- **History must keep both halves.** `run_agent` appends the assistant's tool-call
  message *and* extends the list with the resulting `ToolMessage`s before invoking
  the model again; dropping either half breaks the model's ability to correlate a
  result with its request.
- **The loop has exactly two exits.** It repeats invoke → execute → append until a
  response arrives with no `tool_calls`, or `MAX_ITERATIONS = 10` is exhausted.
- **The iteration cap is a stop, not an answer.** When the cap is hit with tool
  calls still pending, the agent returns a fixed "maximum iterations reached"
  notice — that string must not be mistaken for a completed, model-generated
  final answer.
- **Test each layer in isolation.** The model/binding (`python llm.py`), individual
  tools (each file's `__main__` demo block), and the executor (callable offline
  with hand-made `tool_calls` dicts) can each be exercised without the others,
  which isolates wiring problems from model-behavior or network problems.

## Current limitations

- **Iteration cap:** at most 10 LLM ↔ tool round-trips per query (`MAX_ITERATIONS`).
- **Network-dependent:** every tool call (and every LLM call) needs internet access;
  YouTube scraping via `pytube`/`yt-dlp` can break if YouTube changes its pages.
- **Transcript availability:** `fetch_transcript` fails for videos with captions
  disabled; the error is reported back to the model rather than retried another way.
- **URL formats:** `extract_video_id` only accepts `youtube.com/watch?v=` and
  `youtu.be/` URLs with 11-character IDs (e.g. no Shorts/embed variants).
- **Fixed decoding params:** temperature `0.7` and `max_output_tokens` 512 are
  hard-coded in `src/llm.py`.
- **No CLI, persistence, streaming, or tests:** interaction is via the
  `run_agent()` function; there is no test suite yet.

## Disclaimer

This is an **educational implementation** built to learn how tool calling works —
not a production-ready agent framework. It has no authentication, rate limiting,
input sanitization, retries, observability, or evaluation harness. Do not expose it
directly to untrusted users or rely on it for critical workflows.
