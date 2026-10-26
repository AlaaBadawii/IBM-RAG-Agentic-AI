from typing import TypedDict, Annotated
import operator
from schemas import Dish


class OrchestrationState(TypedDict):
    meals: str
    sections: list[Dish]
    completed_menu: Annotated[list[str], operator.add]
    final_meal_guide: str


class WorkerState(TypedDict):
    section: Dish
    completed_menu: Annotated[
        list, operator.add
    ]  # list with addition operators between elements


dummy_state: OrchestrationState = {
    "meals": "Spaghetti Bolognese and Chicken Stir Fry",
    "sections": [],
    "completed_menu": [],
    "final_meal_guide": "",
}
