from functools import lru_cache

from langchain_core.runnables import RunnableLambda

from .llm import get_llm
from .prompt import prompt_template
from .schema import AnswerQuestion

first_responder_prompt = prompt_template.partial(
    first_instruction="Provide a detailed ~250 word answer"
)


@lru_cache(maxsize=1)
def get_responder_chain():
    """Build (once) the responder chain: prompt -> LLM bound to AnswerQuestion.

    The chain is built lazily so that importing this module does not create a
    watsonx.ai client or perform any network request.
    """

    return first_responder_prompt | get_llm().bind_tools(
        [AnswerQuestion],
        tool_choice="AnswerQuestion",
    )


responder_chain = RunnableLambda(lambda inputs: get_responder_chain().invoke(inputs))


if __name__ == "__main__":
    from langchain_core.messages import AIMessage, HumanMessage

    question = input("Question: ")
    response = responder_chain.invoke({"messages": [HumanMessage(content=question)]})

    if isinstance(response, AIMessage):
        print(response.tool_calls)
    else:
        print([])

    print("----- Answer content from the first responder -----")
    if not isinstance(response, AIMessage) or not response.tool_calls:
        raise ValueError("The responder did not return an AnswerQuestion tool call")

    answer_content = response.tool_calls[0]["args"]["answer"]
    print(answer_content)

    print("----- Reflection content from the first responder -----")
    reflection_content = response.tool_calls[0]["args"]["reflection"]
    print(reflection_content)

    print("----- Search queries from the first responder -----")
    search_queries = response.tool_calls[0]["args"]["search_queries"]
    print(search_queries)
