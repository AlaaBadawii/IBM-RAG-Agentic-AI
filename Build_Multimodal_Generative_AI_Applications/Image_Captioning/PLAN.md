# Multimodal Image Understanding with OpenRouter

## Project Status

**Status:** Planning.

**Type:** Local AI engineering practice project.

**Original inspiration:** IBM Skills Network — *Build an Image Captioning System with watsonx and Granite.*

**Provider:** OpenRouter.

**Primary modality:** Image + Text → Text.

**Language:** Python.

**Initial interface:** CLI / Python application.

**Future extension:** FastAPI + web UI.

---

# 1. Project Goal

Rebuild the IBM image-captioning / multimodal lab locally, but do **not** reproduce the notebook architecture.

The goal is to understand how a production-style Python application sends images to a vision-capable LLM and uses the returned response for multiple visual tasks.

The application should eventually support:

1. Image captioning
2. Visual question answering
3. Object counting
4. Visual inspection / assessment
5. OCR-like information extraction from images
6. Switching between vision models without rewriting application logic
7. Local images
8. Remote image URLs
9. Basic validation and error handling
10. Automated tests for non-LLM logic

---

# 2. What You Are Rebuilding

The original lab performs this general workflow:

```text
Image URL
   ↓
Download image
   ↓
Base64 encode image
   ↓
Build multimodal message
   ↓
watsonx Vision Model
   ↓
Text response
```

Your version should become:

```text
Local / Remote Image
        ↓
Image Preparation
        ↓
Image Representation
        ↓
Multimodal Message
        ↓
Vision Model Client
        ↓
Provider Response
        ↓
Application Result
```

The important difference is that the **OpenRouter integration should be isolated**.

Do not let OpenRouter-specific code spread throughout the project.

---

# 3. Learning Objectives

By completing this project, you should be able to explain:

* What a multimodal LLM is
* What an image input actually looks like at API level
* Why an image sometimes needs to be Base64 encoded
* What a Data URL is
* How a chat message can contain multiple content parts
* How text and image inputs are combined
* What a vision-capable model does
* How OpenRouter sits between your application and model providers
* Why the model name should be configuration rather than application logic
* How to separate provider code from business logic
* How to handle malformed images and API failures
* How to test deterministic components without calling an LLM
* How to evaluate multimodal responses
* How the same inference primitive can support several AI features

---

# 4. Non-Goals

Do NOT build these initially:

* Fine-tuning
* Computer vision model training
* Object-detection bounding boxes
* Image generation
* RAG
* Vector databases
* Agents
* LangGraph
* Celery
* Kubernetes
* Authentication
* Database
* Complex frontend
* Microservices

This project is specifically about understanding **multimodal inference**.

Keep the first version small.

---

# 5. Architecture Target

Use a small layered architecture:

```text
src/
├── config.py
├── main.py
│
├── clients/
│   └── openrouter.py
│
├── images/
│   ├── loader.py
│   └── encoder.py
│
├── prompts/
│   └── vision.py
│
├── services/
│   └── vision.py
│
├── models/
│   └── result.py
│
└── exceptions.py
```

Tests:

```text
tests/
├── test_encoder.py
├── test_loader.py
├── test_prompts.py
└── test_vision_service.py
```

Assets:

```text
assets/
├── image-1.png
├── image-2.png
├── image-3.png
└── image-4.png
```

Configuration:

```text
.env
.env.example
.gitignore
pyproject.toml
README.md
PLAN.md
```

---

# 6. STEP 0 — Understand the Original Lab Before Coding

## Reason

Do not immediately replace `watsonx` with OpenRouter.

First understand what the IBM code is actually doing.

The notebook contains these important operations:

```text
image URLs
   ↓
requests.get(...)
   ↓
base64.b64encode(...)
   ↓
messages = [...]
   ↓
model.chat(...)
   ↓
response['choices'][0]['message']['content']
```

The provider is the part that changes.

The underlying multimodal concept does not.

## What to understand

Study these parts of the original notebook:

### Image preparation

The lab downloads four images from URLs.

Understand:

* What `requests.get()` returns
* What `response.content` contains
* Why binary image data cannot simply be inserted into JSON
* Why Base64 exists

