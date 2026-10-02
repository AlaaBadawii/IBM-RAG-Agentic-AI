from src.tools import add_numbers_with_options


def test_add_numbers_with_options():
    nums = [-2.5, -3.5, -6.5]

    result = add_numbers_with_options.invoke({"numbers": nums, "absolute": False})

    assert result == -12.5

def test_add_abs_numbers_with_options_absolute():
    nums = [-2.5, -3.5, -6.5]

    result = add_numbers_with_options.invoke({"numbers": nums, "absolute": True})

    assert result == 12.5
