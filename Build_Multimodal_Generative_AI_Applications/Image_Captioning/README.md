# Image Captioning Application

A local multimodal image-understanding application using OpenRouter.

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

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env  # Edit .env with your API key
```

## Usage

```bash
# Caption an image
python -m src.main --image assets/image-1.jpg --task caption

# Ask a question
python -m src.main --image assets/image-1.jpg --task question --question "What is in this image?"

# Count objects
python -m src.main --image assets/image-1.jpg --task counting --question "How many cars?"

# Compare models
python -m src.main --image assets/image-1.jpg --task question --question "Describe this" --compare

# Use a specific model
python -m src.main --image assets/image-1.jpg --task caption --model deepseek/deepseek-v4-flash
```

## Evaluation

Evaluation dataset in `evaluation/cases.json` covers captioning, counting, assessment, and extraction tasks.

Run integration tests:
```bash
pytest tests/integration/ -v
```

## Development

Run all unit tests:
```bash
pytest tests/ -v
```

Build Docker image:
```bash
docker build -t vision-app .
docker run -e OPENROUTER_API_KEY=sk-... vision-app
```

## API

FastAPI endpoints at `src/api/app.py`:
- `POST /v1/vision/caption` — Upload image, get caption
- `POST /v1/vision/question` — Upload image + question, get answer
- `GET /v1/models` — List available models

## Architecture Decisions

See `docs/decisions/` for ADRs covering:
- OpenRouter as provider
- Base64 data URLs for image representation
- Provider abstraction