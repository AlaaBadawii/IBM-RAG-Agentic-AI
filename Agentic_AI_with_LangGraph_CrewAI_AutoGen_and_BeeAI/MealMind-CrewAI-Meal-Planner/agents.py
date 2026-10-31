from crewai import Agent

from llm import get_llm
from search_tool import search_tool

meal_planner = Agent(
    role="Meal Planner & Recipe Researcher",
    goal="Search for optimal recipes and create detailed meal plans",
    backstory="""A skilled meal planner who researches the best recipes online,
    consideering dietry needs, cooking skill levels, abudget constraints.
    """,
    tools = [search_tool],
    llm=get_llm(),
    verbose=False
)

shopping_organizer = Agent(
    role="Shooping Organizer",
    goal="Organizing grocery lists by store sections efficiently",
    backstory="An experienced shopper who knows how to organize lists for quick store trips and consider dietry restrictions",
    tools=[],
    llm=get_llm(),
    verbose=False
)

budget_adviser = Agent(
    role="Budget Adviser",
    goal="Provide cost estimates and money-saving tips",
    backstory="A budget-conscious shopper who helps families save money on groceries while respecting dietary needs.",
    tools=[],
    llm=get_llm(),
    verbose=False
)

summary_agent = Agent(
    role="Report Compiler",
    goal="Compile comprehensive meal planning reports from all teams outputs",
    backstory="A skilled coordinator who organizes information from multible specialists into comprehensive, easy-to-follow reports.",
    llm=get_llm(),
    verbose=False
)


