"""Tests for the evaluation dataset."""
import json
import os


def test_evaluation_cases_exist():
    """Verify evaluation cases.json exists and has valid structure."""
    path = os.path.join(os.path.dirname(__file__), "..", "evaluation", "cases.json")
    path = os.path.normpath(path)
    assert os.path.exists(path)
    with open(path) as f:
        data = json.load(f)
    assert "cases" in data
    assert len(data["cases"]) > 0


def test_evaluation_cases_have_required_fields():
    """Verify each case has required fields."""
    path = os.path.join(os.path.dirname(__file__), "..", "evaluation", "cases.json")
    path = os.path.normpath(path)
    with open(path) as f:
        data = json.load(f)
    for case in data["cases"]:
        assert "image" in case
        assert "task" in case
        assert "question" in case
        assert "expected_behavior" in case


def test_evaluation_tasks_are_valid():
    """Verify tasks are from the known set."""
    path = os.path.join(os.path.dirname(__file__), "..", "evaluation", "cases.json")
    path = os.path.normpath(path)
    with open(path) as f:
        data = json.load(f)
    valid_tasks = {"captioning", "counting", "assessment", "extraction", "question"}
    for case in data["cases"]:
        assert case["task"] in valid_tasks
