# Gradio UI Experiments

Two Gradio exercises for practicing the component model: an **implemented sentence builder** and an **experimental image-interface script** using a vision-language model.

**Status:** Sentence builder implemented; image inference needs a code correction. [Course 2](../README.md) · [Certificate](../../README.md)

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

The intended interface takes an image and displays top labels with confidence scores. The source loads **BLIP (Bootstrapping Language-Image Pre-training)**, a caption-generation model, but applies a classification-style inference and ImageNet label mapping. These contracts are incompatible; this is not a working caption-generation or ImageNet-classification pipeline as written.

### Inputs

- `gr.Image` — upload an image or use a provided example URL

### Outputs

- `gr.Label(num_top_classes=3)` — intended top-label display; the current model flow does not produce suitable ImageNet class probabilities

### How it works

1. The image is preprocessed (resize to 256, center crop to 224, normalize with ImageNet stats).
2. The script calls `BlipForConditionalGeneration` directly, then applies `softmax` as if its output were classifier logits.
3. It attempts to map that output to ImageNet labels downloaded from a public URL.
4. BLIP needs its own processor and a caption-generation/decode path; alternatively, the intended label UI needs an actual image classifier. This requires an implementation change.

---

## 3. Project structure

```
Gradio/
├── app.py              # Sentence builder Gradio interface
└── main.py             # Image captioning Gradio interface
```

---

## 4. Setup

**Requirements:** Python 3.10+. The sentence builder needs only Gradio. The image experiment additionally imports `requests`, `torch`, `torchvision`, `transformers`, and Pillow, and downloads external assets.

From the repository root:

```bash
cd Build_RAG_Applications_Get_Started/Gradio
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
python -m pip install gradio
```

---

## 5. Run

### Sentence Builder

```bash
python app.py
```

Open <http://127.0.0.1:7860>, adjust the inputs, and submit to see the generated sentence. Example inputs are provided for quick testing.

### Image Captioning

The retained entry point is [`main.py`](main.py). Its imports would require
`gradio transformers torch torchvision requests pillow`, but installing those
packages does not fix the incompatible inference path described above. No
successful image-inference run or test suite is claimed here. The script uses
Gradio's default launch configuration, unlike the explicit port in `app.py`.

---

## 6. Key concepts practiced

- **Gradio `gr.Interface`** — defining a function + inputs + outputs in minutes
- **Component variety** — `Slider`, `Dropdown`, `CheckboxGroup`, `Radio`, `Image`, `Label`
- **Example inputs** — built-in demos that users can click to test the interface
- **Server configuration** — `server_name` and `server_port` settings
- **Transformers inference** — preprocessing pipeline, model loading, and post-processing predictions
- **Output-contract debugging** — caption token/logit output cannot be treated as ImageNet class probabilities

---

## 7. Notes

- The image experiment fetches ImageNet labels on every startup and has no implemented local-cache path for that request.
- The BLIP model is downloaded automatically on first run. Subsequent runs use the cached version.
- Both demos are single-file applications — no separate template or static directories needed.
- No application environment variables, `.env.example`, dependency manifest, or automated tests are committed in this directory.