### Model request

Understand this structure conceptually:

```python
{
    "role": "user",
    "content": [
        {
            "type": "text",
            "text": "Describe the photo"
        },
        {
            "type": "image_url",
            "image_url": {
                "url": "data:image/jpeg;base64,..."
            }
        }
    ]
}
```

This is the most important part of the entire lab.

### Model response

Understand why the code accesses:

```python
response["choices"][0]["message"]["content"]
```

Do not memorize it.

Understand the response structure.

---

# 7. STEP 1 — Create the Local Python Project

## Reason

The original environment is a notebook.

Your goal is to understand how the same workflow becomes a maintainable Python application.

## Build

Create a new project:

```text
multimodal-openrouter/
```

Create:

```text
src/
tests/
assets/
```

Create:

```text
README.md
PLAN.md
pyproject.toml
.env.example
.gitignore
```

## Recommended Python environment

Use a dedicated virtual environment.

For example:

```bash
python -m venv .venv
```

Activate it and verify:

```bash
python --version
```

## Initial dependencies

Start with only what you actually need.

Core dependencies:

```text
openai
python-dotenv
Pillow
requests
pytest
```

Do not add LangChain yet.

The purpose of this project is to understand the underlying API first.

---

# 8. STEP 2 — Configure OpenRouter

## Reason

Never hardcode API credentials.

The original lab gets credentials from the IBM environment. Your local application needs to explicitly manage its own credentials.

OpenRouter provides an OpenAI-compatible API. The standard base URL is:

```text
https://openrouter.ai/api/v1
```

and the Python OpenAI client can use that base URL directly.

## Build

Create:

```text
.env
```

with:

```text
OPENROUTER_API_KEY=...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=...
```

Create:

```text
.env.example
```

but never put the real key there.

Example:

```text
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=
```

## Create `config.py`

The configuration layer should:

1. Load environment variables
2. Validate required variables
3. Expose configuration to the rest of the application

Conceptually:

```text
Environment
     ↓
config.py
     ↓
application
```

The rest of your code should not directly read:

```python
os.environ["OPENROUTER_API_KEY"]
```

everywhere.

---

# 9. STEP 3 — Choose a Vision Model

## Reason

The IBM lab uses a vision-capable model.

OpenRouter supports many models, but **not every model accepts image input**.

The request format remains essentially the same while the model changes.

OpenRouter's current documentation specifically recommends checking that the selected model supports image input; models expose their supported input modalities.

## Important

Do not permanently hardcode a random model from a tutorial.

Instead:

1. Open the current OpenRouter model catalog.
2. Filter for models accepting image input.
3. Pick one suitable for experimentation.
4. Record the exact model slug in `.env`.

For the first implementation, prioritize:

* Vision support
* Reasonable cost
* Good general image understanding
* Stable API availability

You can later compare multiple models.

## Architecture requirement

Your code should know:

```text
MODEL = configuration
```

not:

```text
MODEL = business logic
```

That means changing the model should require changing configuration, not rewriting your service.

---

# 10. STEP 4 — Implement the OpenRouter Client

## Reason

This is your provider integration boundary.

Your application should not know how OpenRouter authentication works.

Only one component should know.

Target:

```text
Vision Service
      ↓
OpenRouter Client
      ↓
OpenRouter API
```

## Build

Create:

```text
src/clients/openrouter.py
```

Create a small client responsible for:

* Creating the OpenAI-compatible client
* Receiving model/messages
* Calling the chat completion endpoint
* Extracting the model response
* Translating provider errors into application-level errors

The client should NOT:

* Download images
* Decide prompts
* Implement captioning
* Count cars
* Perform business logic

It only talks to OpenRouter.

---

# 11. STEP 5 — Perform the First Text-Only OpenRouter Call

## Reason

Before debugging vision, prove that your provider integration works.

Do not introduce three problems at once:

```text
OpenRouter
+
image encoding
+
vision model
```

First prove:

```text
Python
   ↓
OpenRouter
   ↓
LLM
   ↓
text response
```

## Build

Create a tiny test function or temporary script.

Send:

