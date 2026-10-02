from src.tools import multiply_numbers


def test_multiply_numbers_str():
    output = multiply_numbers.invoke("Multiply numbers 10 20 30")

    assert output == {"result": 6000}


def test_multiply_numbers_dict():
    output = multiply_numbers.invoke({"inputs": {"numbers": [10, 20, 30]}})

    assert output == {"result": 6000}


def test_multiply_numbers_single_number():
    output = multiply_numbers.invoke({"inputs": {"numbers": [7]}})

    assert output == {"result": 7}


def test_multiply_numbers_with_zero():
    output = multiply_numbers.invoke({"inputs": {"numbers": [10, 0, 5]}})

    assert output == {"result": 0}


def test_multiply_numbers_empty_list():
    # No numbers: loop never runs, result stays at initial value 1
    output = multiply_numbers.invoke({"inputs": {"numbers": []}})

    assert output == {"result": 1}


def test_multiply_numbers_negative():
    output = multiply_numbers.invoke({"inputs": {"numbers": [2, -3, 4]}})

    assert output == {"result": -24}
