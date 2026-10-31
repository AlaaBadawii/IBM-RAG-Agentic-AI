"""CrewAI orchestration for NourishBot's two workflows.

``BaseNourishBotCrew`` declares the agents and tasks shared by both crews.
``NourishBotRecipeCrew`` and ``NourishBotAnalysisCrew`` compose those building
blocks into the two user-facing workflows.
"""

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from src.models import NutrientAnalysisOutput, RecipeSuggestionOutput
from src.tools import (
    DietaryFilterTool,
    ExtractIngredientsTool,
    FilterIngredientsTool,
    NutrientAnalysisTool,
)


@CrewBase
class BaseNourishBotCrew:
    """Shared agent and task definitions for the NourishBot crews.

    CrewAI resolves these paths relative to this file, so the YAML files live
    in ``src/config/``.
    """

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def ingredient_detection_agent(self) -> Agent:
        """Detect ingredients in a food image and normalize the raw list."""
        return Agent(
            config=self.agents_config["ingredient_detection_agent"],
            tools=[
                ExtractIngredientsTool.extract_ingredient,
                FilterIngredientsTool.filter_ingredients,
            ],
            allow_delegation=False,
            max_iter=5,
            verbose=True,
        )

    @agent
    def dietary_filtering_agent(self) -> Agent:
        """Remove ingredients that conflict with the user's dietary needs."""
        return Agent(
            config=self.agents_config["dietary_filtering_agent"],
            tools=[DietaryFilterTool.filter_based_on_restrictions],
            allow_delegation=True,
            max_iter=6,
            verbose=True,
        )

    @agent
    def nutrient_analysis_agent(self) -> Agent:
        """Estimate calories and break down nutrients for a plated dish."""
        return Agent(
            config=self.agents_config["nutrient_analysis_agent"],
            tools=[NutrientAnalysisTool.analyze_image],
            allow_delegation=False,
            max_iter=4,
            verbose=True,
        )

    @agent
    def recipe_suggestion_agent(self) -> Agent:
        """Turn a filtered ingredient list into structured recipe ideas."""
        return Agent(
            config=self.agents_config["recipe_suggestion_agent"],
            allow_delegation=False,
            verbose=True,
        )

    @task
    def ingredient_detection_task(self) -> Task:
        """First recipe step: identify and normalize ingredients."""
        task_config = self.tasks_config["ingredient_detection_task"]
        return Task(
            description=task_config["description"],
            expected_output=task_config["expected_output"],
            agent=self.ingredient_detection_agent(),
        )

    @task
    def dietary_filtering_task(self) -> Task:
        """Second recipe step: filter ingredients by dietary restriction."""
        task_config = self.tasks_config["dietary_filtering_task"]
        return Task(
            description=task_config["description"],
            expected_output=task_config["expected_output"],
            agent=self.dietary_filtering_agent(),
            context=[self.ingredient_detection_task()],
        )

    @task
    def nutrient_analysis_task(self) -> Task:
        """Analysis workflow: produce a structured nutrient report."""
        task_config = self.tasks_config["nutrient_analysis_task"]
        return Task(
            description=task_config["description"],
            expected_output=task_config["expected_output"],
            agent=self.nutrient_analysis_agent(),
            output_json=NutrientAnalysisOutput,
        )

    @task
    def recipe_suggestion_task(self) -> Task:
        """Final recipe step: generate recipes from the filtered ingredients."""
        task_config = self.tasks_config["recipe_suggestion_task"]
        return Task(
            description=task_config["description"],
            expected_output=task_config["expected_output"],
            agent=self.recipe_suggestion_agent(),
            context=[self.dietary_filtering_task()],
            output_json=RecipeSuggestionOutput,
        )


@CrewBase
class NourishBotRecipeCrew(BaseNourishBotCrew):
    """Recipe workflow: detect -> filter -> suggest recipes."""

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[
                self.ingredient_detection_agent(),
                self.dietary_filtering_agent(),
                self.recipe_suggestion_agent(),
            ],
            tasks=[
                self.ingredient_detection_task(),
                self.dietary_filtering_task(),
                self.recipe_suggestion_task(),
            ],
            process=Process.sequential,
            verbose=True,
        )


@CrewBase
class NourishBotAnalysisCrew(BaseNourishBotCrew):
    """Analysis workflow: estimate calories and nutrients for a dish."""

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.nutrient_analysis_agent()],
            tasks=[self.nutrient_analysis_task()],
            process=Process.sequential,
            verbose=True,
        )
