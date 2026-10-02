from src.tools import divide_numbers


def test_divide_numbers_str():
    output = divide_numbers.invoke("Divide numbers 100 2 5")

    assert output == {"result": 10.0}


def test_divide_numbers_dict():
    output = divide_numbers.invoke({"inputs": {"numbers": [100, 2, 5]}})

    assert output == {"result": 10.0}


def test_divide_numbers_single_number():
    output = divide_numbers.invoke({"inputs": {"numbers": [42]}})

    assert output == {"result": 42}


def test_divide_numbers_empty_list():
    output = divide_numbers.invoke({"inputs": {"numbers": []}})

    assert output == {"result": None}


def test_divide_numbers_division_by_zero():
    output = divide_numbers.invoke({"inputs": {"numbers": [10, 0]}})

    assert output == {"result": "Error: Division by zero."}


def test_divide_numbers_division_by_zero_later():
    output = divide_numbers.invoke({"inputs": {"numbers": [100, 2, 0, 5]}})

    assert output == {"result": "Error: Division by zero."}


def test_divide_numbers_float_result():
    output = divide_numbers.invoke({"inputs": {"numbers": [7, 2]}})

    assert output == {"result": 3.5}