```text
Hello. Respond with exactly: connection successful
```

Verify the response.

## Success criteria

You should know:

* API key works
* Base URL works
* Model works
* Python SDK works
* Response parsing works

Only continue after this works.

---

# 12. STEP 6 — Implement Image Loading

## Reason

The original lab downloads images using `requests`.

Your application should separate:

```text
Where the image comes from
```

from:

```text
How the image is sent to the model
```

## Build

Create:

```text
src/images/loader.py
```

Support initially:

### Local file

```text
assets/image-1.png
```

### Remote URL

```text
https://example.com/image.png
```

The loader should return binary image data or a clearly defined image object.

---

# 13. STEP 7 — Add Image Validation

## Reason

Professional applications should not blindly send arbitrary bytes to an AI API.

Validate:

* File exists
* File is readable
* File is actually an image
* MIME type can be determined
* Supported image type
* Optional maximum file size

Use Pillow for image validation.

## Supported initial formats

At minimum:

```text
JPEG
PNG
WEBP
```

OpenRouter's current vision guidance lists PNG, JPEG, WebP and GIF among supported image types, subject to model/provider support.

## Important

Do not over-engineer this.

The purpose is to learn the boundary:

```text
untrusted input
      ↓
validation
      ↓
AI pipeline
```

---

# 14. STEP 8 — Implement Base64 Encoding

## Reason

This is one of the main concepts from the original lab.

JSON is text-based.

Image files are binary.

Therefore:

```text
binary image
     ↓
Base64
     ↓
text representation
     ↓
data URL
     ↓
JSON request
```

## Build

Create:

```text
src/images/encoder.py
```

Implement a function conceptually like:

```text
image bytes
      ↓
base64 string
      ↓
data:image/<type>;base64,<encoded-data>
```

Do not copy the notebook function blindly.

Understand each transformation.

---

# 15. STEP 9 — Test the Encoder Without an LLM

## Reason

This should be deterministic.

There is no reason to spend API calls testing Base64.

Write unit tests.

Test:

### Valid image

```text
image → data URL
```

### MIME type

Ensure:

```text
PNG → image/png
JPEG → image/jpeg
```

### Invalid file

Ensure your code fails clearly.

### Empty input

Ensure it does not silently produce garbage.

---

# 16. STEP 10 — Build the Multimodal Message

## Reason

This is the central learning objective.

OpenRouter's multimodal chat request uses a message whose `content` contains typed parts such as:

```text
text
+
image_url
```

rather than treating the image as ordinary text.

## Build

Create a function that transforms:

```text
image
+
user question
```

into:

```text
messages
```

Conceptually:

```text
[
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": QUESTION
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": IMAGE_DATA_URL
                }
            }
        ]
    }
]
```

## Important

Keep this function independent of OpenRouter.

It should construct the message.

The OpenRouter client should send it.

This distinction is important.

---

# 17. STEP 11 — Make Prompt Construction Explicit

## Reason

The IBM lab combines:

```text
assistant_prompt
+
user_query
```

into one string.

For your professional implementation, make the prompt responsibility explicit.

Create:

```text
src/prompts/vision.py
```

Define reusable prompts for:

### Caption

```text
Describe the image clearly and concisely.
```

### Question answering

```text
Answer the user's question based only on the image.
```

### Counting

```text
Count the requested objects visible in the image.
```

### Extraction

```text
Extract the requested information from the image.
```

Do not create an enormous prompt framework.

The point is simply to keep prompt logic out of the provider client.

---

# 18. STEP 12 — Build the Vision Service

## Reason

Now combine the components.

Target architecture:

```text
User
 ↓
Vision Service
 ↓
Image Loader
 ↓
Image Encoder
 ↓
Prompt Builder
 ↓
OpenRouter Client
 ↓
Vision Model
 ↓
Result
```

Create:

```text
src/services/vision.py
```

The service should expose high-level operations such as:

```text
caption_image(...)
answer_image_question(...)
```

Potentially later:

```text
count_objects(...)
extract_information(...)
assess_image(...)
```

## Important architectural principle

The service should not care whether the model is:

```text
Model A
Model B
Model C
```

