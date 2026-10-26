"""Tests for the shared utilities: llm.py and print_workflow_info.py."""

from pathlib import Path

import pytest
from pydantic import SecretStr

from conftest import RecordingChatWatsonx


@pytest.fixture
def llm_module(s1):
    """The shared llm.py module (its import triggers no model creation;
    get_llm is replaced by the harness but the original survives as
    ``_original_get_llm``)."""
    import llm
    return llm


WATSONX_VARS = ("WATSONX_PROJECT_ID", "WATSONX_URL", "WATSONX_MODEL_ID", "WATSONX_API_KEY")


def test_missing_env_vars_lists_every_unset_variable(llm_module, monkeypatch):
    for var in WATSONX_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("WATSONX_MODEL_ID", "test-model")
    monkeypatch.setenv("WATSONX_URL", "https://example.org")
    monkeypatch.setenv("WATSONX_API_KEY", "k")
    monkeypatch.setenv("WATSONX_PROJECT_ID", "p")

    assert llm_module.missing_env_vars() == []

    monkeypatch.delenv("WATSONX_URL")
    assert llm_module.missing_env_vars() == ["WATSONX_URL"]


def test_get_llm_refuses_to_run_without_credentials(llm_module, monkeypatch):
    for var in WATSONX_VARS:
        monkeypatch.delenv(var, raising=False)
    llm_module._original_get_llm.cache_clear()
    try:
        with pytest.raises(OSError) as excinfo:
            llm_module._original_get_llm()
    finally:
        llm_module._original_get_llm.cache_clear()
    message = str(excinfo.value)
    assert "WATSONX_URL" in message
    assert "WATSONX_PROJECT_ID" in message


def test_get_llm_builds_chatwatsonx_from_environment(llm_module, monkeypatch):
    """The real factory maps env vars to ChatWatsonx arguments exactly once."""

    monkeypatch.setenv("WATSONX_PROJECT_ID", "proj-123")
    monkeypatch.setenv("WATSONX_URL", "https://example.org/ml")
    monkeypatch.setenv("WATSONX_MODEL_ID", "test-model")
    monkeypatch.setenv("WATSONX_API_KEY", "key-123")

    monkeypatch.setattr(llm_module, "ChatWatsonx", RecordingChatWatsonx)
    llm_module._original_get_llm.cache_clear()
    try:
        first = llm_module._original_get_llm()
        second = llm_module._original_get_llm()
    finally:
        llm_module._original_get_llm.cache_clear()

    assert first is second, "get_llm must cache its client"
    assert first.project_id == "proj-123"
    assert first.model_id == "test-model"
    assert first.url == SecretStr("https://example.org/ml")
    assert first.apikey == SecretStr("key-123")


def test_test_llm_stub_forbids_model_calls(llm_module):
    """The harness stub raises on any invocation attempt instead of
    silently issuing a network request."""

    with pytest.raises(AssertionError):
        llm_module.get_llm().invoke("hello")


class FakeGraph:
    def __init__(self):
        self.images = []

    def draw_mermaid_png(self):
        return b"FAKE-PNG-BYTES"


class FakeApp:
    def __init__(self, graph):
        self.graph = graph

    def get_graph(self):
        return self.graph


class UnavailableAttribute:
    """Builder-like object whose optional attributes do not exist."""

    def __init__(self, nodes, edges):
        self.nodes = nodes
        self.edges = edges

    @property
    def finish_points(self):
        raise AttributeError("no finish_points")

    @property
    def finish_point(self):
        raise AttributeError("no finish_point")


def test_print_workflow_info_reports_nodes_edges_and_finish_fallback(capsys):
    from print_workflow_info import print_workflow_info

    builder = UnavailableAttribute(nodes={"a": "node-a"}, edges=[("a", "b")])
    print_workflow_info(builder)
    out = capsys.readouterr().out
    assert "WORKFLOW INFORMATION" in out
    assert "node-a" in out
    assert "('a', 'b')" in out  # the edges repr
    assert "Finish points attribute not directly accessible" in out


def test_print_workflow_info_writes_png_bytes_from_app(tmp_path, capsys):
    from print_workflow_info import print_workflow_info

    graph = FakeGraph()
    app = FakeApp(graph)
    builder = UnavailableAttribute(nodes={"a": "node-a"}, edges=[("a", "b")])
    target = tmp_path / "rendered.png"

    print_workflow_info(builder, app=app, output_path=str(target))

    assert target.read_bytes() == b"FAKE-PNG-BYTES"
    assert graph in [app.graph], "app.get_graph is the source of the PNG"
    assert "Graph saved to:" in capsys.readouterr().out


def test_print_workflow_info_default_output_is_its_own_directory(tmp_path, monkeypatch, capsys):
    """Without output_path the PNG lands next to print_workflow_info.py
    (the lab root) — which is why callers pass explicit paths."""
    from print_workflow_info import print_workflow_info

    builder = UnavailableAttribute(nodes={}, edges=[])
    default_target = Path(__file__).resolve().parents[1] / "graph.png"
    try:
        print_workflow_info(builder, app=FakeApp(FakeGraph()))
        assert default_target.read_bytes() == b"FAKE-PNG-BYTES"
    finally:
        default_target.unlink(missing_ok=True)
