from src.tools import sum_numbers_with_complex_output


def test_sum_complex_output_integers_and_decimals():
    output = sum_numbers_with_complex_output.invoke(
        {"inputs": "Add 10, 20.5, and -3."}
    )

    assert output == {"result": 27.5}


def test_sum_complex_output_integers_only():
    output = sum_numbers_with_complex_output.invoke(
        {"inputs": "10 20 30"}
    )

    assert output == {"result": 60.0}


def test_sum_complex_output_negative_and_decimal():
    output = sum_numbers_with_complex_output.invoke(
        {"inputs": "Values are -2.5 and -3.5"}
    )

    assert output == {"result": -6.0}


def test_sum_complex_output_no_numbers():
    output = sum_numbers_with_complex_output.invoke(
        {"inputs": "hello world, no digits here!"}
    )

    assert output == {"result": "No numbers found in input."}


def test_sum_complex_output_empty_string():
    output = sum_numbers_with_complex_output.invoke({"inputs": ""})

    assert output == {"result": "No numbers found in input."}


def test_sum_complex_output_gdp_example():
    # Mirrors the agent.py example: 27.72 + 2.14 + 1.79 = 31.65
    output = sum_numbers_with_complex_output.invoke(
        {"inputs": "US GDP was approximately $27.72 trillion, Canada's was $2.14 trillion and Mexico's was $1.79 trillion"}
    )

    assert output["result"] == 31.65
