from crewai import Crew, Process

from agents import budget_adviser, meal_planner, shopping_organizer, summary_agent
from tasks import budget_task, meal_planning_task, shopping_task, summary_task
from yaml_leftover import yaml_leftover_manager, yaml_leftover_task

complete_grocery_crew = Crew(
    agents= [
        meal_planner,
        shopping_organizer,
        budget_adviser,
        yaml_leftover_manager,
        summary_agent
    ],
    tasks= [
        meal_planning_task,
        shopping_task,
        budget_task,
        yaml_leftover_task,
        summary_task
    ],
    process=Process.sequential,
    verbose=True
)

if __name__ == "__main__":
    complete_result = complete_grocery_crew.kickoff(
        inputs={
            "meal_name": "Chicken Stir Fry",
            "servings": 4,
            "budget": "$25",
            "dietary_restrictions": ["no nuts", "low sodium"],
            "cooking_skill": "beginner",
        }
    )

    print("✅ Complete meal planning with summary completed!")
    print("📋 Complete Results:")
    print(complete_result)