# Data Visualization Agent

**Status: Guided notebook retained; standalone script is an incomplete draft.**

[Course 6](../README.md) · [Certificate overview](../../README.md)

## What Exists

- [`chat-with-your-dataframe-using-langchain-v1.ipynb`](chat-with-your-dataframe-using-langchain-v1.ipynb): IBM Skills Network lab on using natural language to inspect a student dataset and request charts with `create_pandas_dataframe_agent`.
- [`main.py`](main.py): draft watsonx/pandas-agent wiring that downloads the student CSV, asks for a gender-count bar chart, and prints the final intermediate tool input.

The notebook is course material with guided exercises. Its retained cells do not
establish that a standalone application is complete or that the current script runs.

## Technologies and Intended Workflow

The source references pandas, matplotlib, `langchain-experimental`, and IBM
watsonx clients. The intended flow is CSV → dataframe agent → generated analysis
or plotting code → inspection of intermediate tool steps.

## Current Limitations

- `main.py` uses literal placeholder URL, API key, model ID, and project ID values; it does not read environment variables or load `.env`.
- It imports a legacy `ibm_watson_machine_learning` LangChain extension alongside `ibm_watsonx_ai`; a compatible dependency stack is not specified.
- No standalone `requirements.txt`, `.env.example`, automated tests, CLI, or chart-serving UI is tracked.
- The script prints generated tool input rather than providing a complete chart-output workflow; it assumes an intermediate step exists.

Open the notebook in a Jupyter-compatible viewer to read the guided lab and its
environment requirements. There is no verified standalone execution command to
provide until credentials, dependencies, and the chart workflow are completed.
