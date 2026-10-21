"""The ReAct chain is built lazily and binds the tool registry."""

from langchain_core.runnables import RunnableLambda

from react_agent import model_react
from react_agent.tools import tools


def test_get_model_react_is_cached_and_binds_every_tool(monkeypatch):
    bound = {}

    class _FakeModel:
        def bind_tools(self, tools_arg):
            bound["tools"] = tools_arg
            return RunnableLambda(lambda _input: "MODEL")

    monkeypatch.setattr(model_react, "get_llm", lambda: _FakeModel())
    model_react.get_model_react.cache_clear()

    first = model_react.get_model_react()
    second = model_react.get_model_react()

    assert first is second
    assert bound["tools"] is tools
    assert len(tools) == 4
    model_react.get_model_react.cache_clear()
