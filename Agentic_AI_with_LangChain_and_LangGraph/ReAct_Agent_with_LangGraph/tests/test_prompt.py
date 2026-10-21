"""Prompt construction tests."""

from langchain_core.messages import AIMessage, HumanMessage

from react_agent.prompt import SYSTEM_PROMPT, chat_prompt


def test_placeholder_name_matches_the_key_call_model_supplies():
    # call_model invokes the chain with {"scratch_pad": state["messages"]}.
    assert chat_prompt.input_variables == ["scratch_pad"]


def test_history_is_inserted_into_the_placeholder_after_the_system_message():
    history = [HumanMessage(content="hello"), AIMessage(content="hi there")]

    rendered = chat_prompt.invoke({"scratch_pad": history}).to_messages()

    assert rendered[0].type == "system"
    assert rendered[1:] == history


def test_system_prompt_does_not_demand_disclosure_of_internal_reasoning():
    lowered = SYSTEM_PROMPT.lower()
    assert "always explain your thinking process" not in lowered
    assert "chain-of-thought" in lowered


def test_system_prompt_treats_tool_output_as_untrusted():
    assert "untrusted" in SYSTEM_PROMPT.lower()
