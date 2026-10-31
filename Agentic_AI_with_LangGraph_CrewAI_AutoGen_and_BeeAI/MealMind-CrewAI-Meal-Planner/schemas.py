from typing import Literal

from pydantic import BaseModel, Field


class GroceryItem(BaseModel):
    """Individual grocery item."""

    name: str = Field(description="Name of the grocery Item")
    quantity: str = Field(
        description="Quantity needed (for example, '2 lbs', '1 gallon')"
    )
    estimated_price: str = Field(description="Estimated price (for example, '$3-5')")
    category: str = Field(description="Store section (for example, 'Produce', 'Dairy')")

class MealPlan(BaseModel):
    """Simple meal plan"""

    meal_name: str = Field(description="Name of the meal")
    difficulty_level: Literal["Easy", "Medium", "Hard"] = Field(
        description="'Easy', 'Medium', 'Hard'"
    )
    servings: int = Field(description="Number of people it serves")
    researched_ingredients: list[str] = Field(
        description="Ingredients found through research"
    )

class ShoppingCategory(BaseModel):
    """Store section with items"""
    section_name: str = Field(
        description="Store section (for example, 'Produce', 'Dairy')"
    )
    items: list[GroceryItem] = Field(description="Items in this section")
    estimated_total: str = Field(description="Estimated cost for this section")

class GroceryShoppingPlan(BaseModel):
    """Complete simplified shopping plan"""

    total_budget: str = Field(description="Total planned budget")
    meal_plans: list[MealPlan] = Field(description="Planned meals")
    shopping_sections: list[ShoppingCategory] = Field(
        description="Organized by store sections"
    )
    shopping_tips: list[str] = Field(description="Money-saving and efficiency tips")