It only asks the client to generate a response.

---

# 19. STEP 13 — Implement Image Captioning

## Reason

This reproduces the primary exercise from the IBM lab.

The original notebook asks:

```text
Describe the photo
```

for each image.

## Build

Start with one image.

Input:

```text
image-1.png
```

Prompt:

```text
Describe the photo.
```

Output:

```text
caption
```

Do not process four images immediately.

Get one working first.

---

# 20. STEP 14 — Add the Four Original Lab Tasks

Once captioning works, reproduce the notebook's four different use cases.

## Task A — Captioning

```text
Describe the photo.
```

## Task B — Object counting

The original lab asks:

```text
How many cars are in this image?
```

## Task C — Visual assessment

The original lab asks:

```text
How severe is the damage in this image?
```

## Task D — Information extraction

The original lab asks:

```text
How much sodium is in this product?
```

The important lesson is:

```text
Same vision pipeline
        +
different user question
        =
different capability
```

You are not building four separate AI systems.

---

# 21. STEP 15 — Add a CLI

## Reason

Before building a web API, make the core application usable from the terminal.

This gives you a simple way to test the entire pipeline.

Example interface:

```bash
python -m src.main \
    --image assets/image-1.png \
    --task caption
```

Or:

```bash
python -m src.main \
    --image assets/image-2.png \
    --task question \
    --question "How many cars are in this image?"
```

## Tasks

Support initially:

```text
caption
question
```

Do not create an elaborate CLI framework yet.

---

# 22. STEP 16 — Add Structured Application Results

## Reason

Do not return raw provider responses everywhere.

Create:

```text
src/models/result.py
```

Represent the application-level result.

For example, conceptually:

```text
VisionResult
├── text
├── model
├── task
└── metadata
```

The exact schema is up to you.

The key concept:

```text
Provider response
        ↓
Application result
```

This prevents OpenRouter's response format from leaking throughout your application.

---

# 23. STEP 17 — Add Error Handling

## Reason

AI API calls fail.

Your application should distinguish between:

```text
Invalid input
API authentication failure
Model unavailable
Unsupported image
Timeout
Rate limit
Provider failure
Unexpected response
```

Create:

```text
src/exceptions.py
```

Define meaningful application exceptions.

Do not expose huge raw provider stack traces to users.

---

# 24. STEP 18 — Add Timeouts

## Reason

Network calls can hang.

Your AI client should have a reasonable timeout.

Do not allow:

```text
user → request → forever
```

Use an explicit timeout and handle timeout errors.

---

# 25. STEP 19 — Add Logging

## Reason

You want to know what your application is doing without printing secrets.

Log things such as:

```text
task
model
image size
request duration
success/failure
```

Never log:

```text
OPENROUTER_API_KEY
```

and be careful about logging image data or sensitive user content.

---

# 26. STEP 20 — Add Cost / Usage Awareness

## Reason

Multimodal requests can be more expensive than ordinary text requests.

You should know what you're sending.

Track where practical:

```text
model
request duration
usage information returned by API
```

Do not build billing infrastructure.

Just make the application observable.

---

# 27. STEP 21 — Add Model Switching

## Reason

One of the advantages of OpenRouter is that the application can change the model without changing the multimodal message structure.

OpenRouter's image guide explicitly describes the same image-message structure being usable across vision-capable models, with the model field being the primary change.

Your architecture should therefore allow:

```text
MODEL=A
```

then:

```text
MODEL=B
```

without touching:

```text
VisionService
ImageEncoder
PromptBuilder
CLI
```

Only configuration should change.

---

# 28. STEP 22 — Compare Two Vision Models

## Reason

This turns the project from:

> "I called a vision API."

into:

> "I understand multimodal model selection."

Run the same images and questions through two models.

Keep:

```text
same image
same prompt
same task
```

Change only:

```text
model
```

Record:

* Response quality
* OCR quality
* Counting accuracy
* Caption detail
* Latency
* Cost
* Failure behavior

Do not rely only on your subjective impression.

Create a small evaluation dataset.

---

# 29. STEP 23 — Create a Small Evaluation Dataset

Create:

```text
evaluation/
├── cases.json
└── README.md
```

