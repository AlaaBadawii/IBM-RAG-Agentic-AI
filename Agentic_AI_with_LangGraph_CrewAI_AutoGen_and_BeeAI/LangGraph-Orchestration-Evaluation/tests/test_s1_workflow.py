"""Section 1 workflow behavior tests (orchestrator, workers, fan-out, graph)."""

import pytest
from langgraph.types import Send


def make_dish(s1, name):
    return s1.schemas.Dish(
        name=name,
        ingredients=["ingredient A", "ingredient B"],
        location="Italian" if name.startswith("Pasta") else "Japanese",
    )


class FakePlannerPipe:
    """Deterministic planner substitute returning a fixed Dishes payload."""

    def __init__(self, dishes):
        self.dishes = dishes
        self.calls = []

    def invoke(self, inputs):
        self.calls.append(inputs)
        return self.dishes


class FakePlannedSections:
    """Planner substitute with the dict shape the orchestrator tolerates."""

    def __init__(self, sections):
        self.sections = sections
        self.calls = []

    def invoke(self, inputs):
        self.calls.append(inputs)
        return {"sections": self.sections}


class FakeChefPipe:
    """Deterministic chef substitute: one canned answer per dish name."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def invoke(self, inputs):
        self.calls.append(inputs)
        return type("AIMessage", (), {"content": self.answers[inputs["name"]]})()


class TestOrchestrator:
    def test_returns_dish_sections_from_structured_object(self, s1):
        dishes = s1.schemas.Dishes(sections=[make_dish(s1, "Pasta Carbonara")])
        fake = FakePlannerPipe(dishes)
        s1.orchestrator.planner_pipe = fake
        result = s1.orchestrator.orchestrator({"meals": "Pasta Carbonara"})
        assert result == {"sections": dishes.sections}
        assert fake.calls == [{"meals": "Pasta Carbonara"}]

    def test_tolerates_dict_shaped_planner_output(self, s1):
        dish = make_dish(s1, "Pasta Carbonara")
        s1.orchestrator.planner_pipe = FakePlannedSections([dish])
        result = s1.orchestrator.orchestrator({"meals": "Pasta Carbonara"})
        assert result == {"sections": [dish]}


class TestAssignWorkers:
    def test_one_send_per_section_targets_chef_worker(self, s1):
        sections = [make_dish(s1, "Pasta Carbonara"), make_dish(s1, "Sushi")]
        sends = s1.assign_workers.assign_workers({"sections": sections})
        assert len(sends) == 2
        assert all(isinstance(send, Send) for send in sends)
        assert all(send.node == "chef_worker" for send in sends)
        assert [send.arg["section"] for send in sends] == sections

    def test_no_sections_dispatch_no_workers(self, s1):
        assert s1.assign_workers.assign_workers({"sections": []}) == []


class TestChefWorker:
    def test_returns_single_item_menu_list_and_passes_dish_fields(self, s1):
        fake = FakeChefPipe({"Sushi": "Recipe for Sushi"})
        s1.chef_worker.chef_pipe = fake
        result = s1.chef_worker.chef_worker({"section": make_dish(s1, "Sushi")})
        assert result == {"completed_menu": ["Recipe for Sushi"]}
        assert fake.calls == [
            {"name": "Sushi", "location": "Japanese", "ingredients": ["ingredient A", "ingredient B"]}
        ]


class TestSynthesizer:
    def test_joins_completed_menu_with_separator(self, s1):
        result = s1.synthesizer.synthesizer({"completed_menu": ["Part A", "Part B"]})
        assert result == {"final_meal_guide": "Part A\n\n---\n\nPart B"}


class TestGraphStructure:
    def test_compiled_graph_has_expected_nodes(self, s1):
        app = s1.graph.orchestrator_worker
        assert set(app.get_graph().nodes) == {"__start__", "__end__", "orchestrator", "chef_worker", "synthesizer"}

    def test_compiled_graph_has_expected_edges(self, s1):
        edges = {(e.source, e.target) for e in s1.graph.orchestrator_worker.get_graph().edges}
        assert edges == {
            ("__start__", "orchestrator"),
            ("orchestrator", "chef_worker"),
            ("chef_worker", "synthesizer"),
            ("synthesizer", "__end__"),
        }


class TestEndToEndOffline:
    """Full graph invocation with all model pipes replaced by fakes."""

    def test_parallel_workers_merge_results_and_synthesize(self, s1):
        pasta = make_dish(s1, "Pasta Carbonara")
        sushi = make_dish(s1, "Sushi")
        s1.orchestrator.planner_pipe = FakePlannerPipe(
            s1.schemas.Dishes(sections=[pasta, sushi])
        )
        s1.chef_worker.chef_pipe = FakeChefPipe(
            {"Pasta Carbonara": "Carbonara plan", "Sushi": "Sushi plan"}
        )

        state = s1.graph.orchestrator_worker.invoke({"meals": "Pasta Carbonara and Sushi"})

        assert state["meals"] == "Pasta Carbonara and Sushi"
        assert len(state["sections"]) == 2
        # The two parallel worker outputs are merged by the operator.add reducer;
        # order across workers is not deterministic, contents are.
        assert set(state["completed_menu"]) == {"Carbonara plan", "Sushi plan"}
        guide = state["final_meal_guide"]
        assert "Carbonara plan" in guide and "Sushi plan" in guide
        assert "\n\n---\n\n" in guide

    def test_planner_reports_no_meals_graph_stops_cleanly(self, s1):
        """With zero sections the conditional edges dispatch no workers;
        the run ends without synthesizer output."""

        s1.orchestrator.planner_pipe = FakePlannerPipe(s1.schemas.Dishes(sections=[]))
        s1.chef_worker.chef_pipe = FakeChefPipe({})

        state = s1.graph.orchestrator_worker.invoke({"meals": "nothing"})

        assert state["sections"] == []
        assert state["completed_menu"] == []
        assert "final_meal_guide" not in state

    def test_single_section_produces_full_chain(self, s1):
        dish = make_dish(s1, "Sushi")
        s1.orchestrator.planner_pipe = FakePlannerPipe(s1.schemas.Dishes(sections=[dish]))
        s1.chef_worker.chef_pipe = FakeChefPipe({"Sushi": "Sushi plan"})

        state = s1.graph.orchestrator_worker.invoke({"meals": "Sushi"})

        assert state["completed_menu"] == ["Sushi plan"]
        assert state["final_meal_guide"] == "Sushi plan"
