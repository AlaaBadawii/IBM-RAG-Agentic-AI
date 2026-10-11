"""A simple agent that uses the LLM to perform tasks."""

from langchain_core.messages import BaseMessage, HumanMessage

from execute_tool import execute_tools
from llm import llm_with_tools

MAX_ITERATIONS = 10
def run_agent(user_input: str):
    messages: list[BaseMessage] = [HumanMessage(content=user_input)]

    for _ in range(MAX_ITERATIONS):
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        if response.tool_calls:
            tool_results = execute_tools(response.tool_calls)
            messages.extend(tool_results)
        else:
            break

    if response.tool_calls:
        print("Maximum iterations reached. Some tool calls may not have been executed.")
        return "Agent stopped because the maximum number of iterations was reached."
    
    return response.content

if __name__ == "__main__":
    user_input = input("Enter your request: ")
    result = run_agent(user_input)
    print("\nFinal response:")
    print(result)
