"""AgentState / message-reducer behaviour."""

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.message import add_messages

from react_agent.agent_state import AgentState


def test_add_messages_appends_in_order():
    history = add_messages(
        [HumanMessage(content="q", id="1")],
        [AIMessage(content="a", id="2")],
    )
    assert [message.id for message in history] == ["1", "2"]


def test_add_messages_updates_a_message_with_the_same_id_in_place():
    history = add_messages(
        [AIMessage(content="draft", id="1")],
        [AIMessage(content="final", id="1")],
    )
    assert len(history) == 1
    assert history[0].content == "final"


def test_agent_state_is_a_typed_dict_with_a_messages_key():
    assert AgentState.__annotations__["messages"] is not None