Each case should contain:

```text
image
task
question
expected behavior
```

Example:

```json
{
    "image": "image-2.png",
    "task": "counting",
    "question": "How many cars are in this image?",
    "expected": "1"
}
```

You don't need hundreds of examples.

Start with:

```text
10–20 cases
```

covering:

* Captioning
* Counting
* Color
* OCR
* Product labels
* Visual reasoning

---

# 30. STEP 24 — Evaluate Deterministically Where Possible

## Reason

LLM output is often not deterministic.

For example:

```text
"There is one car."
```

and:

```text
"I can see a single car."
```

mean the same thing.

Do not blindly compare strings.

For tasks like counting:

```text
expected = 1
```

you can evaluate the extracted number.

For extraction:

```text
expected sodium = X
```

you can normalize the result.

For captioning:

Use human evaluation initially.

---

# 31. STEP 25 — Add Retry / Resilience Carefully

## Reason

Network and provider failures happen.

Only retry failures where retrying makes sense.

Potential retry cases:

```text
temporary network error
temporary provider failure
rate limit with appropriate backoff
```

Do not blindly retry:

```text
invalid API key
invalid image
unsupported model
invalid request
```

Otherwise you can turn one error into many unnecessary API calls.

---

# 32. STEP 26 — Add Optional OpenRouter Fallbacks

## Reason

OpenRouter supports model fallback mechanisms, allowing alternative models to be tried when the preferred model fails.

Do not implement this at the beginning.

First understand:

```text
single model
```

Then optionally support:

```text
primary vision model
        ↓
fallback vision model
```

This is useful later for reliability.

---

# 33. STEP 27 — Add Image Optimization

## Reason

Large images increase payload size and potentially cost.

Before sending an image:

```text
original image
      ↓
validate
      ↓
resize if necessary
      ↓
encode
      ↓
send
```

Consider:

* Maximum dimensions
* JPEG/WebP conversion where appropriate
* Quality
* File size

Do not aggressively compress images if it destroys information needed for OCR.

---

# 34. STEP 28 — Add Security Boundaries

Before considering the project "professional", handle:

### Secrets

Never commit:

```text
.env
```

### User files

Treat uploaded images as untrusted input.

### File paths

Prevent arbitrary filesystem access if you later expose this through an API.

### URLs

If you allow arbitrary remote image URLs later, consider SSRF risks.

Do not implement remote URL fetching blindly in a public API.

For the initial project, local images are enough.

---

# 35. STEP 29 — Refactor After It Works

## Reason

Do not over-engineer before you understand the problem.

Your first implementation will probably look like:

```text
main()
  ↓
load image
  ↓
encode
  ↓
call model
```

That is okay.

Once it works, refactor toward:

```text
Client
Service
Image utilities
Prompt utilities
Configuration
Models
Exceptions
```

The goal is to understand **why** each abstraction exists.

---

# 36. STEP 30 — Add Automated Tests

Minimum test categories:

## Unit tests

### Image encoder

Test:

```text
PNG → valid data URL
JPEG → valid data URL
```

### Image loader

Test:

```text
existing file
missing file
invalid file
```

### Prompt builder

Test:

```text
question → correct message structure
```

### Result parser

Test:

```text
valid provider response
malformed provider response
empty response
```

## Mock the LLM

Do NOT call OpenRouter in normal unit tests.

Use mocks.

Your test suite should remain:

```text
fast
cheap
offline
repeatable
```

---

# 37. STEP 31 — Add Integration Tests

Create a small separate integration test suite.

Example:

```text
tests/integration/
```

These tests may actually call OpenRouter.

Do not run them on every local unit-test command.

Use something explicit such as:

```bash
pytest -m integration
```

The integration test should verify:

```text
Python
 ↓
OpenRouter
 ↓
vision model
 ↓
image
 ↓
response
```

---

# 38. STEP 32 — Optional FastAPI Layer

Only after the Python service works.

Add:

```text
src/api/
├── app.py
└── routes.py
```

Expose:

```http
POST /v1/vision/caption
```

and:

```http
POST /v1/vision/question
```

Possible request:

```text
multipart/form-data
```

