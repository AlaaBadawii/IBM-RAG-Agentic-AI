# Style Finder — Fashion Style Analyzer

A multimodal generative AI web application that analyzes fashion images: it encodes an uploaded outfit photo, finds the closest match in a product-embedding database via vector similarity, and generates a detailed fashion analysis with purchasable item details using a vision-language model.

Built with **Gradio** and powered by **IBM watsonx.ai** (`meta-llama/llama-4-maverick-17b-128e-instruct-fp8`) + **ResNet50** image embeddings.

## Features

- **Fashion image analysis** — Upload an outfit photo or use one of the built-in example images.
- **Image encoding** — ResNet50-based feature extraction plus base64 encoding for the LLM.
- **Similarity matching** — Cosine-similarity search over precomputed embeddings (`swift-style-embeddings.pkl`) to find the closest catalog outfit.
- **AI fashion response** — Llama 4 Vision generates garment, fabric, color, and style analysis with an `ITEM DETAILS` / `SIMILAR ITEMS` section (names, prices, links).
- **Robust response handling** — Refusal/truncation detection, automatic item-list re-append, and Markdown formatting for Gradio display.
- **Gradio UI** — Image upload, example-image buttons, status indicator, and Markdown results panel.

## Tech Stack

| Component | Technology |
|---|---|
| UI | Gradio 5 (`gr.Blocks`, Soft theme) |
| Vision LLM | IBM watsonx.ai `ModelInference` — `meta-llama/llama-4-maverick-17b-128e-instruct-fp8` |
| Image embeddings | PyTorch, torchvision ResNet50, scikit-learn cosine similarity |
| Data | pandas + pickle embedding store (`swift-style-embeddings.pkl`) |
| Image handling | Pillow, base64 |

## Project Structure

```
Style_Finder/
├── app.py                      # StyleFinderApp orchestration + Gradio interface
├── config.py                   # Model ID, project/region, image + similarity settings
├── requirements.txt
├── swift-style-embeddings.pkl  # Precomputed outfit embeddings dataset (untracked/large)
├── examples/                   # test-1.png … test-6.png sample outfit images
├── models/
│   ├── image_processor.py      # ImageProcessor: encode_image, find_closest_match
│   └── llm_service.py          # LlamaVisionService: generate_response, generate_fashion_response
└── utils/
    └── helpers.py              # get_all_items_for_image, format_alternatives_response, process_response
```

### How it works

1. `StyleFinderApp.process_image(image)` saves the upload to a temp file.
2. `ImageProcessor.encode_image(path, is_url=False)` returns `{base64, vector}` (ResNet50 features).
3. `ImageProcessor.find_closest_match(vector, data)` runs cosine similarity against the `Embedding` column and returns the closest row + score.
4. `get_all_items_for_image(Image URL, data)` collects every catalog item sharing the matched image.
5. `LlamaVisionService.generate_fashion_response(...)` builds an exact-match (`ITEM DETAILS`) or similar-match (`SIMILAR ITEMS`) retail-catalog prompt and calls `model.chat()` with text + base64 image.
6. `process_response(...)` escapes `$`, normalizes Markdown, and guarantees an `Item Details` / `Similar Items` section even on refusal or truncation.

## Prerequisites

- Python 3.10+
- IBM watsonx.ai access (project ID; API key if outside the Skills Network lab)
- `swift-style-embeddings.pkl` dataset in the project root (expected columns include `Item Name`, `Price`, `Link`, `Image URL`, `Embedding`)

## Installation

```bash
cd Style_Finder

# (Recommended) Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Edit `config.py`:

```python
LLAMA_MODEL_ID = "meta-llama/llama-4-maverick-17b-128e-instruct-fp8"
PROJECT_ID = "skills-network"
REGION = "us-south"

IMAGE_SIZE = (224, 224)
NORMALIZATION_MEAN = [0.485, 0.456, 0.406]
NORMALIZATION_STD = [0.229, 0.224, 0.225]

SIMILARITY_THRESHOLD = 0.8
DEFAULT_ALTERNATIVES_COUNT = 5
```

`LlamaVisionService` also accepts `temperature=0.2`, `top_p=0.6`, `max_tokens=2000`, and an optional `api_key` (passed through to `Credentials`).

## Usage

```bash
python app.py
```

Then open the local Gradio URL (default `http://127.0.0.1:5000`, plus a public `share=True` link):

1. Upload a fashion image or click **Use Example 1/2/3**.
2. Click **Analyze Style**.
3. Read the style analysis + item list (name, price, link) in the results panel.

## Notes & Limitations

- `swift-style-embeddings.pkl` (~6 MB) is required at runtime as `StyleFinderApp("swift-style-embeddings.pkl")`; keep it out of version control if it is regenerated per environment (currently untracked).
- Match quality depends on image clarity and the `SIMILARITY_THRESHOLD` (0.8); scores below threshold are reported as similar, not exact.
- LLM output is for catalog/informational purposes; prices/links come from the dataset snapshot and may be stale.
- Gradio launches with `share=True` — set to `False` if you don't want a public link.

## License

For educational purposes (IBM Skills Network — *Build Multimodal Generative AI Applications*). Add a license of your choice if distributing.
