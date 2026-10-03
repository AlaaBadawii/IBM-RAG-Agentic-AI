import os

from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from tools import (
    call_dataframe_method,
    evaluate_classification_dataset,
    evaluate_regression_dataset,
    get_dataset_summaries,
    list_csv_files,
    preload_datasets,
)

load_dotenv()  # Load environment variables from .env file

API_KEY = os.getenv("OPENROUTER_API_KEY")
# Support both names: .env currently uses BASE_URL, code used OPENROUTER_BASE_URL
BASE_URL = os.getenv("OPENROUTER_BASE_URL") or os.getenv(
    "BASE_URL", "https://openrouter.ai/api/v1"
)
MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")

if not API_KEY:
    raise ValueError(
        "OPENROUTER_API_KEY is missing. Set it in .env: OPENROUTER_API_KEY=<your-key>"
    )

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are a data science assistant. Use the available tools to analyze CSV files. "
                "Your job is to determine whether each dataset is for classification or regression, "
                "based on its structure. "
                "Only use evaluate_classification_dataset for discrete class labels, "
                "and evaluate_regression_dataset for continuous targets. "
                "If a tool returns an error, read it and try the other evaluation tool instead of crashing."
            ),
        ),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("user", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
)

llm = ChatOpenAI(
    model=MODEL,
    api_key=SecretStr(API_KEY) if API_KEY else None,
    base_url=BASE_URL,
)

tools = [
    list_csv_files,
    preload_datasets,
    get_dataset_summaries,
    call_dataframe_method,
    evaluate_classification_dataset,
    evaluate_regression_dataset,
]

agent = create_openai_tools_agent(llm, tools, prompt)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True,
    handle_tool_error=True,
    max_iterations=15,
)
print("📊 Ask questions about your dataset (type 'exit' to quit):") if __name__ == "__main__" else None

chat_history: list = []

if __name__ == "__main__":
    while True:
        try:
            user_input = input(" You:")
        except (EOFError, KeyboardInterrupt):
            print("\nsee ya later")
            break
        if user_input.strip().lower() in ["exit", "quit"]:
            print("see ya later")
            break

        try:
            result = agent_executor.invoke(
                {"input": user_input, "chat_history": chat_history}
            )
            print(f"my Agent: {result['output']}")
            chat_history.extend(
                [HumanMessage(content=user_input), AIMessage(content=result["output"])]
            )
        except Exception as e:  # noqa: BLE001 - keep the interactive loop alive
            print(f"my Agent [error, continuing]: {e!s}")
