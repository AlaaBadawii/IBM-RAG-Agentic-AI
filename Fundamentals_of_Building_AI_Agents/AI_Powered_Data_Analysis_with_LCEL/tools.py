import glob
import os
from typing import Any

import pandas as pd
from langchain_core.tools import tool
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

DATAFRAME_CACHE = {}


@tool
def list_csv_files() -> list[str] | None:
    """
    List all CSV files in the current directory.

    Returns:
        A list of CSV file names.
    """
    csv_files = glob.glob(os.path.join(os.getcwd(), "*.csv"))
    if not csv_files:
        return None
    return [os.path.basename(file) for file in csv_files]


@tool
def preload_datasets(paths: list[str]) -> str:
    """
    Loads CSV files into a global cache if not already loaded.

    This function helps to efficiantly manage datasets by loading them once
    and storing htem in memory for future use. Without caching, you would waste tokens describing contents reapetedly in agent responses.

    Args:
        paths: A list of file paths to csv files
    Returns:
        A message summarizing which datasets were loaded or already cached
    """
    loaded = []
    cached = []

    for path in paths:
        if path not in DATAFRAME_CACHE:
            DATAFRAME_CACHE[path] = pd.read_csv(path)
            loaded.append(path)
        else:
            cached.append(path)

    return f"Loaded datasets: {loaded}\nAlready cached: {cached}"


@tool
def get_dataset_summaries(dataset_paths: list[str]) -> list[dict[str, Any]]:
    """
    Analyze multiple CSV files and return metadata summries for each.

    Args:
        dataset_paths (list[str]):
            A list of file paths to csv datasets
    Returns:
        List[Dict[str, Any]]:
            A list of summries, one per dataset, each containing metadata:
            - "file_name": The name of the dataset file.
            - "column_names": A list of column names in the dataset.
            - "data_types": A list of data types corresponding to each column.
    """
    summaries = []
    for path in dataset_paths:
        if path not in DATAFRAME_CACHE:
            DATAFRAME_CACHE[path] = pd.read_csv(path)

        df = DATAFRAME_CACHE[path]
        summary = {
            "file_name": path,
            "column_names": df.columns.tolist(),
            "data_types": df.dtypes.astype(str).tolist(),
        }
        summaries.append(summary)

    return summaries


@tool
def call_dataframe_method(file_name: str, method: str) -> str:
    """
    Execute a method on a DataFrame and return the result
    This tool lets you run simple DtaFrame methods like 'head', 'tail', or 'describe'
    on a cached dataset that has been preloaded using the 'preload_datasets' tool.
    It is useful for quickly inspecting the data without needing to load it again.

    Args:
        file_name (str): The name of the cached dataset.
        method (str): The name of the method to execute.

    Returns:
        str: The result of the method execution.
    Example:
        If you have preloaded a dataset named 'data.csv', you can call:
        call_dataframe_method(file_name='data.csv', method='head')
        to get the first few rows of the dataset.
    """
    if file_name not in DATAFRAME_CACHE:
        try:
            DATAFRAME_CACHE[file_name] = pd.read_csv(file_name)
        except FileNotFoundError:
            return f"Error: The file '{file_name}' was not found."
        except (
            OSError,
            ValueError,
            pd.errors.EmptyDataError,
            pd.errors.ParserError,
        ) as e:
            return f"Error loading '{file_name}': {e!s}"

    df = DATAFRAME_CACHE[file_name]
    func = getattr(df, method, None)
    if func is None or not callable(func):
        return f"Error: The method '{method}' is not valid for DataFrame."

    try:
        result = func()
        return str(result)
    except (TypeError, ValueError, KeyError, IndexError, NotImplementedError) as e:
        return f"Error executing '{method}' on '{file_name}': {e!s}"


@tool
def evaluate_classification_dataset(
    file_name: str, target_column: str
) -> dict[str, float | str]:
    """
    Train and evaluate a classifier on a dataset using the specified target column.

    Args:
        file_name (str): The name of the cached dataset.
        target_column (str): The name of the target column for classification.

    Returns:
        dict[str, float | str]: A dictionary containing the model's accuracy
            score or an error message.
    """
    if file_name not in DATAFRAME_CACHE:
        try:
            DATAFRAME_CACHE[file_name] = pd.read_csv(file_name)
        except FileNotFoundError:
            return {"error": f"The file '{file_name}' was not found."}
        except (
            OSError,
            ValueError,
            pd.errors.EmptyDataError,
            pd.errors.ParserError,
        ) as e:
            return {"error": f"Error loading '{file_name}': {e!s}"}

    df = DATAFRAME_CACHE[file_name]

    if target_column not in df.columns:
        return {"error": f"Target column '{target_column}' not found in '{file_name}'."}

    X = df.drop(columns=[target_column])
    y = df[target_column]
    try:
        x_train, x_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        model = RandomForestClassifier()
        model.fit(x_train, y_train)
        y_pred = model.predict(x_test)
        accuracy = accuracy_score(y_test, y_pred)
    except ValueError as e:
        return {
            "error": f"Classification failed on '{file_name}' column "
            f"'{target_column}': {e!s}. This dataset may be for regression, "
            "not classification."
        }
    except Exception as e:
        return {"error": f"Classification failed: {e!s}"}

    return {"accuracy": float(accuracy)}

@tool
def evaluate_regression_dataset(
    file_name: str, target_column: str
) -> dict[str, float | str]:
    """
    Train and evaluate a regression model on a dataset using the specified target column.

    Args:
        file_name (str): The name of the cached dataset.
        target_column (str): The name of the target column for regression.

    Returns:
        dict[str, float | str]: A dictionary containing the model's R^2 score
            or an error message.
    """
    if file_name not in DATAFRAME_CACHE:
        try:
            DATAFRAME_CACHE[file_name] = pd.read_csv(file_name)
        except FileNotFoundError:
            return {"error": f"The file '{file_name}' was not found."}
        except (
            OSError,
            ValueError,
            pd.errors.EmptyDataError,
            pd.errors.ParserError,
        ) as e:
            return {"error": f"Error loading '{file_name}': {e!s}"}

    df = DATAFRAME_CACHE[file_name]

    if target_column not in df.columns:
        return {"error": f"Target column '{target_column}' not found in '{file_name}'."}

    X = df.drop(columns=[target_column])
    y = df[target_column]
    try:
        x_train, x_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        model = RandomForestRegressor()
        model.fit(x_train, y_train)
        y_pred = model.predict(x_test)
        r2 = r2_score(y_test, y_pred)
        mse = mean_squared_error(y_test, y_pred)
    except ValueError as e:
        return {
            "error": f"Regression failed on '{file_name}' column "
            f"'{target_column}': {e!s}."
        }
    except Exception as e:
        return {"error": f"Regression failed: {e!s}"}

    return {"r2_score": float(r2), "mse": float(mse)}