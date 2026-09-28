# AI Nutrition Coach (multimodal build)

## Status
COMPLETED (implemented, documented, committed). Source:
`/home/alaabadawii/LLMs/IBM/Build_Multimodal_Generative_AI_Applications/cal_coach_app/`.

## What this is
A multimodal generative AI web application that analyzes food photos and
returns nutritional assessments: per-item identification, portion and calorie
estimates, total calories, nutrient breakdown, and a health evaluation. Built
as the applied lab of the IBM "Build Multimodal Generative AI Applications"
course (Module 3: full-stack multimodal web apps), extended with the author's
own README and project documentation.

## What's actually there (evidence)
- `app.py` — Flask backend: image upload, base64 encoding, watsonx.ai vision
  call, formatted HTML response rendering.
- `templates/`, `static/` — responsive web UI: live image preview, loading
  indicator, custom-question input (default: *"How many calories are in this
  food?"*).
- Built-in disclaimer that estimates are approximate and not medical advice.
- `README.md` — features, tech stack, project structure, setup.

## Why it matters (technical decision documented)
- A full-stack multimodal loop in one deployable app: image in, structured
  nutrition assessment out, with the vision model (`meta-llama/llama-4-
  maverick-17b-128e-instruct-fp8` via IBM watsonx.ai) doing both perception
  (what foods) and estimation (portions, calories, nutrients).
- The medical-advice disclaimer is part of the build, not an afterthought:
  model estimates are presented as approximate by design.

## Skills exercised (from course, applied here)
- Vision-language prompting, image encoding (base64), Flask full-stack apps,
  Jinja2/CSS/JS frontends, IBM watsonx.ai.

## Technologies
Python, Flask, Jinja2, IBM watsonx.ai (Llama 4 Maverick vision), Pillow,
requests, HTML/CSS/vanilla JavaScript.

## Provenance
`/home/alaabadawii/LLMs/IBM/Build_Multimodal_Generative_AI_Applications/cal_coach_app/README.md`.
Committed by the user (`88567c9` in the IBM monorepo).

## Relationship to the course
Built while completing IBM "Build Multimodal Generative AI Applications"
(Course 5 of the IBM RAG and Agentic AI Professional Certificate; certificate
record: `../certificates/ibm_build-multimodal-generative-ai-applications.md`).
The course is the learning record; this file is the implementation record.
