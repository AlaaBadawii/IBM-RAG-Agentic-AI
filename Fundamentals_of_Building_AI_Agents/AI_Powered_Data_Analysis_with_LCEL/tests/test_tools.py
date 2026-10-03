"""Offline tests for the dataset tools (no API key or network needed)."""

import os

import tools
from tools import (
    call_dataframe_method,
    evaluate_classification_dataset,
    evaluate_regression_dataset,
    get_dataset_summaries,
    list_csv_files,
    preload_datasets,
)

CLASSIFICATION_CSV = "classification-dataset.csv"
REGRESSION_CSV = "regression-dataset.csv"


def setup_function(_):
    tools.DATAFRAME_CACHE.clear()


def test_list_csv_files_finds_both_datasets():
    files = list_csv_files.invoke({})
    assert CLASSIFICATION_CSV in files
    assert REGRESSION_CSV in files


def test_preload_datasets_caches():
    first = preload_datasets.invoke({"paths": [CLASSIFICATION_CSV]})
    assert CLASSIFICATION_CSV in first
    second = preload_datasets.invoke({"paths": [CLASSIFICATION_CSV]})
    assert "Already cached" in second


def test_get_dataset_summaries_schema():
    summaries = get_dataset_summaries.invoke(
        {"dataset_paths": [CLASSIFICATION_CSV, REGRESSION_CSV]}
    )
    assert len(summaries) == 2
    by_name = {s["file_name"]: s for s in summaries}
    assert "target" in by_name[CLASSIFICATION_CSV]["column_names"]
    assert "target" in by_name[REGRESSION_CSV]["column_names"]
    assert len(by_name[CLASSIFICATION_CSV]["column_names"]) == len(
        by_name[CLASSIFICATION_CSV]["data_types"]
    )


def test_call_dataframe_method_head_and_errors():
    head = call_dataframe_method.invoke(
        {"file_name": CLASSIFICATION_CSV, "method": "head"}
    )
    assert "mean radius" in head
    bad_method = call_dataframe_method.invoke(
        {"file_name": CLASSIFICATION_CSV, "method": "not_a_method"}
    )
    assert bad_method.startswith("Error")
    missing = call_dataframe_method.invoke(
        {"file_name": "no-such-file.csv", "method": "head"}
    )
    assert missing.startswith("Error")


def test_evaluate_classification_dataset_accuracy():
    result = evaluate_classification_dataset.invoke(
        {"file_name": CLASSIFICATION_CSV, "target_column": "target"}
    )
    assert "accuracy" in result
    assert result["accuracy"] > 0.9


def test_evaluate_classification_on_regression_data_returns_error():
    result = evaluate_classification_dataset.invoke(
        {"file_name": REGRESSION_CSV, "target_column": "target"}
    )
    assert "error" in result


def test_evaluate_regression_dataset_scores():
    result = evaluate_regression_dataset.invoke(
        {"file_name": REGRESSION_CSV, "target_column": "target"}
    )
    assert "r2_score" in result
    assert "mse" in result
    assert result["r2_score"] > 0.7


def test_evaluate_unknown_target_column_returns_error():
    result = evaluate_classification_dataset.invoke(
        {"file_name": CLASSIFICATION_CSV, "target_column": "nope"}
    )
    assert "error" in result


def test_llm_module_imports_without_starting_chat():
    # Importing llm must not block on input() (guarded by __main__).
    import llm

    assert len(llm.tools) == 6
    assert llm.agent_executor.max_iterations == 15
    assert "chat_history" in str(llm.prompt.messages).lower() or any(
        "chat_history" in str(m) for m in llm.prompt.messages
    )
    assert os.getenv("OPENROUTER_API_KEY", "") != ""
