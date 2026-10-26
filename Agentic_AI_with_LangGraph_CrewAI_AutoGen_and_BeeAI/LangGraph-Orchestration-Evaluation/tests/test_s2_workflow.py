"""Section 2 reflection-graph tests (structure + offline end-to-end runs)."""

import pytest


class FakeGradePipe:
    def __init__(self, grade_text):
        self.grade_text = grade_text
        self.calls = []

    def invoke(self, inputs):
        self.calls.append(inputs)
        return type("AIMessage", (), {"content": self.grade_text})()


class FakePlanPipe:
    def __init__(self, plan):
        self.plan = plan
        self.calls = []

    def invoke(self, inputs):
        self.calls.append(inputs)
        return type("AIMessage", (), {"content": self.plan})()


class FakeEvaluatorPipe:
    """Returns a scripted sequence of Feedback objects, one per call."""

    def __init__(self, schemas, grades):
        self.schemas = schemas
        self.sequence = list(grades)
        self.calls = []

    def invoke(self, inputs):
        self.calls.append(inputs)
        index = self.calls.index(inputs) if self.calls.count(inputs) > 1 else len(self.calls) - 1
        grade = self.sequence[min(index, len(self.sequence) - 1)]
        return self.schemas.Feedback(grade=grade, feedback=f"reasoning {index}")


def make_state(s2, **overrides):
    state = {
        "investment_plan": "",
        "investor_profile": "Age: 29\nRisk tolerance: High",
        "target_grade": "MISSING",
        "feedback": "",
        "grade": "MISSING",
        "n": 0,
    }
    state.update(overrides)
    return state


class TestGraphStructure:
    def test_compiled_graph_has_expected_nodes(self, s2):
        nodes = set(s2.graph.optimizer_workflow.get_graph().nodes)
        assert nodes == {
            "__start__", "__end__",
            "determine_target_grade", "investment_plan_generator", "evaluate_plan",
        }

    def test_compiled_graph_has_expected_edges(self, s2):
        edges = {(e.source, e.target) for e in s2.graph.optimizer_workflow.get_graph().edges}
        assert edges == {
            ("__start__", "determine_target_grade"),
            ("determine_target_grade", "investment_plan_generator"),
            ("investment_plan_generator", "evaluate_plan"),
            ("evaluate_plan", "__end__"),
            ("evaluate_plan", "investment_plan_generator"),
        }


class TestEndToEndOffline:
    def _install(self, s2, evaluator_grades, *, target="aggressive", final_plan="Revised plan"):
        fake_grade = FakeGradePipe(target)
        s2.determine_target_grade.grade_pipe = fake_grade
        s2.investment_plan_generator.cathie_wood_pipe = FakePlanPipe("Initial Cathie Wood plan")
        s2.investment_plan_generator.ray_dalio_pipe = FakePlanPipe(final_plan)
        s2.evaluate_plan.buffett_evaluator_pipe = FakeEvaluatorPipe(s2.schemas, evaluator_grades)

    def test_accepted_when_first_evaluation_matches_target(self, s2):
        self._install(s2, ["aggressive"])

        state = s2.graph.optimizer_workflow.invoke({"investor_profile": "Age: 29"})

        assert state["target_grade"] == "aggressive"
        assert state["grade"] == "aggressive"
        assert state["feedback"] == "reasoning 0"
        assert state["n"] == 1
        assert state["investment_plan"] == "Initial Cathie Wood plan"

    def test_rejection_loops_back_refining_until_grades_match(self, s2):
        self._install(s2, ["moderate", "aggressive"])

        state = s2.graph.optimizer_workflow.invoke({"investor_profile": "Age: 29"})

        assert state["grade"] == "aggressive"
        assert state["n"] == 2
        assert state["feedback"] == "reasoning 1"
        # the second generation ran with evaluator feedback present
        assert state["investment_plan"] == "Revised plan"

    def test_iteration_limit_stops_the_loop_gracefully(self, s2):
        # the evaluator never agrees with the target grade
        self._install(s2, ["moderate"] * 8)

        state = s2.graph.optimizer_workflow.invoke({"investor_profile": "Age: 29"})

        assert state["n"] == 6  # stops when the counter exceeds the limit of 5
        assert state["grade"] == "moderate"
        assert state["investment_plan"] == "Revised plan"
