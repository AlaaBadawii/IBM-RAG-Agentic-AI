import os

from crewai_tools import SerperDevTool
from dotenv import load_dotenv

load_dotenv()

serper_api_key = os.getenv("SERPER_API_KEY")

if not serper_api_key:
    raise ValueError("SERPER_API_KEY environment variable is not set. Please set it in your .env file.")


search_tool = SerperDevTool()

if __name__ == "__main__":
    query = "Latest Breakthroughs in Agentic AI"
    results = search_tool.run(query=query)
    for result in results['organic']:
        print(f"\nResult: {result}\n")
    