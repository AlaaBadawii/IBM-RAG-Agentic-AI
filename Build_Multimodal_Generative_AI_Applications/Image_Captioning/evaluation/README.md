# Evaluation Dataset

Covers captioning, counting, assessment, and extraction tasks.

[← Image Captioning project](../README.md) · [Course 5](../../README.md)

[`cases.json`](cases.json) contains five qualitative scenarios, including an
image-question case. Image filenames resolve under [`../assets/`](../assets/).
These are desired behaviors, not stored successful model responses or benchmarks.

Each case contains:
- image: asset filename
- task: captioning, counting, assessment, extraction, question
- question: the prompt to send
- expected_behavior: what the model should do

## Using the Cases

From the project root, a captioning case maps to the CLI's `caption` task
(the JSON dataset uses the label `captioning`):

```bash
python -m src.main --image assets/image-1.jpg --task caption
```

The other CLI task names are `counting`, `assessment`, `extraction`, and `question`.
Use the object's name for counting, the requested field for extraction, and a full
question for VQA. Inspect the image before deciding whether the case's expected
behavior is meaningful.

[`tests/test_evaluation.py`](../tests/test_evaluation.py) checks JSON structure,
required fields, and task labels. It does not score actual model answers. There
is no automated quality-scoring runner or measured benchmark in this directory.
