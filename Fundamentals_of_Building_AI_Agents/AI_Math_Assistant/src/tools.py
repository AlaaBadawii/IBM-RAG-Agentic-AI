import re

from langchain_core.tools import tool


@tool
def add_numbers(inputs: str | dict[str, list[int]]) -> dict:
    """
    add a list of numbers provided in the input dictionary or extracts numbers from a string.

    Parameters:
    - inputs (str):
    string, it should contain numbers that can be extracted and summed.

    Returns:
    - dict: A dictionary with a single key "result" containing the sum of the numbers

    Example Input (Dictionary):
    {"numbers": [10, 20, 30]}

    Example Input (String):
    "Add numbers 10, 20, and 30."

    Example Output:
    {"result": 60}
    """
    if isinstance(inputs, dict):
        numbers = inputs["numbers"]
    else:
        numbers = [int(x) for x in inputs.replace(",", "").split() if x.isdigit()]

    return {"result": sum(numbers)}


@tool
def add_numbers_with_options(numbers: list[float], absolute: bool = False) -> float:
    """
    Adds a list of float numbers

    Parameters:
    - numbers (List[float]): A list of float numbers
    - absolute (bool): If True, use the absolute values

    Returns:
    - float: The total sum of numbers.
    """
    if absolute:
        numbers = [abs(num) for num in numbers]

    return sum(numbers)


@tool
def sum_numbers_with_complex_output(inputs: str) -> dict[str, float | str]:
    """
    Extracts and sums all integers and decimal numbers from the input string.

    Parameters:
    - inputs (str): A string that may contain numeric values.

    Returns:
    - dict: A dictionary with the key "result". If numbers are found, the value is their sum (float).
            If no numbers are found or an error occurs, the value is a corresponding message (str).

    Example Input:
    "Add 10, 20.5, and -3."

    Example Output:
    {"result": 27.5}
    """
    matches = re.findall(r"-?\d+(?:\.\d+)?", inputs)
    if not matches:
        return {"result": "No numbers found in input."}
    try:
        numbers = [float(num) for num in matches]
        total = sum(numbers)
        return {"result": total}
    except ValueError as e:
        return {"result": f"Error during summation: {e!s}"}

@tool
def sum_numbers_from_text(inputs: str) -> float:
    """
    Extracts and sums all integers and decimal numbers from the input string.

    Parameters:
    - inputs (str): A string that may contain numeric values.

    Returns:
    - float: The total sum of the extracted numbers. If no numbers are found, returns 0.0.

    Example Input:
    "Add 10, 20.5, and -3."

    Example Output:
    27.5
    """
    matches = re.findall(r"-?\d+(?:\.\d+)?", inputs)
    if not matches:
        return 0.0
    try:
        numbers = [float(num) for num in matches]
        return sum(numbers)
    except ValueError as e:
        raise ValueError(f"Error during summation: {e!s}")

@tool
def subtract_numbers(inputs: str | dict[str, list[int]]) -> dict:
    """
    Subtracts a list of numbers provided in the input dictionary or extracts numbers from a string.

    Parameters:
    - inputs (str):
    string, it should contain numbers that can be extracted and subtracted.

    Returns:
    - dict: A dictionary with a single key "result" containing the result of the subtraction

    Example Input (Dictionary):
    {"numbers": [10, 20, 30]}

    Example Input (String):
    "Subtract numbers 10, 20, and 30."

    Example Output:
    {"result": -40}
    """
    if isinstance(inputs, dict):
        numbers = inputs["numbers"]
    else:
        numbers = [int(x) for x in inputs.replace(",", "").split() if x.isdigit()]

    if not numbers:
        return {"result": 0}

    result = numbers[0]
    for num in numbers[1:]:
        result -= num

    return {"result": result}

@tool
def multiply_numbers(inputs: str | dict[str, list[int]]) -> dict:
    """
    Multiplies a list of numbers provided in the input dictionary or extracts numbers from a string.

    Parameters:
    - inputs (str):
    string, it should contain numbers that can be extracted and multiplied.

    Returns:
    - dict: A dictionary with a single key "result" containing the result of the multiplication

    Example Input (Dictionary):
    {"numbers": [10, 20, 30]}

    Example Input (String):
    "Multiply numbers 10, 20, and 30."

    Example Output:
    {"result": 6000}
    """
    if isinstance(inputs, dict):
        numbers = inputs["numbers"]
    else:
        numbers = [int(x) for x in inputs.replace(",", "").split() if x.isdigit()]

    result = 1
    for num in numbers:
        result *= num

    return {"result": result}


@tool
def divide_numbers(inputs: str | dict[str, list[int]]) -> dict:
    """
    Divides a list of numbers provided in the input dictionary or extracts numbers from a string.

    Parameters:
    - inputs (str):
    string, it should contain numbers that can be extracted and divided.

    Returns:
    - dict: A dictionary with a single key "result" containing the result of the division

    Example Input (Dictionary):
    {"numbers": [100, 2, 5]}

    Example Input (String):
    "Divide numbers 100, 2, and 5."

    Example Output:
    {"result": 10.0}
    """
    if isinstance(inputs, dict):
        numbers = inputs["numbers"]
    else:
        numbers = [int(x) for x in inputs.replace(",", "").split() if x.isdigit()]

    if not numbers:
        return {"result": None}

    result = numbers[0]
    for num in numbers[1:]:
        if num == 0:
            return {"result": "Error: Division by zero."}
        result /= num

    return {"result": result}


import time

import requests as _requests
import wikipedia.wikipedia as wp
from langchain_community.utilities import WikipediaAPIWrapper

wp.API_URL = "https://en.wikipedia.org/w/api.php"


def _patched_request(params, _retries=3):
    params["format"] = "json"
    if "action" not in params:
        params["action"] = "query"
    headers = {"User-Agent": "AI-Math-Assistant-Lab/1.0 (contact@example.com)"}

    last_exc = None
    for attempt in range(_retries):
        r = _requests.get(wp.API_URL, params=params, headers=headers)
        try:
            return r.json()
        except ValueError as e:
            last_exc = e
            print(
                f"Attempt {attempt + 1}/{_retries} failed — status {r.status_code}, body: {r.text[:200]!r}"
            )
            time.sleep(1)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Wikipedia request failed without a response")


wp._wiki_request = _patched_request


# Create a Wikipedia tool using the @tool decorator
@tool
def search_wikipedia(query: str) -> str:
    """Search Wikipedia for factual information about a topic.

    Parameters:
    - query (str): The topic or question to search for on Wikipedia

    Returns:
    - str: A summary of relevant information from Wikipedia
    """
    wiki = WikipediaAPIWrapper(wiki_client=wp)
    return wiki.run(query)