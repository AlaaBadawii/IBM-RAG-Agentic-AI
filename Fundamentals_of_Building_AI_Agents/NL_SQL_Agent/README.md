# NL_SQL_Agent (Natural Language SQL Agent)

## Project Overview

This is a small learning project from my IBM AI Agents learning journey. Its purpose was to get hands-on practice building a natural-language SQL agent that answers questions about a MySQL database.

It is not a production system. The value of the project was implementing and debugging the integration between an LLM, an agent framework, and a real database.

## Features

- Initializes a Watsonx LLM and validates the required Watsonx environment variables.
- Connects to MySQL with SQLAlchemy and LangChain's `SQLDatabase`, then prints the available tables.
- Creates a LangChain tool-calling SQL agent that converts a natural-language question into SQL, runs it, and returns an answer.
- Provides a simple command-line interface with `--prompt` and prints the agent's final answer.
- Reports missing environment variables by name without exposing secret values.

## How It Works

The user passes a question with `--prompt`. The SQL agent in `sql_agent.py` sends the question and database tools to the Watsonx LLM from `llm_agent.py`. The LLM chooses a tool, queries the MySQL database, and the agent returns the result as a natural-language answer.

## Tech Stack

- Python
- LangChain (`langchain-community` SQL agent and `SQLDatabase`)
- IBM watsonx.ai via `langchain-ibm` (`ChatWatsonx`)
- SQLAlchemy with `mysql-connector-python` for the MySQL connection
- MySQL with the Chinook sample database
- `python-dotenv` and `argparse` for configuration and CLI input

## Project Structure

- `llm_agent.py` — Loads `.env`, validates the Watsonx variables, and creates the shared `llm` object. It does not connect to the database.
- `sql_agent.py` — Imports `llm`, validates the MySQL variables, builds the connection URL, connects to the database, creates the SQL agent, and runs the `--prompt` question.
- `.env` — Holds Watsonx and MySQL configuration. It is not committed as shared code and its values are never printed.
- `.env.example` — Safe template listing the required variable names with placeholder values. Copy it to `.env` and fill in your own values.
- `requirements.txt` — Pinned direct dependencies matching the verified local environment.
- `chinook-mysql.sql` — SQL dump that creates and populates the Chinook sample database used for questions.

## Setup and Configuration

1. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install the dependencies from the pinned requirements file:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and fill in your own values for:

   ```text
   WATSONX_API_KEY
   WATSONX_PROJECT_ID
   WATSONX_URL
   WATSONX_MODEL_ID
   MYSQL_USERNAME
   MYSQL_PASSWORD
   MYSQLHOST
   MYSQL_PORT
   DB_NAME
   ```

4. Prepare the database by loading `chinook-mysql.sql` into your local MySQL instance with your MySQL client, then set `DB_NAME` to that database.

## Usage

Ask a natural-language question with `--prompt`:

```bash
python sql_agent.py --prompt "How many albums are there in the database?"
```

The script prints the available tables, runs the agent with verbose output, and prints the final answer. A verified run of the example above returned `347` albums from the `Album` table.

## Lessons Learned

- **Version Compatibility:** Different LangChain versions expose different imports and agent APIs, so checking installed versions and compatible documentation is important. Verifying the local `create_sql_agent` signature avoided guessing the correct input format.
- **LLM–Agent Integration:** A model generating text is not enough; its interface and output must be compatible with the agent framework's expectations. The agent needed tool-calling support and a dict input such as `{"input": ...}`.
- **Layer-by-Layer Debugging:** Troubleshooting the model, database connection, schema, and agent separately makes integration problems easier to isolate. Each layer was checked before testing the full question-answering flow.
- **Database Integration:** Inspecting actual table names and constructing database URLs safely are important when connecting an application to MySQL. This project used `sqlalchemy.URL.create()` and `SQLDatabase.from_uri()` plus a table listing.
- **Configuration Management:** Environment variables help separate credentials and configuration from application code. Missing-variable checks report names only, keeping keys and passwords out of logs.

## Limitations and Future Improvements

Implemented behavior is limited to single `--prompt` questions against the configured database with basic missing-variable checks. Not implemented, but relevant next steps would be automated tests, stronger error handling around database and model failures, and SQL safety controls such as read-only permissions and query limits.
