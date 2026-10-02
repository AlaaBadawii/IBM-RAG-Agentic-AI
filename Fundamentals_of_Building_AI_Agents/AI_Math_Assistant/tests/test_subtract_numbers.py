from src.tools import subtract_numbers


def test_subtract_numbers_str():
    output = subtract_numbers.invoke("Subtract numbers 10 20 30")

    assert output == {"result": -40}


def test_subtract_numbers_dict():
    output = subtract_numbers.invoke({"inputs": {"numbers": [10, 20, 30]}})

    assert output == {"result": -40}


def test_subtract_numbers_single_number():
    output = subtract_numbers.invoke({"inputs": {"numbers": [42]}})

    assert output == {"result": 42}


def test_subtract_numbers_empty_list():
    output = subtract_numbers.invoke({"inputs": {"numbers": []}})

    assert output == {"result": 0}


def test_subtract_numbers_with_negatives():
    # 10 - (-5) - 3 = 12
    output = subtract_numbers.invoke({"inputs": {"numbers": [10, -5, 3]}})

    assert output == {"result": 12}
