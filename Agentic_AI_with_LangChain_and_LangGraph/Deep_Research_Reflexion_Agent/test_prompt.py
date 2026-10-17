from langchain_core.messages import HumanMessage

from prompt import prompt_template


def _render(first_instruction, question):
    prompt = prompt_template.partial(first_instruction=first_instruction)
    return prompt.invoke({"messages": [HumanMessage(content=question)]}).to_messages()


def test_prompt_renders_system_human_system_messages():
    messages = _render(
        "Provide a detailed ~250 word answer", "Any ideas for a healthy breakfast"
    )
    assert [message.type for message in messages] == ["system", "human", "system"]


def test_prompt_includes_the_first_instruction_and_the_question():
    messages = _render(
        "Provide a detailed ~250 word answer", "Any ideas for a healthy breakfast"
    )
    rendered = "\n".join(message.content for message in messages)
    assert "Provide a detailed ~250 word answer" in rendered
    assert "Any ideas for a healthy breakfast" in rendered


def test_prompt_asks_for_separate_search_queries():
    messages = _render("Provide a detailed ~250 word answer", "question")
    rendered = "\n".join(message.content for message in messages).lower()
    assert "search queries" in rendered
    assert "reflection" in rendered
