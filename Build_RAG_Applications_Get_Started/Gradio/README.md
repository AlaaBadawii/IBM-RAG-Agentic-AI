# Gradio UI Experiments

Two hands-on Gradio demonstrations for practicing the Gradio component model: a **sentence builder** and an **image captioning** demo using a vision-language model.

This project is part of **Course 2 — Build RAG Applications: Get Started** (IBM RAG and Agentic AI Professional Certificate), used as practice with Gradio's interface components before building the LinkedIn Icebreaker Bot UI.

---

## 1. Sentence Builder

A `gr.Interface` that generates a descriptive sentence from a set of structured inputs. The user adjusts sliders, selects dropdowns, checks checkboxes, and clicks submit to see a generated sentence.

### Inputs

| Component | Description |
|---|---|
| `gr.Slider` (3–20) | Number of tech workers |
| `gr.Dropdown` | Tech worker type (Data Scientist, Software Developer, Software Engineer) |
| `gr.CheckboxGroup` | Countries (Canada, Japan, France) |
| `gr.Radio` | Location (office, restaurant, meeting room) |
| `gr.Dropdown` (multiselect) | Activities (partied, brainstormed, coded, fixed bugs) |
| `gr.Checkbox` | Morning or night |

### Output

A single sentence combining all inputs, e.g.:

> The 4 Software Developers from Canada and Japan went to the office where they brainstormed and fixed bugs until the morning.

---

## 2. Image Captioning

A `gr.Interface` that takes an image as input and returns the top predicted labels with confidence scores. Uses **BLIP (Bootstrapping Language-Image Pre-training)** from Salesforce for image understanding.

### Inputs

- `gr.Image` — upload an image or use a provided example URL

### Outputs

- `gr.Label` — top predicted ImageNet labels with confidence scores

### How it works

1. The image is preprocessed (resize to 256, center crop to 224, normalize with ImageNet stats).
2. `BlipForConditionalGeneration` generates predictions.
3. Predictions are mapped to human-readable ImageNet labels (downloaded from a public URL).
4. The top-3 labels by confidence are displayed.

---

## 3. Project structure

```
Gradio/
├── app.py              # Sentence builder Gradio interface
└── main.py             # Image captioning Gradio interface
```

---

## 4. Setup

**Requirements:** Python 3.10+, internet access for downloading the ImageNet labels and the BLIP model.

```bash
cd Gradio
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install gradio transformers torch requests
```

---

## 5. Run

### Sentence Builder

```bash
python app.py
```

Open <http://127.0.0.1:7860>, adjust the inputs, and submit to see the generated sentence. Example inputs are provided for quick testing.

### Image Captioning

```bash
python main.py
```

Open the browser, upload an image or click an example, and see the top predicted labels with confidence scores. The model (`Salesforce/blip-image-captioning-base`) is downloaded automatically on first run.

---

## 6. Key concepts practiced

- **Gradio `gr.Interface`** — defining a function + inputs + outputs in minutes
- **Component variety** — `Slider`, `Dropdown`, `CheckboxGroup`, `Radio`, `Image`, `Label`
- **Example inputs** — built-in demos that users can click to test the interface
- **Server configuration** — `server_name` and `server_port` settings
- **Transformers inference** — preprocessing pipeline, model loading, and post-processing predictions
- **Confidence-based labeling** — converting raw model logits to probability distributions via `softmax`

---

## 7. Notes

- The image captioning demo downloads ImageNet labels from a public URL on startup. If offline, you can cache them locally and load from a local file.
- The BLIP model is downloaded automatically on first run. Subsequent runs use the cached version.
- Both demos are single-file applications — no separate template or static directories needed.
