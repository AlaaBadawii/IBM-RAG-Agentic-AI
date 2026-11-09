# Course 5 — Build Multimodal Generative AI Applications

**Course status: Completed as of November 9, 2026 · Estimated duration: 9 hours**

[← Certificate overview](../README.md)

## Overview and Learning Objectives

The course studies multimodal AI across text, images, speech, and video. The
retained work focuses on image understanding, visual similarity, and generated
text/audio; the syllabus's image/video-generation models are not all implemented here.

- Build vision-language prompts and prepare images for model APIs.
- Combine visual embeddings with catalog metadata and generated explanations.
- Turn generated text into an audio lesson or story.
- Validate deterministic requirements around probabilistic model output.
- Expose workflows through Flask, FastAPI, and Gradio while understanding upload and serving limitations.

## Project and Lab Index

| Project | Relationship and actual state | Documentation |
|---|---|---|
| Image Captioning | Extended vision-service implementation: CLI, Gradio, retry/fallback, tests; API/container limitations remain | [README](Image_Captioning/README.md) |
| Vocabulary Audio Storyteller | Independent vocabulary-learning extension with validation, bounded retries, and MP3 output | [README](Vocab_Learning_App/README.md) |
| Personal Storyteller | Minimal single-file story → narration app | [README](Personal_Storyteller/README.md) |
| Style Finder | Guided lab implementation; missing external catalog dataset limits fresh-clone execution | [README](Style_Finder/README.md) |
| Cal Coach / AI Nutrition Coach | Guided Flask/watsonx lab; authentication and upload/error-handling limitations | [README](cal_coach_app/README.md) |
| AI Meeting Assistant | Stub: lab instructions only, no application code | [README](AI_Meeting_Assistant/README.md) |

## Technologies Actually Used

- **Vision:** OpenRouter-compatible OpenAI SDK and watsonx Llama-4 vision calls.
- **Visual search:** PyTorch/torchvision ResNet50, scikit-learn cosine similarity, pandas catalog lookup.
- **Text/audio:** `requests`, JSON validation, gTTS narration.
- **Interfaces:** Flask, FastAPI/Uvicorn, Gradio `Interface`/`Blocks`, Pillow/base64 handling.
- **Engineering artifacts:** pytest, vision behavior cases, ADRs, Dockerfile and Compose definitions.

Whisper is described in the Meeting Assistant instructions; there is no retained
meeting-transcription implementation to count as demonstrated functionality.

## Setup and Entry Points

Run each command from its project directory. Dependency packaging differs, so use
the linked project README rather than one shared installation for the course.

| Project | Entry point | Configuration actually consumed |
|---|---|---|
| Image Captioning | `python -m src.main --image assets/image-1.jpg --task caption`; `python -m src.api.gradio_app` | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`; optional base URL/fallback model |
| Vocabulary Storyteller | `python app.py` | `LLM_API_KEY`; optional base/model/limit/timeout settings; `GRADIO_SHARE` must be in the process environment at startup |
| Personal Storyteller | `python main.py` | `LLM_API_KEY`; optional `LLM_BASE_URL`, `LLM_MODEL` |
| Style Finder | `python app.py` | No credential env reader; fixed Skills Network config and external pickle dataset |
| Cal Coach | `python app.py` | No credential env reader; fixed Skills Network config |
| Meeting Assistant | No entry point | Instructions only |

The image API has a declared Uvicorn entry point, but passes filenames rather
than uploaded bytes to its service. Style Finder's dataset is not tracked. These
are code/data limitations, not issues solved by an extra `.env` setting.

## Testing and Engineering Lessons

- Image Captioning has eight test modules (seven unit and one mocked pipeline module) with 47 test functions, plus five qualitative vision cases. The cases are not an automated quality benchmark.
- Vocabulary Storyteller has five modules with 77 test functions; parameterization expands some cases. Its LLM/TTS dependencies are faked in tests.
- No new application execution, test-pass count, or coverage percentage is claimed by this documentation update.
- Prompt instructions are not deterministic validation. The vocabulary app adds explicit coverage/shape checks; the minimal storyteller does not.
- A working local-file service does not automatically imply a working HTTP upload route or reproducible container build.
- Audio filenames, upload cleanup, provider configuration, and model-result metadata are part of correctness, not just UI details.
