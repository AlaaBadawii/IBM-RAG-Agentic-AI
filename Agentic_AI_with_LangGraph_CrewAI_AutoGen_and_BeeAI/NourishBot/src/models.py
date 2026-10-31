"""Pydantic schemas for NourishBot's structured CrewAI outputs."""

from pydantic import BaseModel, Field


class Recipe(BaseModel):
    """A single recipe suggestion."""

    title: str = Field(..., description="Recipe title")
    ingredients: list[str] = Field(
        ...,
        description="List of ingredients required for the recipe",
    )
    instructions: str = Field(..., description="Step-by-step cooking instructions")
    calorie_estimate: int = Field(..., description="Estimated calories per serving")


class RecipeSuggestionOutput(BaseModel):
    """The structured output of the recipe suggestion task."""

    recipes: list[Recipe] = Field(..., description="List of suggested recipes")


class VitaminInfo(BaseModel):
    """A vitamin and its percentage of the daily value."""

    name: str = Field(..., description="Name of the vitamin")
    percentage_dv: str = Field(..., description="Percentage of the Daily Value")


class MineralInfo(BaseModel):
    """A mineral and its amount."""

    name: str = Field(..., description="Name of the mineral")
    amount: str = Field(..., description="Amount and unit of the mineral")


class NutrientBreakdown(BaseModel):
    """Macronutrient and micronutrient details for a dish."""

    protein: str | None = Field(None, description="Protein content")
    carbohydrates: str | None = Field(None, description="Carbohydrates content")
    fats: str | None = Field(None, description="Fats content")
    vitamins: list[VitaminInfo] = Field(
        default_factory=list,
        description="List of vitamins and their %DV",
    )
    minerals: list[MineralInfo] = Field(
        default_factory=list,
        description="List of minerals and their amounts",
    )


class NutrientAnalysisOutput(BaseModel):
    """The structured output of the nutrient analysis task."""

    dish: str | None = Field(None, description="Identified dish")
    portion_size: str | None = Field(None, description="Portion size description")
    estimated_calories: int | None = Field(
        None,
        description="Estimated calories per portion",
    )
    nutrients: NutrientBreakdown = Field(
        default_factory=NutrientBreakdown,
        description="Detailed nutrient breakdown",
    )
    health_evaluation: str | None = Field(
        None,
        description="Health evaluation summary",
    )
