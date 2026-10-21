"""A safe arithmetic calculator tool.

Model-generated and user-supplied input is untrusted, so this module evaluates
expressions by walking an explicitly allowed subset of the Python AST instead of
calling ``eval()``. ``ast.literal_eval`` is *not* used either: it cannot evaluate
arithmetic operators or function calls, and it is the wrong tool for the job.

Permitted syntax:

* binary ``+``, ``-``, ``*``, ``/``, ``//``, ``%``, ``**``
* unary ``+`` and ``-``
* parentheses
* the functions in :data:`_FUNCTIONS` (``sqrt``, ``sin``, ``log``, ...)
* the constants in :data:`_CONSTANTS` (``pi``, ``e``, ``tau``)

Everything else -- attribute access, subscripting, imports, lambdas,
comprehensions, comparisons, strings, bitwise operators, arbitrary calls -- is
rejected with a :class:`CalculatorError`. Complexity is bounded to keep a
pathological expression from exhausting memory or CPU.
"""

import ast
import math
import operator
from functools import lru_cache

from langchain.tools import tool

MAX_EXPRESSION_LENGTH = 200
MAX_NODES = 100
MAX_POW_EXPONENT = 1000

_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}

_FUNCTION_NAMES = (
    "sqrt",
    "exp",
    "log",
    "log10",
    "log2",
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "sinh",
    "cosh",
    "tanh",
    "floor",
    "ceil",
    "fabs",
    "degrees",
    "radians",
    "hypot",
)
_FUNCTIONS = {name: getattr(math, name) for name in _FUNCTION_NAMES}
_FUNCTIONS["abs"] = abs
_FUNCTIONS["round"] = round


class CalculatorError(ValueError):
    """Raised when an expression is invalid or uses disallowed syntax."""


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise CalculatorError(f"unsupported constant: {node.value!r}")
        return node.value

    if isinstance(node, ast.Name):
        if node.id in _CONSTANTS:
            return _CONSTANTS[node.id]
        raise CalculatorError(f"unknown name: {node.id!r}")

    if isinstance(node, ast.UnaryOp):
        op = _UNARY_OPERATORS.get(type(node.op))
        if op is None:
            raise CalculatorError(f"unsupported unary operator: {type(node.op).__name__}")
        return op(_eval(node.operand))

    if isinstance(node, ast.BinOp):
        op = _BINARY_OPERATORS.get(type(node.op))
        if op is None:
            raise CalculatorError(f"unsupported operator: {type(node.op).__name__}")
        right = node.right
        if isinstance(node.op, ast.Pow) and isinstance(right, ast.Constant):
            if isinstance(right.value, (int, float)) and abs(right.value) > MAX_POW_EXPONENT:
                raise CalculatorError("exponent is too large")
        return op(_eval(node.left), _eval(right))

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS:
            raise CalculatorError("unsupported function call")
        if node.keywords:
            raise CalculatorError("keyword arguments are not supported")
        args = [_eval(arg) for arg in node.args]
        return _FUNCTIONS[node.func.id](*args)

    raise CalculatorError(f"unsupported expression element: {type(node).__name__}")


@lru_cache(maxsize=128)
def evaluate(expression: str) -> float:
    """Evaluate ``expression`` and return the numeric result.

    The result is cached, which makes repeated agent calls on the same
    expression cheap and side-effect free.

    Raises:
        CalculatorError: for invalid, unsupported, too-long, or too-complex
            expressions, and for division by zero.
    """

    if not isinstance(expression, str) or not expression.strip():
        raise CalculatorError("expression must be a non-empty string")
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise CalculatorError("expression is too long")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise CalculatorError(f"invalid expression syntax: {exc.msg}") from exc

    if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
        raise CalculatorError("expression is too complex")

    try:
        return _eval(tree.body)
    except ZeroDivisionError as exc:
        raise CalculatorError("division by zero") from exc
    except OverflowError as exc:
        raise CalculatorError("result is too large") from exc


@tool
def calculator(expression: str) -> str:
    """Evaluate an arithmetic expression and return the result as text.

    Supports ``+ - * / // % **``, parentheses, the constants ``pi``, ``e`` and
    ``tau``, and functions such as ``sqrt``, ``sin``, ``cos``, ``tan``, ``log``
    and ``abs``. Examples: ``2 + 3 * 4`` -> 14, ``sqrt(16)`` -> 4.0,
    ``sin(pi / 2)`` -> 1.0, ``2 ** 3`` -> 8.

    :param expression: The arithmetic expression to evaluate.
    :return: The result as a string, or an ``Error: ...`` message if the
        expression is invalid.
    """

    try:
        return str(evaluate(expression))
    except CalculatorError as exc:
        return f"Error: {exc}"
