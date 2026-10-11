import argparse
import os

from dotenv import load_dotenv
from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.utilities.sql_database import SQLDatabase
from sqlalchemy import URL

from llm_agent import llm

load_dotenv()

required = [
    "MYSQL_USERNAME",
    "MYSQL_PASSWORD",
    "MYSQLHOST",
    "MYSQL_PORT",
    "DB_NAME",
]

missing = [key for key in required if not os.getenv(key)]
if missing:
    raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

mysql_username = os.environ["MYSQL_USERNAME"]
mysql_password = os.environ["MYSQL_PASSWORD"]
mysql_host = os.environ["MYSQLHOST"]
mysql_port = os.environ["MYSQL_PORT"]
database_name = os.environ["DB_NAME"]


# Build the MySQL connection URL safely.
mysql_uri = URL.create(
    drivername="mysql+mysqlconnector",
    username=mysql_username,
    password=mysql_password,
    host=mysql_host,
    port=int(mysql_port),
    database=database_name,
)

# Connect to MySQL.
db = SQLDatabase.from_uri(mysql_uri)

print("Available tables:", db.get_usable_table_names())

# Create the SQL agent.
agent_executor = create_sql_agent(
    llm=llm,
    db=db,
    agent_type="tool-calling",
    verbose=True,
    handle_parsing_errors=True,
)

# Use the prompt from command line argument
parser = argparse.ArgumentParser(description="Query the database with the SQL agent.")
parser.add_argument("--prompt", help="Natural-language database query")
args = parser.parse_args()

if args.prompt:
    result = agent_executor.invoke({"input": args.prompt})
    print(result.get("output", result))
else:
    print("Please provide a prompt using --prompt argument")
