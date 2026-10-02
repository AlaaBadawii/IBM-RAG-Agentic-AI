from src.tools import sum_numbers_from_text


def test_sum_from_text_integers_and_decimals():
    result = sum_numbers_from_text.invoke({"inputs": "Add 10, 20.5, and -3."})

    assert result == 27.5


def test_sum_from_text_integers_only():
    result = sum_numbers_from_text.invoke({"inputs": "10 20 30"})

    assert result == 60.0


def test_sum_from_text_negative_and_decimal():
    result = sum_numbers_from_text.invoke({"inputs": "Values are -2.5 and -3.5"})

    assert result == -6.0


def test_sum_from_text_no_numbers_returns_zero():
    result = sum_numbers_from_text.invoke({"inputs": "hello world, no digits here!"})

    assert result == 0.0


def test_sum_from_text_empty_string_returns_zero():
    result = sum_numbers_from_text.invoke({"inputs": ""})

    assert result == 0.0


def test_sum_from_text_gdp_example():
    # Mirrors the agent.py example: 27.72 + 2.14 + 1.79 = 31.65
    result = sum_numbers_from_text.invoke(
        {
            "inputs": "US GDP was approximately $27.72 trillion, Canada's was $2.14 trillion and Mexico's was $1.79 trillion"
        }
    )

    assert result == 31.65
