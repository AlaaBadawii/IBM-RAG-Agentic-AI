""" pytest configuration and offline test harness.

Design goals (see ../README.md, "Running the tests"):

- The suite runs completely offline: it must work with or without the
  user's real ``.env`` and must never call watsonx.ai.
- Model-dependent components are substituted at the narrowest sensible
  seam: ``llm.get_llm``. Every project module builds its pipes through
  that single factory, so replacing it (before any project module is
  executed) removes the only path to the network. Any accidental model
  call raises ``AssertionError``.
- Both projects define same-named modules (``state``, ``schemas``,
  ``prompt``, ``pipe``, ...). Sessions load each project from its own
  directory via ``importlib`` under bare module names, in dependency
  order, so inter-module imports resolve to the right project's files
  while both projects remain importable in one test session.
"""

import importlib.util
import sys
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.runnables import Runnable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

S1_DIR = ROOT / "01-parallel-meal-planning"
S2_DIR = ROOT / "02-investment-advisor-reflection"

# Modules of each project, in dependency order (a module may import
# modules earlier in its list).
S1_MODULES = (
    "schemas", "state", "prompt", "pipe",
    "orchestrator", "chef_worker", "assign_workers", "synthesizer", "graph",
)
S2_MODULES = (
    "schemas", "state", "prompt", "pipe",
    "determine_target_grade", "investment_plan_generator",
    "evaluate_plan", "route_investment", "graph",
)


class DummyLLM(Runnable):
    """Stand-in for ``ChatWatsonx`` that forbids any model invocation."""

    last_instance: "DummyLLM | None" = None

    def __init__(self):
        DummyLLM.last_instance = self

    def invoke(self, input, config=None, **kwargs):
        raise AssertionError("Tests must not call the model")

    def with_structured_output(self, schema=None, **kwargs):
        return self

    def bind_tools(self, tools, **kwargs):
        return self


class RecordingChatWatsonx:
    """Records constructor kwargs instead of building a real client."""

    def __init__(self, project_id=None, url=None, model_id=None, apikey=None, **kwargs):
        self.project_id = project_id
        self.url = url
        self.model_id = model_id
        self.apikey = apikey


@lru_cache(maxsize=2)
def _load_project(directory: Path, module_names: tuple[str, ...]) -> SimpleNamespace:
    """Execute every module of one project and return a namespace of them."""
    import llm

    if not hasattr(llm, "_original_get_llm"):
        # keep the full lru-cached wrapper (with its cache_clear) so tests
        # can exercise and reset real caching behavior
        llm._original_get_llm = llm.get_llm
        llm._original_get_llm.cache_clear()
    llm.get_llm = lambda: DummyLLM()

    ns = SimpleNamespace()
    for name in module_names:
        path = directory / f"{name}.py"
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        # Register before exec so same-named modules from the other
        # project do not shadow this project's imports.
        sys.modules[name] = module
        spec.loader.exec_module(module)
        setattr(ns, name, module)
    return ns


@pytest.fixture(scope="session")
def s1():
    """All modules of 01-parallel-meal-planning, loaded offline."""
    return _load_project(S1_DIR, S1_MODULES)


@pytest.fixture(scope="session")
def s2():
    """All modules of 02-investment-advisor-reflection, loaded offline."""
    return _load_project(S2_DIR, S2_MODULES)
