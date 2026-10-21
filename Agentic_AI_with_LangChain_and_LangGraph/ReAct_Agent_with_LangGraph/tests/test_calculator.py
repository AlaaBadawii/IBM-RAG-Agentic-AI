"""Calculator tool: correct arithmetic and a tightly sandboxed evaluator."""

import math

import pytest

from react_agent.tools.arithmetic import CalculatorError, calculator, evaluate


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2 + 3 * 4", 14),
        ("(2 + 3) * 4", 20),
        ("2 ** 3", 8),
        ("10 / 4", 2.5),
        ("10 // 3", 3),
        ("10 % 3", 1),
        ("-5 + 3", -2),
        ("+7", 7),
        ("2 * (3 + 4) - 5", 9),
    ],
)
def test_arithmetic_operators(expression, expected):
    assert evaluate(expression) == expected


def test_functions_and_constants():
    assert evaluate("sqrt(16)") == 4.0
    assert evaluate("sin(pi / 2)") == pytest.approx(1.0)
    assert evaluate("log(e)") == pytest.approx(1.0)
    assert evaluate("abs(-7)") == 7
    assert evaluate("cos(0)") == pytest.approx(1.0)
    assert evaluate("floor(3.7)") == 3
    assert evaluate("round(2.567, 2)") == pytest.approx(2.57)


@pytest.mark.parametrize(
    "expression",
    [
        "",
        "   ",
        "2 +",
        "2 +* 3",
        "(2 + 3",
    ],
)
def test_invalid_syntax_is_rejected(expression):
    with pytest.raises(CalculatorError):
        evaluate(expression)


@pytest.mark.parametrize(
    "expression",
    [
        "x + 1",
        "__import__('os')",
        "open('/etc/passwd')",
        "(1).__class__",
        "().__class__.__bases__",
        "[1, 2, 3]",
        "{'a': 1}",
        "'a' + 'b'",
        "lambda: 1",
        "[i for i in range(3)]",
        "1 if True else 2",
        "1 < 2",
        "1 and 2",
        "1 << 2",
        "print('hi')",
        "i.__class__",
    ],
)
def test_disallowed_syntax_is_rejected(expression):
    with pytest.raises(CalculatorError):
        evaluate(expression)


def test_division_by_zero_is_a_clear_error():
    with pytest.raises(CalculatorError, match="division by zero"):
        evaluate("1 / 0")


def test_overflow_is_a_clear_error():
    with pytest.raises(CalculatorError):
        evaluate("exp(100000)")


def test_huge_exponent_is_rejected():
    with pytest.raises(CalculatorError, match="exponent is too large"):
        evaluate("2 ** 100000")


def test_too_long_expression_is_rejected():
    with pytest.raises(CalculatorError, match="too long"):
        evaluate("1+" * 200 + "1")


def test_too_complex_expression_is_rejected():
    with pytest.raises(CalculatorError, match="too complex"):
        evaluate("1+" * 99 + "1")


def test_tool_returns_a_string_result():
    assert calculator.invoke({"expression": "2 + 3 * 4"}) == "14"


def test_tool_reports_errors_as_strings():
    result = calculator.invoke({"expression": "1 / 0"})
    assert result.startswith("Error:")
    assert "division by zero" in result


def test_cannot_execute_arbitrary_code():
    # A would-be code-execution payload must be refused, not run.
    payload = "__import__('os').system('echo pwned')"
    with pytest.raises(CalculatorError):
        evaluate(payload)
    assert calculator.invoke({"expression": payload}).startswith("Error:")
