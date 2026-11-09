# Personal Storyteller

**Status: Implemented minimal story-and-audio app; experimental single-user workflow.**

[Course 5](../README.md) · [Certificate overview](../../README.md)

## What Exists

[`main.py`](main.py) is a single-file Gradio app. A topic is inserted into a prompt
requesting a beginner-friendly educational story of roughly 200–300 words. The
app calls an OpenRouter-compatible chat endpoint, then uses gTTS to save MP3
narration and returns the story and audio path to the interface.

The directory also retains a sample [`generated_story.mp3`](generated_story.mp3)
and a Gradio public certificate artifact. There is no tracked dependency manifest,
`.env.example`, automated test suite, or structured evaluation.

## Dependencies and Configuration

Source imports require `gradio`, `requests`, `python-dotenv`, and `gTTS`.

| Variable read by `main.py` | Use |
|---|---|
| `LLM_API_KEY` | Hosted-model key; required for a real model call |
| `LLM_BASE_URL` | Defaults to `https://openrouter.ai/api/v1` |
| `LLM_MODEL` | Defaults to `meta-llama/llama-4-maverick-17b-128e-instruct` |

Provide your own values in a local, ignored `.env` file or the process environment.
The root `OPENROUTER_API_KEY` convention is not the variable this script reads.
Both story generation and gTTS require network access.

## Run

From the repository root:

```bash
cd Build_Multimodal_Generative_AI_Applications/Personal_Storyteller
python3 -m venv venv
source venv/bin/activate
python -m pip install gradio requests python-dotenv gTTS
python main.py
```

Gradio uses its default local port (normally 7860) and launches with `share=True`.
The command is matched to the source entry point; no execution result is claimed.

## Limitations and Lessons

- Story length, factual correctness, topic validity, and output quality are not checked programmatically.
- The HTTP request has no explicit timeout or retry policy, and errors are not wrapped in an application-specific UI message.
- Every request writes the same temporary `story_audio.mp3` path; concurrent requests can overwrite each other's audio.
- The sample MP3 is not an evaluation benchmark. This mini-app demonstrates text generation → TTS → Gradio wiring, not a production storytelling service.
