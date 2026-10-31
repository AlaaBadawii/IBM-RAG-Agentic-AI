from crewai import Task

from agents import budget_adviser, meal_planner, shopping_organizer, summary_agent
from schemas import GroceryShoppingPlan, MealPlan
from yaml_leftover import yaml_leftover_task

meal_planning_task = Task(
    description=(
        """Search for the best '{meal_name}' recipe for {seervings} people within a {budget} budget.
        Consider dietry restrictions: {dietary_restrictions} and cooking skill level: {cooking_skill}.
        Find recipes that match the skill level and provide complete ingredient lists with quatities."""
    ),
    expected_output="A detailed meal plan with researched ingrediets, quantities, and cooking instructions appropriate for the skill level.",
    agent=meal_planner,
    output_pydantic=MealPlan,
    output_file="meals.json"
)

shopping_task = Task(
    description=(
        "Organize the ingredients from the '{meal_name}' meal plan into a grocery shopping list. "
        "Group items by store sections and estimate quantities for {servings} people. "
        "Consider dietary restrictions: {dietary_restrictions} and cooking skill: {cooking_skill}. "
        "Stay within budget: {budget}."
    ),
    expected_output="An organized shopping list grouped by store sections with quantities and prices.",
    agent=shopping_organizer,
    context=[meal_planning_task],
    output_pydantic=GroceryShoppingPlan,
    output_file="Shopping_list.json"
)

budget_task = Task(
    description=(
        "Analyze the shopping plan for '{meal_name}' serving {servings} people. "
        "Ensure total cost stays within {budget}. Consider dietary restrictions: {dietary_restrictions}. "
        "Provide practical money-saving tips and alternative ingredients if needed to meet budget."
    ),
    expected_output="A complete shopping guide with detailed prices, budget analysis, and money-saving tips.",
    agent=budget_adviser,
    context=[meal_planning_task, shopping_task],
    output_file="shopping_guide.md",
)

summary_task = Task(
    description=(
        "Compile a comprehensive meal planning report that includes:\n"
        "1. The complete recipe and cooking instructions from the meal planner\n"
        "2. The organized shopping list with prices from the shopping organizer\n"
        "3. The budget analysis and money-saving tips from the budget advisor\n"
        "4. The leftover management suggestions from the waste reduction specialist\n"
        "Format this as a complete, user-friendly meal planning guide."
    ),
    expected_output="A comprehensive meal planning guide that combines all team outputs into one cohesive report.",
    agent=summary_agent,
    context=[meal_planning_task, shopping_task, budget_task, yaml_leftover_task]
)
