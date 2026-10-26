"""Section 1 schema/state validation tests (01-parallel-meal-planning)."""

import operator
import pytest
from pydantic import ValidationError


class TestDishSchema:
    def test_valid_dish_has_all_fields(self, s1):
        dish = s1.schemas.Dish(name="Spaghetti Bolognese", ingredients=["pasta", "beef"], location="Italian")
        assert dish.name == "Spaghetti Bolognese"
        assert dish.ingredients == ["pasta", "beef"]
        assert dish.location == "Italian"

    def test_missing_required_field_is_rejected(self, s1):
        with pytest.raises(ValidationError):
            s1.schemas.Dish(name="Only Name")

    def test_ingredients_must_be_a_list(self, s1):
        with pytest.raises(ValidationError):
            s1.schemas.Dish(name="Soup", ingredients="carrots", location="Italian")


class TestDishesSchema:
    def test_sections_nests_dish_objects(self, s1):
        dish = s1.schemas.Dish(name="Sushi", ingredients=["rice", "fish"], location="Japanese")
        dishes = s1.schemas.Dishes(sections=[dish])
        assert dishes.sections == [dish]

    def test_sections_is_required(self, s1):
        with pytest.raises(ValidationError):
            s1.schemas.Dishes()


class TestStateReducers:
    def test_completed_menu_uses_the_add_reducer(self, s1):
        annotations = s1.state.OrchestrationState.__annotations__
        assert annotations["completed_menu"].__metadata__[0] is operator.add

    def test_worker_state_completed_menu_uses_the_add_reducer(self, s1):
        annotations = s1.state.WorkerState.__annotations__
        assert annotations["completed_menu"].__metadata__[0] is operator.add

    def test_worker_state_holds_a_single_dish_section(self, s1):
        annotations = s1.state.WorkerState.__annotations__
        assert annotations["section"] is s1.schemas.Dish


class TestDummyState:
    def test_sample_state_matches_schema_shape(self, s1):
        from typing import get_type_hints

        dummy = s1.state.dummy_state
        hints = get_type_hints(s1.state.OrchestrationState)
        assert set(dummy) == set(hints)
