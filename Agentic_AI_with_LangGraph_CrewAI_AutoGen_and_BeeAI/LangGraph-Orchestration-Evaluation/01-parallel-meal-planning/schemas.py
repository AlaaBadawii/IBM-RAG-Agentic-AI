from pydantic import BaseModel, Field


class Dish(BaseModel):
    name: str = Field(
        description="Name of the dish (for example, Spaghetti Bolognese, Chicken Curry)."
    )
    ingredients: list[str] = Field(
        description="List of ingredients needed for this dish, separated by commas."
    )
    location: str = Field(
        description="The cuisine or cultural origin of the dish (for example, Italian, Indian, Mexican)."
    )

class Dishes(BaseModel):
    sections: list[Dish] = Field(
        description="A list of grocery sections, one for each dish, with ingredients."
    )
