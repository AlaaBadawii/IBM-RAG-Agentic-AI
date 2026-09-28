# Multimodal AI — Learning vs Applied Evidence

Distinguishes "I studied multimodal AI" from "I used it to build something".

## Evidence state

- Multimodal **learning**: LEARNING (IBM "Build Multimodal Generative AI
  Applications" complete; rest of the RAG & Agentic AI specialization in
  progress).
- Multimodal **application**: DOCUMENTED (three implemented builds below,
  each with source, README, and user commits in the IBM monorepo).

Sources: `../certificates/ibm_build-multimodal-generative-ai-applications.md`,
`../completed_projects/multimodal_style_finder.md`,
`../completed_projects/multimodal_nutrition_coach.md`,
`../completed_projects/multimodal_image_captioning.md`,
`../in_progress_courses/ibm_rag_and_agentic_ai.md`.

## What multimodal learning covers (course material — learning, not ability proof)

IBM Course 5 (complete, Sep 2026): multimodal foundations (text/speech/image/
video integration), TTS/STT (gTTS, Whisper), text-to-image/image-to-text and
image captioning (DALL·E, GPT Image, Llama 4), text-to-video (Sora),
multimodal RAG/search, multimodal QA and chatbots, Flask/Gradio full-stack
apps. **Progression is course exposure.**

## What multimodal practice exists (application evidence)

- **Style Finder** (DOCUMENTED): Gradio web app — ResNet50 image embeddings +
  cosine-similarity retrieval over a product-embedding store + Llama 4 vision
  analysis via watsonx.ai. Retrieval picks the catalog row; the LLM narrates.
- **AI Nutrition Coach** (DOCUMENTED): Flask web app — food-photo upload →
  per-item identification, portions, calories, nutrients, health evaluation
  via Llama 4 vision, with an approximate-estimates disclaimer.
- **Image Captioning service** (DOCUMENTED): CLI captioning with provider
  abstraction, evaluation, tests, retry/resilience, model fallback, Docker
  packaging.
- Further lab implementations (no separate project records): a personal
  storyteller script (Mistral + gTTS, `Personal_Storyteller/main.py`), a
  vocabulary-learning app in progress (`Vocab_Learning_App/src/`). The AI
  Meeting Assistant lab has no implementation in the repo and is recorded
  here as not built — lab instructions only.

## Publicly safe claim

- "I completed IBM's multimodal AI course and built three multimodal apps:
  a fashion-style finder, a nutrition coach, and an image captioning service."

## Avoid

- "I'm a multimodal AI expert / proficient in multimodal AI." (One course
  plus three lab builds; production or client work would be needed for more.)
- Any claim about the meeting assistant as a built thing (no implementation
  exists).

## Relationship

- Multimodal learning → Style Finder / Nutrition Coach / Image Captioning →
  supports the applied-AI-engineer positioning alongside the RAG and agent
  work already in the knowledge base.
