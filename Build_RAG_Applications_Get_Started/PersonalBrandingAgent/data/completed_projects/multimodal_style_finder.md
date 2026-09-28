# Style Finder — Fashion Style Analyzer (multimodal build)

## Status
COMPLETED (implemented, documented, committed). Source:
`/home/alaabadawii/LLMs/IBM/Build_Multimodal_Generative_AI_Applications/Style_Finder/`.

## What this is
A multimodal generative AI web application that analyzes fashion images: it
encodes an uploaded outfit photo, finds the closest match in a
product-embedding database via vector similarity, and generates a detailed
fashion analysis with purchasable item details using a vision-language model.
Built as the applied lab of the IBM "Build Multimodal Generative AI
Applications" course (Module 3: multimodal retrieval and search), extended
with the author's own project structure and README.

## What's actually there (evidence)
- `app.py` — `StyleFinderApp` orchestration + Gradio interface (`gr.Blocks`,
  Soft theme): image upload, example-image buttons, status indicator,
  Markdown results panel.
- `models/image_processor.py` — `ImageProcessor`: ResNet50 feature
  extraction, base64 encoding, cosine-similarity search over precomputed
  embeddings (`swift-style-embeddings.pkl`).
- `models/llm_service.py` — `LlamaVisionService`: retail-catalog prompts
  (exact-match `ITEM DETAILS` / similar-match `SIMILAR ITEMS`) against IBM
  watsonx.ai (`meta-llama/llama-4-maverick-17b-128e-instruct-fp8`).
- `utils/helpers.py` — catalog-item collection, alternatives formatting,
  response post-processing.
- `config.py` — model ID, project/region, image + similarity settings.
- `examples/` — six sample outfit images; `requirements.txt`.

## Why it matters (technical decision documented)
- Retrieval + generation are separated: scikit-learn cosine similarity over
  ResNet50 vectors picks the catalog row; the vision LLM only writes the
  analysis. The LLM never searches — it narrates what retrieval found.
- Vision-model output is treated as unreliable by default: refusal/truncation
  detection with automatic item-list re-append and Markdown normalization, so
  the UI always shows an `Item Details` / `Similar Items` section (see
  `../stories_lessons/vision_model_output_guarantees.md`).

## Skills exercised (from course, applied here)
- Multimodal retrieval and search, image embeddings (ResNet50), cosine
  similarity, vision-language prompting, Gradio web apps, IBM watsonx.ai.

## Technologies
Python 3.10+, Gradio 5, PyTorch/torchvision (ResNet50), scikit-learn, pandas,
Pillow, IBM watsonx.ai (Llama 4 Maverick vision).

## Provenance
`/home/alaabadawii/LLMs/IBM/Build_Multimodal_Generative_AI_Applications/Style_Finder/README.md`
(documents architecture, data flow, setup). Committed by the user
(`ee1d2ea` and related history in the IBM monorepo).

## Relationship to the course
Built while completing IBM "Build Multimodal Generative AI Applications"
(Course 5 of the IBM RAG and Agentic AI Professional Certificate; certificate
record: `../certificates/ibm_build-multimodal-generative-ai-applications.md`).
The course is the learning record; this file is the implementation record.
