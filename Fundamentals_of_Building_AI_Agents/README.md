# Course 6 — Fundamentals of Building AI Agents

**Course status: Completed as of November 9, 2026 · Estimated duration: 11 hours**

[← Certificate overview](../README.md)

## Overview and Learning Objectives

The course introduces reasoning with tools, tool schemas, agent execution loops,
and built-in LangChain agents for tabular data, visualization, and SQL. Retained
work spans guided labs, adapted implementations, and an incomplete visualization draft.

- Describe what binding a tool does and what the application must still execute.
- Preserve assistant tool requests and linked `ToolMessage` observations.
- Bound agent iteration and return tool failures as useful observations.
- Build dataset-analysis and database agents with explicit configuration.
- Separate offline tool testing from live provider and database integration.

## Project and Lab Index

| Project | Actual state and implementation | Documentation |
|---|---|---|
| AI Math Assistant | Eight declared math/Wikipedia tools, `create_agent` wiring, and tool tests; import-time live call and registry limitations | [README](AI_Math_Assistant/README.md) |
| AI-Powered Data Analysis with LCEL | Adapted OpenRouter tools-agent implementation with six CSV/ML tools and local tests; the directory name is not its agent architecture | [README](AI_Powered_Data_Analysis_with_LCEL/README.md) |
| Tool-Calling Agent | Hand-written watsonx bind → invoke → execute → append loop over five YouTube tools | [README](Tool_calling_Agent/README.md) |
| NL-to-SQL Agent | Guided MySQL/Chinook tool-calling agent with a `--prompt` interface | [README](NL_SQL_Agent/README.md) |
| Data Visualization Agent | Guided notebook plus incomplete placeholder-configured draft script | [README](Data_Visualization_Agent/README.md) |

## Technologies and Implementation Details

- **LangChain:** `@tool`, `create_agent`, `create_openai_tools_agent`, `AgentExecutor`, messages, `create_sql_agent`, and `SQLDatabase`.
- **Providers:** OpenRouter through `langchain-openai`; watsonx through `langchain-ibm` and IBM SDKs.
- **Tools/data:** pandas, scikit-learn RandomForest probes, Wikipedia, pytube, yt-dlp, YouTube Transcript API, SQLAlchemy, and MySQL.
- **Testing:** pytest and mocked Wikipedia requests.

The projects intentionally retain different LangChain generations. Math uses
`create_agent` from LangChain 1.x; Data Analysis uses the 0.3-era tools-agent
pattern. Their dependency manifests should be used in separate environments.

The manual YouTube agent executes tool requests itself and stops after ten
iterations. Data Analysis has a fifteen-iteration `AgentExecutor` and retains
chat history. Neither should be confused with a general production agent framework.

## Setup and Entry Points

Each project with a manifest provides detailed setup in its README. Commands
below are relative to the named **project directory** after setup.

| Project | Actual invocation | Configuration consumed |
|---|---|---|
| Math Assistant | From `src`: `python agent.py` | `OPENROUTER_API_KEY`, `BASE_URL`; fixed model ID |
| Data Analysis | `python llm.py` | `OPENROUTER_API_KEY`; optional `OPENROUTER_BASE_URL`/`BASE_URL`, `OPENROUTER_MODEL` |
| Tool-Calling Agent | From `src`: `python run_agent.py` | `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `WATSONX_PROJECT_NAME`, `WATSONX_URL`, `WATSONX_MODEL_ID` |
| NL-to-SQL | `python sql_agent.py --prompt "How many albums are there in the database?"` | `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`, `WATSONX_MODEL_ID`; `MYSQL_USERNAME`, `MYSQL_PASSWORD`, `MYSQLHOST`, `MYSQL_PORT`, `DB_NAME` |
| Visualization draft | No verified standalone command | No env reader; literal placeholder credentials |

`WATSONX_PROJECT_NAME` in the manual agent is required by startup validation,
although it is not sent as an inference parameter. Math's `llm.py` makes a live
greeting request on import. The SQL agent requires an accessible, populated
MySQL instance; copying `.env.example` alone does not create the database.

## Tests and Engineering Lessons

- Math has 37 tool-test functions in eight modules. Wikipedia is mocked, and these tests do not exercise live agent startup.
- Data Analysis has nine functions in one module. Its import/configuration check needs a nonempty `OPENROUTER_API_KEY`, which can be a dummy value for the offline suite. A guarded chat loop does not remove import-time key validation.
- No pass count, measured coverage percentage, or model/ML benchmark is claimed by this documentation update.
- Tool docstrings and schemas are part of the model's execution contract; registration should use intended tools rather than all public callables.
- Keep arithmetic and data probes deterministic where possible; validate generated reasoning against their actual outputs.
- Distinguish iteration-limit exits from final model answers and debug model, tools, state, and transport independently.
