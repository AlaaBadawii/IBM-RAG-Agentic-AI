from src.tools import add_numbers


def test_add_numbers_str():
    input_1 = "Add the numbers 10, 20, and 30"

    output_1 = add_numbers.invoke(input_1)

    expected_output = {"result": 60}

    assert output_1 == expected_output

def test_add_numbers_dict():
    output_2 = add_numbers.invoke({"inputs": {"numbers": [10, 20, 30]}})

    expected_output = {"result": 60}

    assert output_2 == expected_output
