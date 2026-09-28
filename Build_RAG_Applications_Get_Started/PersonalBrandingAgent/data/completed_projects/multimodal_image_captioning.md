# Image Captioning Service (multimodal build)

## Status
COMPLETED (implemented, tested, documented, committed). Source:
`/home/alaabadawii/LLMs/IBM/Build_Multimodal_Generative_AI_Applications/Image_Captioning/`.

## What this is
A local multimodal image-understanding application: CLI-driven image
captioning over OpenAI-compatible vision APIs with provider abstraction,
evaluation, tests, retry/resilience, and model fallback. Built as the applied
lab of the IBM "Build Multimodal Generative AI Applications" course
(Module 2: integrating visual modalities), extended with the author's own
architecture (`PLAN.md`, `docs/`, `evaluation/`).

## What's actually there (evidence)
- `src/` — vision service: image encoding (base64 data URLs), multimodal
  prompts, OpenAI-compatible API calls behind a provider abstraction.
- `tests/` — test suite (`pytest`); `evaluation/` — caption evaluation.
- Retry/resilience and model fallback (a second model answers when the first
  fails).
- `Dockerfile`, `docker-compose.yml`, `pyproject.toml`.
- `README.md`, `PLAN.md`, `docs/` — architecture and usage documentation.

## Why it matters (technical decision documented)
- Provider abstraction + fallback treats vision-model failure as expected:
  the app answers even when one provider does not — the same posture as the
  Style Finder output guarantees (`../stories_lessons/vision_model_output_guarantees.md`),
  applied one layer down at the transport/model level.
- Evaluation and tests ship with the app: caption quality is checked, not
  eyeballed.

## Skills exercised (from course, applied here)
- Text-to-image/image-to-text patterns, image captioning, multimodal
  prompts, provider abstraction, evaluation harnesses, Docker packaging.

## Technologies
Python, OpenAI-compatible vision APIs, pytest, Docker / docker-compose.

## Provenance
`/home/alaabadawii/LLMs/IBM/Build_Multimodal_Generative_AI_Applications/Image_Captioning/README.md`.
Committed by the user (`a1cff92` and related history in the IBM monorepo).

## Relationship to the course
Built while completing IBM "Build Multimodal Generative AI Applications"
(Course 5 of the IBM RAG and Agentic AI Professional Certificate; certificate
record: `../certificates/ibm_build-multimodal-generative-ai-applications.md`).
The course is the learning record; this file is the implementation record.
