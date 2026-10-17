"""Tool-calling contract tests.

These verify that the Pydantic schemas the agent binds as tools produce the
expected JSON schemas. The actual binding of these tools to the model is tested
in ``test_chains.py`` (with the model mocked).
"""

from langchain_core.utils.function_calling import convert_to_openai_tool

from deep_research_agent.schema import AnswerQuestion, ReviseAnswer


def test_answer_question_tool_schema():
    tool = convert_to_openai_tool(AnswerQuestion)

    assert tool["type"] == "function"
    function = tool["function"]
    assert function["name"] == "AnswerQuestion"

    parameters = function["parameters"]
    assert set(parameters["properties"]) == {"answer", "reflection", "search_queries"}
    assert set(parameters["required"]) == {"answer", "reflection", "search_queries"}

    search_queries = parameters["properties"]["search_queries"]
    assert search_queries["type"] == "array"
    assert search_queries["items"] == {"type": "string"}

    reflection = parameters["properties"]["reflection"]
    assert set(reflection["properties"]) == {"missing", "superfluous"}
    assert set(reflection["required"]) == {"missing", "superfluous"}


def test_revise_answer_tool_schema_includes_references():
    function = convert_to_openai_tool(ReviseAnswer)["function"]

    assert function["name"] == "ReviseAnswer"
    assert "references" in function["parameters"]["properties"]
    assert set(function["parameters"]["required"]) == {
        "answer",
        "references",
        "reflection",
        "search_queries",
    }
