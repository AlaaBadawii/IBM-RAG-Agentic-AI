import asyncio
import logging
from typing import Any

from beeai_framework.agents.experimental import RequirementAgent
from beeai_framework.context import RunContext
from beeai_framework.emitter import Emitter
from beeai_framework.memory import UnconstrainedMemory
from beeai_framework.middleware.trajectory import GlobalTrajectoryMiddleware
from beeai_framework.tools import StringToolOutput, Tool, ToolRunOptions
from pydantic import BaseModel, Field

from llm import get_llm


# define tool input schema
class CalculatorInput(BaseModel):
    """Input model for basic mathematical calculations."""

    expression: str = Field(
        description="Mathematical expression using +, -, *, / (e.g. '10 + 5', '20 - 8', '4 * 6', '15 / 3')"
    )


class SimpleCalculatorTool(Tool[CalculatorInput, ToolRunOptions, StringToolOutput]):
    """
    A simple calculator tool for basic arithemtic operations add, subtract, multiply, divide.
    """

    @property
    def name(self) -> str:
        return "simple_calculator"

    @property
    def description(self) -> str:
        return "Perform basic arithmetic calculations using numbers and +, -, *, /, and parentheses."

    @property
    def input_schema(self) -> type[CalculatorInput]:
        return CalculatorInput

    def __init__(self, options: dict[str, Any] | None = None):
        super().__init__(options)

    def _create_emitter(self) -> Emitter:
        return Emitter.root().child(
            namespace=["tool", "calculator", "basic"], creator=self
        )

    def _safe_calculate(self, expression: str) -> float:
        """Safely evaluate basic arithmetic expressions."""
        expr = expression.replace(" ", "")

        allowed_chars = set("0123456789()-+*/.")
        if not all(c in allowed_chars for c in expr):
            raise ValueError(
                "Only Only numbers and basic operators (+, -, *, /, parentheses) are allowed"
            )

        try:
            result = eval(expr, {"__builtins__": {}}, {})
            return float(result)
        except ZeroDivisionError:
            raise ValueError("Division by zero isn't allowed")
        except (SyntaxError, TypeError, ValueError, NameError) as e:
            raise ValueError(f"Invalid arthemtic expression: {e!s}")

    async def _run(
        self,
        input: CalculatorInput,
        options: ToolRunOptions | None,
        context: RunContext,
    ) -> StringToolOutput:
        """Perform basic arthimetic calculations."""
        try:
            expression = input.expression.strip()

            # Perform calculation
            result = self._safe_calculate(expression)

            # Format result
            output = "🧮 Simple Calculator\n"
            output += f"Expression: {expression}\n"
            output += f"Result: {result}\n"

            # Add operation type hint
            if "+" in expression:
                output += "Operation: Addition"
            elif "-" in expression:
                output += "Operation: Subtraction"
            elif "*" in expression:
                output += "Operation: Multiplication"
            elif "/" in expression:
                output += "Operation: Division"
            else:
                output += "Operation: Basic Arithmetic"

            return StringToolOutput(output)

        except ValueError as e:
            return StringToolOutput(f"❌ Calculation Error: {e!s}")
        except (ArithmeticError, AttributeError, RuntimeError) as e:
            return StringToolOutput(f"❌ Unexpected Error: {e!s}")


async def calculator_agent():
    """RequirementAgent with SimpleCalculatorTool - Interactive Math Assistant"""
    llm = get_llm("watsonx")

    calc_agent = RequirementAgent(
        llm=llm,
        tools=[SimpleCalculatorTool()],
        memory=UnconstrainedMemory(),
        instructions="""You are a helpful math assistant. When users ask for calculations, 
        use the SimpleCalculator tool to provide accurate results. 
        Always show both the expression and the calculated result.""",
        middlewares=[GlobalTrajectoryMiddleware(included=[Tool])]
    )

    # Interactive examples - simulating human input
    math_queries = [
        "What is 15 + 27?",
        "Calculate 144 divided by 12",
        "I need to know what 8 times 9 equals",
        "What's (10 + 5) * 3 - 7?",
    ]

    for query in math_queries:
        print(f"\n👤 Human: {query}")
        result = await calc_agent.run(query)
        print(f"🤖 Agent: {result.answer.text}")


async def main() -> None:
    logging.getLogger("asyncio").setLevel(logging.CRITICAL)
    await calculator_agent()


if __name__ == "__main__":
    asyncio.run(main())