containing:

```text
image
question
```

Response:

```json
{
    "task": "question",
    "answer": "...",
    "model": "..."
}
```

The API layer should call:

```text
VisionService
```

It should NOT contain OpenRouter logic.

---

# 39. STEP 33 — Optional Gradio Interface

The original IBM ecosystem frequently uses Gradio for ML demonstrations, but do not make the UI the foundation of the project.

If you add it, architecture should remain:

```text
Gradio
   ↓
VisionService
   ↓
OpenRouterClient
   ↓
Vision Model
```

not:

```text
Gradio
   ↓
OpenRouter API directly
```

The UI is only an interface.

---

# 40. STEP 34 — Add Docker

After the local application is stable.

Create:

```text
Dockerfile
.dockerignore
```

The container should receive:

```text
OPENROUTER_API_KEY
```

through environment configuration.

Never bake the API key into the image.

Test:

```text
Docker
 ↓
Python application
 ↓
OpenRouter
```

---

# 41. STEP 35 — Write the README

The README should explain:

## 1. What it is

A local multimodal image-understanding application using OpenRouter.

## 2. What it demonstrates

* Vision LLMs
* Multimodal prompts
* Image encoding
* OpenAI-compatible APIs
* Provider abstraction
* Evaluation
* Testing

## 3. Architecture

Include a diagram:

```text
                ┌──────────────────┐
                │   User / CLI     │
                └────────┬─────────┘
                         ↓
                ┌──────────────────┐
                │  Vision Service  │
                └────────┬─────────┘
                         ↓
          ┌──────────────┴──────────────┐
          ↓                             ↓
 ┌────────────────┐             ┌────────────────┐
 │ Image Pipeline │             │ Prompt Builder │
 └───────┬────────┘             └───────┬────────┘
         └──────────────┬───────────────┘
                        ↓
                ┌──────────────────┐
                │ OpenRouter Client│
                └────────┬─────────┘
                         ↓
                ┌──────────────────┐
                │ Vision LLM       │
                └──────────────────┘
```

## 4. Setup

Explain:

```text
venv
dependencies
.env
model configuration
```

## 5. Usage

Show captioning and visual Q&A.

## 6. Evaluation

Explain your test dataset and results.

## 7. Architecture decisions

Explain why:

* OpenRouter
* provider abstraction
* Base64
* service layer
* configuration
* tests

---

# 42. STEP 36 — Document Architecture Decisions

Create:

```text
docs/
└── decisions/
```

Start with:

```text
ADR-001-openrouter.md
ADR-002-image-representation.md
ADR-003-provider-abstraction.md
```

Each ADR should answer:

```text
Context
Decision
Why
Alternatives
Consequences
```

Example:

### ADR-001

Why use OpenRouter instead of direct provider SDKs?

### ADR-002

Why support Base64 data URLs?

### ADR-003

Why isolate the provider client?

---

# 43. STEP 37 — Final Project Structure

Target something close to:

```text
multimodal-openrouter/
│
├── assets/
│   ├── image-1.png
│   ├── image-2.png
│   ├── image-3.png
│   └── image-4.png
│
├── evaluation/
│   ├── cases.json
│   └── README.md
│
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── exceptions.py
│   │
│   ├── clients/
│   │   ├── __init__.py
│   │   └── openrouter.py
│   │
│   ├── images/
│   │   ├── __init__.py
│   │   ├── loader.py
│   │   └── encoder.py
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   └── vision.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   └── vision.py
│   │
│   └── models/
│       ├── __init__.py
│       └── result.py
│
├── tests/
│   ├── unit/
│   │   ├── test_encoder.py
│   │   ├── test_loader.py
│   │   ├── test_prompts.py
│   │   └── test_vision_service.py
│   │
│   └── integration/
│       └── test_openrouter_vision.py
│
├── docs/
│   └── decisions/
│       ├── ADR-001-openrouter.md
│       ├── ADR-002-image-representation.md
│       └── ADR-003-provider-abstraction.md
│
├── .env
├── .env.example
├── .gitignore
├── Dockerfile
├── PLAN.md
├── README.md
└── pyproject.toml
```

---

