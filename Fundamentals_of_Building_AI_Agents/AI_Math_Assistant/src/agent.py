from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

import tools as tools_module
from llm import llm

tools = [
    value
    for name, value in vars(tools_module).items()
    if not name.startswith("_") and callable(value)
]

agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt="You are a helpful mathematical assistant that can perform various operations. Use the tools precisely and explain your reasoning clearly.",
)


if __name__ == "__main__":
    response = agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content="In 2023, the US GDP was approximately $27.72 trillion, while Canada's was around $2.14 trillion and Mexico's was about $1.79 trillion what is the total."
                )
            ]
        }
    )

    print(response["messages"][-1].content)
