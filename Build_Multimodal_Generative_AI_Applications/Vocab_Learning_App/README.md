# Vocabulary Audio Storyteller

Paste a list of English vocabulary words and get a complete audio lesson: a
simple definition for each word, two practical example sentences, one story that
uses every word in context, and a single MP3 you can listen to while walking,
exercising or commuting.

**Vocabulary list → Understand each word → See examples → Hear the vocabulary → Hear all the words in context through a story**

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Gradio](https://img.shields.io/badge/UI-Gradio-orange)

---

## Project

The app takes a list of words like this:

```text
achieve
challenge
confident
opportunity
improve
```

and produces:

1. **Vocabulary lesson** — a plain-English definition and two distinct example
   sentences per word.
2. **Story** — one short, readable story that uses *every* supplied word.
3. **Audio lesson** — a single MP3 containing all of the above, read aloud.

## Why I Built It

I learn English vocabulary by reading explanations, then listening to them again
while walking. The listening part used to be manual work: copy the words into one
app, get explanations, copy the text into a text-to-speech app, generate audio,
repeat for the next list.

This project removes that manual step. It is a small, focused application that
automates a workflow I actually use, and it was a good excuse to practise the
part of AI application work that is *not* the model call: input normalisation,
structured output, programmatic validation, bounded retries and file handling.

## How It Works

```text
Vocabulary List
      ↓
LLM
      ↓
Definitions + Examples
      ↓
Story Using All Words
      ↓
Audio Script
      ↓
Text-to-Speech
      ↓
Audio Lesson
```

The important detail is the split between what the LLM does and what Python does.
The model writes language; Python decides whether that language is acceptable.

## Features

- Paste one word or phrase per line, with or without numbering or bullets.
- Multi-word phrases are supported (`take responsibility`, `make progress`).
- Duplicate entries are removed while the original order is preserved.
- One LLM request produces definitions, two examples per word, and the story.
- The response is parsed as JSON, with a fallback extractor for responses
  wrapped in prose or code fences.
- **Programmatic validation**: every supplied word must appear in the lesson,
  must have exactly two examples, and must appear in the story.
- **Bounded recovery**: an unusable response is regenerated once; a story that
  misses words is rewritten up to twice.
- The audio script is assembled in Python from the validated data, so the lesson
  wording never depends on the model following formatting rules.
- One MP3 per generation, uniquely named, playable and downloadable in the UI.
- Errors are reported as readable messages instead of tracebacks.

## Tech Stack

| Piece | What it does |
| --- | --- |
| Python 3.10+ | Application logic |
| [Gradio](https://www.gradio.app/) | Web interface |
| [requests](https://requests.readthedocs.io/) | Calls to an OpenRouter-compatible `/chat/completions` endpoint |
| [gTTS](https://gtts.readthedocs.io/) | Text-to-speech (MP3) |
| [python-dotenv](https://pypi.org/project/python-dotenv/) | Local configuration |
| pytest | Tests for the deterministic parts |

## Example

Input:

```text
achieve
challenge
confident
```

Output (excerpt from a real run):

> **1. achieve**
> **Definition:** To achieve something means to succeed in doing it or reaching a
> goal after hard work.
> **Examples:**
> - She worked very hard and finally achieved her dream of becoming a doctor.
> - If you study a little every day, you can achieve a high score on the test.
>
> **2. challenge**
> **Definition:** A challenge is something difficult that tests your ability and
> makes you try hard.

> **Story**
> Lena always dreamed of running a marathon, but she knew it would be a huge
> challenge. She was not a natural runner, and her first week of training was very
> hard…

The same content is then spoken into one MP3: each word, its definition, both
examples, and finally the story.

## Setup

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd Vocab_Learning_App

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

Configure your credentials:

```bash
cp .env.example .env
```

Then edit `.env`:

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=your_model
```

`.env` is git-ignored. No credentials are stored anywhere else in the project.

## Running

```bash
python app.py
```

Gradio prints a local URL (by default <http://127.0.0.1:7860>). Paste your words,
press **Generate Lesson**, and the lesson, story and audio player appear.

Set `GRADIO_SHARE=1` in `.env` to also expose a temporary public link.

## Tests

```bash
python -m pytest
```

84 tests cover the deterministic parts — input parsing, JSON extraction,
structured-response validation, vocabulary coverage, retry policy and
audio-script construction. The LLM and the TTS engine are replaced with fakes, so
the suite needs no network access.

## Architecture

```text
Vocab_Learning_App/
├── app.py               # Gradio UI and orchestration (retries, error handling)
├── requirements.txt
├── pytest.ini
├── .env.example
├── src/
│   ├── config.py        # Environment configuration
│   ├── vocabulary.py    # Parses and normalises the user's word list
│   ├── llm.py           # Prompts and OpenRouter-compatible chat calls
│   ├── validation.py    # Structured-output validation and vocabulary coverage
│   └── audio.py         # Audio-script construction and text-to-speech
└── tests/
```

Each module has one job:

- **`config.py`** reads the environment. It is the only place that touches
  credentials, and it never logs them.
- **`vocabulary.py`** is purely deterministic. It turns raw textbox contents into
  a clean list and never invents words.
- **`llm.py`** builds the prompts and talks to the API. It turns transport,
  HTTP and parsing failures into a single `LLMError`.
- **`validation.py`** is the referee. It owns the coverage checks, because "did
  the story use every word?" is a question Python answers exactly.
- **`audio.py`** builds the spoken script from validated data and wraps the TTS
  engine behind one function, so a different provider can be swapped in later.
- **`app.py`** wires it together and decides what the user sees.

## Validation

LLM instructions are not a guarantee, so the app verifies the result itself
before showing anything:

1. **Required fields** — every entry has `word`, `definition` and `examples`, and
   the response contains a story.
2. **Example count** — every word has at least two usable example sentences
   (extra ones are trimmed to two).
3. **Lesson coverage** — every word the user typed has a matching entry, in the
   user's own order and spelling.
4. **Story coverage** — every word the user typed actually appears in the story.

Coverage matching accepts ordinary inflected forms, so a story saying *"she
achieved her goal"* counts as covering *achieve*, and *"he took responsibility"*
counts as covering *take responsibility*.

When validation fails:

- A malformed or incomplete response is regenerated once.
- A story missing words triggers a second request that names the missing words
  and asks for a rewrite — at most twice.
- If it still fails, the app says so plainly rather than presenting an
  incomplete lesson as finished.

Retries are bounded in both directions (`MAX_GENERATION_ATTEMPTS`,
`MAX_STORY_REVISIONS` in `app.py`), so there is no regeneration loop.

## Limitations

- **gTTS is simple.** One fixed voice, no speed or voice control, and it needs an
  internet connection.
- **Story length is not enforced.** The prompt asks for roughly 300–500 words,
  but validation only checks coverage — a model may return something shorter.
- **Coverage matching is heuristic.** It handles common inflections and a small
  irregular-verb list, not full lemmatisation, so unusual word forms could be
  reported as missing.
- **LLM output varies.** Definitions and stories differ between runs.
- **Everything needs the network.** Both the LLM call and the TTS call are
  remote.
- **The word limit is 15.** Beyond that the lesson and audio get long; change
  `MAX_VOCABULARY_ITEMS` in `.env`.
- **Not production software.** No accounts, storage, rate limiting or queueing —
  it is a single-user learning tool.
