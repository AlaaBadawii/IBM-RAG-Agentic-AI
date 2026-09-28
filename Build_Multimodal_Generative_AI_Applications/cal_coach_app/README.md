# Cal Coach App — AI Nutrition Coach

A multimodal generative AI web application that analyzes food images and provides detailed nutritional assessments, including calorie estimation, nutrient breakdown, and health evaluation.

Built with **Flask** and powered by **IBM watsonx.ai** (`meta-llama/llama-4-maverick-17b-128e-instruct-fp8` vision-language model).

## Features

- **Food image analysis** — Upload a photo of a meal; the app identifies each food item.
- **Portion size & calorie estimation** — Per-item portion and calorie estimates.
- **Total calorie calculation** — Aggregated calorie count for the whole meal.
- **Nutrient breakdown** — Protein, carbohydrates, fats, vitamins, and minerals per food item.
- **Health evaluation** — One-paragraph assessment of the meal's healthiness.
- **Custom questions** — Ask any question about the uploaded image (default: *"How many calories are in this food?"*).
- **Responsive web UI** — Live image preview, loading indicator, and formatted HTML response rendering.
- **Built-in disclaimer** — Notes that estimates are approximate and not medical advice.

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Python, Flask |
| Generative AI | IBM watsonx.ai `ModelInference` — `meta-llama/llama-4-maverick-17b-128e-instruct-fp8` |
| Image handling | Pillow, base64 encoding |
| Frontend | HTML (Jinja2 templates), CSS, vanilla JavaScript |
| HTTP | requests |

## Project Structure

```
cal_coach_app/
├── app.py                 # Flask app, watsonx.ai integration, routes
├── templates/
│   └── index.html         # Upload form, image preview, response display
├── static/
│   └── style.css          # App styling
└── README.md
```

### Key functions in `app.py`

- `input_image_setup(uploaded_file)` — Reads an uploaded file and returns a base64-encoded string.
- `format_response(response_text)` — Converts the model's Markdown-ish output (`**bold**`, `* bullets`) into HTML (`<p>`, `<ul>/<li>`).
- `generate_model_response(encoded_image, user_query, assistant_prompt)` — Sends text + `image_url` (base64 data URI) to the model via `model.chat()` and returns formatted HTML.
- `index()` (`GET /`, `POST /`) — Renders the form, handles upload + query, and renders the nutrition report.

## Prerequisites

- Python 3.9+
- IBM watsonx.ai access (URL + API key / credentials, and a project ID)

## Installation

```bash
# 1. Clone / navigate to the project
cd cal_coach_app

# 2. (Recommended) Create and activate a virtual environment
python3 -m venv my_env
source my_env/bin/activate  # Windows: my_env\Scripts\activate

# 3. Install dependencies
pip install Flask ibm_watsonx_ai Pillow requests
```

You can also pin the versions used during development:

```
Flask==3.1.3
ibm_watsonx_ai==1.1.20
pillow==12.3.0
requests==2.32.0
```

## Configuration

Edit the watsonx.ai client setup at the top of `app.py`:

```python
credentials = Credentials(
    url="https://us-south.ml.cloud.ibm.com",
    # api_key = "<YOUR_API_KEY>"
)
client = APIClient(credentials)
model_id = "meta-llama/llama-4-maverick-17b-128e-instruct-fp8"
project_id = "skills-network"
```

Set your own API key and project ID before running outside of Skills Network environments.

> **Note:** `app.py` currently sets a Flask app without a `secret_key`. Flash messages (`flash(...)`) require one — add `app.secret_key = "your-secret-key"` (or load from an environment variable) before production use.

## Usage

```bash
python app.py
```

Then open http://127.0.0.1:5000/ in your browser:

1. Enter a question (or keep the default *"How many calories are in this food?"*).
2. Choose a food image (`image/*`).
3. Click **"Tell me the total calories"**.
4. Wait for *"Calculating, please wait..."* — the nutrition report appears below the form.

### Response format

The assistant prompt instructs the model to return:

1. **Identification** — one food item per line
2. **Portion Size & Calorie Estimation** — e.g. `**Salmon**: 6 ounces, 210 calories`
3. **Total Calories** — e.g. `Total Calories: 235`
4. **Nutrient Breakdown** — Protein, Carbohydrates, Fats, Vitamins, Minerals
5. **Health Evaluation** — one paragraph
6. **Disclaimer** — approximate values; consult a qualified professional

## Example

**Input:** photo of salmon + asparagus, query *"How many calories are in this food?"*

**Output (abridged):**

- **Salmon**: 6 ounces, 210 calories
- **Asparagus**: 3 spears, 25 calories
- Total Calories: 235
- **Protein**: Salmon (35g), Asparagus (3g) = 38g
- Health Evaluation: ...
- Disclaimer: ...

## Limitations

- Calorie and nutrient values are **estimates** based on general food data; actual values vary by portion, ingredients, and preparation.
- This app is for informational purposes only — not medical or dietary advice.
- Requires network access to IBM watsonx.ai; image analysis quality depends on image clarity and the underlying model.

## License

For educational purposes (IBM Skills Network — *Build Multimodal Generative AI Applications*). Add a license of your choice if distributing.
