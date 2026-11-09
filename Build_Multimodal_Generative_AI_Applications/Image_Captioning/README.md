# Image Captioning Application

A local multimodal image-understanding application using OpenRouter.

**Status: Implemented CLI/Gradio service with experimental API and container workflows.** [Course 5](../README.md) · [Certificate](../../README.md)

## What It Demonstrates

- Vision LLMs
- Multimodal prompts
- Image encoding (Base64 data URLs)
- OpenAI-compatible APIs
- Provider abstraction
- Evaluation
- Testing
- Retry/resilience
- Model fallback

## Architecture

```
                 ┌──────────────────┐
                 │   User / CLI    │
                 └────────┬─────────┘
                          ↓
                 ┌──────────────────┐
                 │  Vision Service  │
                 └────────┬─────────┘
                          ↓
     ┌────────────────────┼────────────────────┐
     ↓                    ↓                    ↓
┌──────────┐      ┌──────────────┐      ┌──────────┐
│  Image   │      │   Prompt     │      │  OpenAI  │
│  Pipeline│      │   Builder    │      │ Client   │
└──────┬───┘      └──────┬───────┘      └────┬─────┘
       ↓                 ↓                   ↓
  load_image     build_message      OpenRouter API
  encode_image              ↓
  optimize_image       Vision LLM
       ↓
  data URL
```

## Setup

From the repository root:

```bash
cd Build_Multimodal_Generative_AI_Applications/Image_Captioning
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env  # Edit .env with your API key
```

[`src/config.py`](src/config.py) reads `OPENROUTER_API_KEY` and
`OPENROUTER_MODEL` (both required at import time), plus optional
`OPENROUTER_BASE_URL` and `OPENROUTER_FALLBACK_MODEL`. Set a vision-capable model
ID available to your account. The registry's default does not remove the
import-time `OPENROUTER_MODEL` requirement, even when using the CLI `--model` flag.

## Usage

```bash
# Caption an image
python -m src.main --image assets/image-1.jpg --task caption

# Ask a question
python -m src.main --image assets/image-1.jpg --task question --question "What is in this image?"

# Count objects
python -m src.main --image assets/image-1.jpg --task counting --question "cars"

# Compare models
python -m src.main --image assets/image-1.jpg --task question --question "Describe this" --compare

# Use a specific model
python -m src.main --image assets/image-1.jpg --task caption --model google/gemini-2.5-flash
```

## Evaluation

The five cases in [`evaluation/cases.json`](evaluation/cases.json) describe desired captioning, counting, assessment, extraction, and question behavior. [`evaluation/README.md`](evaluation/README.md) explains their use. The tests validate dataset structure; no automated vision-quality benchmark is implemented.

Run integration tests:
```bash
python -m pytest tests/integration/ -v
```

## Development

Run the suite from the project root, with the required import-time variables set:
```bash
python -m pytest tests/ -v
```

There are seven unit-test modules and one mocked pipeline-integration module,
containing 47 test functions in total. The integration tests mock the provider;
they do not verify a live OpenRouter call. No pass count or coverage percentage
is reported here. Use `python -m pytest` so the project root is on the import path.

### Container Entry Points

The Dockerfile's default command is the CLI, which requires `--image`. The
Compose file overrides it with Uvicorn on port 8000. A CLI invocation must supply
the image argument and both required environment variables via your local `.env`:
```bash
docker build -t vision-app .
docker run --rm --env-file .env vision-app python -m src.main --image assets/image-1.jpg --task caption
```

The Dockerfile runs `pip install -e .` before copying the source, so package
discovery/build behavior needs separate validation; the build is not claimed to
pass. Its blank model/key defaults are not usable configuration. Compose's port
mapping does not fix the API upload limitation below.

`COPY . .` has no tracked `.dockerignore`; a local `.env` would be copied into
the image unless excluded from the build context. Keep credential files out of
that context before evaluating the container workflow. A reproducible packaging
fix is separate from these documentation changes.

## API

FastAPI routes are defined in [`src/api/app.py`](src/api/app.py):
- `POST /v1/vision/caption` — Declared upload route; currently passes the client filename, not uploaded bytes, to the service
- `POST /v1/vision/question` — Declared question route with the same filename limitation; `question` is a query parameter
- `GET /v1/models` — List available models

Server entry point:

```bash
uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

FastAPI file routes also need `python-multipart`, which is not explicitly declared
in `pyproject.toml`. Arbitrary browser uploads cannot be processed correctly until
the route passes bytes or a saved temporary file to the service.

## Gradio UI

```bash
python -m src.api.gradio_app
```

Gradio uses its default local launch settings (normally port 7860) and supplies
temporary file paths to Caption, Question, and Count tabs. CLI tasks additionally
include assessment and extraction.

## Implementation Limitations

- Local image loading checks a 10 MiB size limit and supported extensions (`jpg`, `jpeg`, `png`, `webp`, `gif`). These checks are not a complete API upload-size policy.
- The loader has a URL path, but `VisionService._prepare_image()` then opens the original string as a local filename; end-to-end URL inference is not implemented correctly.
- Fallback responses are wrapped with the primary client's model/usage metadata; result metadata may not identify the model that actually answered.
- Tests and JSON cases demonstrate engineering seams, not production readiness or measured model quality.

## Architecture Decisions

See the ADRs for [OpenRouter](docs/decisions/ADR-001-openrouter.md),
[base64 image representation](docs/decisions/ADR-002-image-representation.md), and
[provider abstraction](docs/decisions/ADR-003-provider-abstraction.md).