# 44. Recommended Build Order

Do not build everything in one pass.

Follow this exact progression:

```text
PHASE 1 — Understand
    ↓
Original notebook
    ↓
Understand multimodal message structure

PHASE 2 — Provider
    ↓
OpenRouter configuration
    ↓
Text-only API call
    ↓
Vision API call

PHASE 3 — Image pipeline
    ↓
Local image
    ↓
Validation
    ↓
Base64
    ↓
Data URL

PHASE 4 — Application
    ↓
Message builder
    ↓
Vision client
    ↓
Vision service
    ↓
Captioning
    ↓
Visual Q&A

PHASE 5 — Engineering
    ↓
Errors
    ↓
Logging
    ↓
Tests
    ↓
Configuration
    ↓
Evaluation

PHASE 6 — Extensions
    ↓
Multiple models
    ↓
Model comparison
    ↓
FastAPI
    ↓
Gradio
    ↓
Docker
```

---

# 45. Definition of Done

The project is complete when you can run:

```text
image
  +
question
  ↓
your Python application
  ↓
OpenRouter
  ↓
vision model
  ↓
answer
```

and explain every stage without looking at the notebook.

You should be able to answer these questions:

### API

1. What does OpenRouter actually do?
2. Why is the API compatible with the OpenAI client?
3. What is the base URL?
4. What is a model slug?

### Multimodal input

5. Why isn't an image sent as ordinary text?
6. What is `image_url`?
7. What is a Data URL?
8. Why would you use Base64?
9. When would you use a normal HTTPS image URL instead?

### Architecture

10. Why is the OpenRouter client separate from the vision service?
11. Why is prompt construction separate from the provider?
12. Why should the model be configuration?
13. Why should the API layer not directly call OpenRouter?

### Reliability

14. What happens if the API key is invalid?
15. What happens if the model doesn't support images?
16. What happens if the image is corrupt?
17. What happens if the provider times out?
18. Which errors should be retried?

### Evaluation

19. How do you know the model counted the objects correctly?
20. How do you evaluate OCR-like extraction?
21. How would you compare two vision models fairly?

If you cannot answer these yet, the project is not finished.

---

# 46. Important Learning Rule

Do **not** ask an AI coding agent to build the entire repository from this PLAN.md.

Build each phase yourself.

For every step:

```text
1. Read the reason.
2. Predict how you would implement it.
3. Implement it.
4. Run it.
5. Inspect the result.
6. Explain why it works.
7. Only then continue.
```

If you get stuck, use an agent to explain the problem or review your implementation before asking it to write code.

The purpose of this project is not:

> "Have AI generate another project."

The purpose is:

> "Understand how a multimodal AI application actually works."

---

# 47. Final Extension Ideas

Only after the core system is understood, consider:

### Multimodal RAG

```text
Documents
   ↓
Text + Images
   ↓
Retrieval
   ↓
Vision LLM
```

### Document understanding

```text
PDF
 ↓
pages/images
 ↓
vision model
 ↓
structured information
```

### Structured extraction

Ask the model to produce:

```json
{
    "product_name": "...",
    "sodium": "...",
    "serving_size": "..."
}
```

Then validate it with Pydantic.

### FastAPI production service

```text
POST /v1/vision/analyze
```

### Model evaluation harness

```text
same dataset
     ↓
model A
model B
model C
     ↓
metrics
     ↓
comparison
```

### Provider abstraction

Eventually allow:

```text
VisionProvider
├── OpenRouterProvider
├── DirectProvider
└── LocalProvider
```

But only introduce this abstraction when you have a real second provider.

Do not build abstractions for imaginary requirements.

---

# 48. Core Concept to Remember

The entire project can be reduced to this:

```text
IMAGE
  +
INSTRUCTION
      ↓
MULTIMODAL MESSAGE
      ↓
VISION-CAPABLE MODEL
      ↓
TEXT / STRUCTURED RESULT
```

OpenRouter is the model-access layer.

Your application architecture sits around it.

The image encoder is an input-preparation component.

The vision service is your application logic.

The model is an external dependency.

Keeping those responsibilities separate is the main engineering lesson of this rebuild.
