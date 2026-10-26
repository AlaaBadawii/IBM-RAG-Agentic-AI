"""Section 2 component tests (schemas, target grade, generator, evaluator, router)."""

import pytest
from pydantic import ValidationError


class FakeStringPipe:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def invoke(self, inputs):
        self.calls.append(inputs)
        return type("AIMessage", (), {"content": self.content})()


class TestSchemas:
    def test_feedback_valid_object_round_trips(self, s2):
        feedback = s2.schemas.Feedback(grade="moderate", feedback="Balanced")
        assert feedback.model_dump() == {"grade": "moderate", "feedback": "Balanced"}

    def test_feedback_rejects_unknown_grade(self, s2):
        with pytest.raises(ValidationError):
            s2.schemas.Feedback(grade="wild risk", feedback="n/a")

    def test_grades_literal_documented_values(self, s2):
        import typing

        values = set(typing.get_args(s2.schemas.grades))
        assert {
            "ultra-conservative", "conservative", "moderate", "aggressive", "high risk",
        }.issubset(values)

    def test_reflection_state_fields(self, s2):
        assert set(s2.state.ReflectionState.__annotations__) == {
            "investment_plan", "investor_profile", "target_grade", "feedback", "grade", "n",
        }


class TestDetermineTargetGrade:
    def test_lowercases_plain_text_response(self, s2):
        fake = FakeStringPipe("AGGRESSIVE")
        s2.determine_target_grade.grade_pipe = fake
        result = s2.determine_target_grade.determine_target_grade({"investor_profile": "Age: 29"})
        assert result == {"target_grade": "aggressive"}

    def test_flattens_list_shaped_content(self, s2):
        content = [{"text": "Aggressive"}, " grade"]
        fake = FakeStringPipe(content)
        s2.determine_target_grade.grade_pipe = fake
        result = s2.determine_target_grade.determine_target_grade({"investor_profile": "Age: 29"})
        assert result == {"target_grade": "aggressive grade"}


class TestInvestmentPlanGenerator:
    def test_initial_generation_uses_cathie_wood_persona(self, s2):
        class FakePipe:
            def __init__(self, content):
                self.content = content
                self.calls = []

            def invoke(self, inputs):
                self.calls.append(inputs)
                return type("AIMessage", (), {"content": self.content})()

        cathie = FakePipe("Cathie Wood plan")
        ray = FakePipe("Ray Dalio plan")
        s2.investment_plan_generator.cathie_wood_pipe = cathie
        s2.investment_plan_generator.ray_dalio_pipe = ray

        state = {"investor_profile": "Age: 29", "feedback": "", "grade": "MISSING"}
        result = s2.investment_plan_generator.investment_plan_generator(state)

        assert result == {"investment_plan": "Cathie Wood plan"}
        assert cathie.calls == [{"investor_profile": "Age: 29"}]
        assert ray.calls == []

    def test_refinement_uses_ray_dalio_persona_with_evaluator_context(self, s2):
        class FakePipe:
            def __init__(self, content):
                self.content = content
                self.calls = []

            def invoke(self, inputs):
                self.calls.append(inputs)
                return type("AIMessage", (), {"content": self.content})()

        cathie = FakePipe("Cathie Wood plan")
        ray = FakePipe("Ray Dalio revised plan")
        s2.investment_plan_generator.cathie_wood_pipe = cathie
        s2.investment_plan_generator.ray_dalio_pipe = ray

        state = {
            "investor_profile": "Age: 29",
            "feedback": "too aggressive",
            "grade": "high risk",
        }
        result = s2.investment_plan_generator.investment_plan_generator(state)

        assert result == {"investment_plan": "Ray Dalio revised plan"}
        assert ray.calls == [
            {"investor_profile": "Age: 29", "grade": "high risk", "feedback": "too aggressive"}
        ]
        assert cathie.calls == []


class TestEvaluatePlan:
    def test_increments_iteration_counter_and_returns_feedback(self, s2):
        feedback = s2.schemas.Feedback(grade="aggressive", feedback="Matches the profile")
        recorded = {}

        class FakeEvaluator:
            def invoke(self, inputs):
                recorded.update(inputs)
                return feedback

        s2.evaluate_plan.buffett_evaluator_pipe = FakeEvaluator()

        state = {
            "investment_plan": "plan text",
            "investor_profile": "profile text",
            "target_grade": "aggressive",
            "n": 2,
        }
        result = s2.evaluate_plan.evaluate_plan(state)

        assert result == {"grade": "aggressive", "feedback": "Matches the profile", "n": 3}
        assert recorded == {
            "investment_plan": "plan text",
            "investor_profile": "profile text",
            "target_grade": "aggressive",
        }

    def test_accepts_dict_shaped_evaluator_response(self, s2):
        class FakeEvaluator:
            def invoke(self, inputs):
                return {"grade": "moderate", "feedback": "ok"}

        s2.evaluate_plan.buffett_evaluator_pipe = FakeEvaluator()
        result = s2.evaluate_plan.evaluate_plan(
            {"investment_plan": "p", "investor_profile": "i", "target_grade": "aggressive"}
        )
        assert result == {"grade": "moderate", "feedback": "ok", "n": 1}


class TestRouteInvestment:
    @pytest.mark.parametrize(
        ("state", "kwargs", "expected"),
        [
            ({"grade": "aggressive", "target_grade": "aggressive", "n": 3}, {}, "Accepted"),
            ({"grade": "moderate", "target_grade": "aggressive", "n": 1}, {}, "Rejected + Feedback"),
            ({"grade": "moderate", "target_grade": "aggressive", "n": 5}, {}, "Rejected + Feedback"),
            ({"grade": "moderate", "target_grade": "aggressive", "n": 6}, {}, "Accepted"),
            ({"grade": "moderate", "target_grade": "MISSING", "n": 1}, {}, "Rejected + Feedback"),
            (
                {"grade": "moderate", "target_grade": "MISSING", "n": 2},
                {"iteration_limit": 1},
                "Accepted",
            ),
        ],
    )
    def test_routing_table(self, s2, state, kwargs, expected, capsys):
        assert s2.route_investment.route_investment(state, **kwargs) == expected

    def test_missing_grade_defaults_do_not_match(self, s2):
        result = s2.route_investment.route_investment({"grade": "MISSING", "target_grade": "moderate", "n": 0})
        assert result == "Rejected + Feedback"
