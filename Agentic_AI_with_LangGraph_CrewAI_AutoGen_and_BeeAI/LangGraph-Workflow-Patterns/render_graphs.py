"""Render graph.png for every workflow from its actual compiled LangGraph graph.

Usage:
    python render_graphs.py

The PNG files are written next to each workflow's ``graph.py``. Rendering uses
Graphviz via ``pygraphviz`` and is fully local — no LLM or image-service requests
are made. Importing the workflows nonetheless requires the watsonx.ai environment
variables to be set (see .env.example), because the node modules construct their
LLM clients at import time; no model invocations occur, so there is no API cost.
"""

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

WORKFLOW_DIRS = [
    "01-sequential-agent-coordination",
    "02-intent-based-routing",
    "03-parallel-agent-execution",
]


def load_compiled_workflow(workflow_dir: Path):
    """Import a workflow's ``graph.py`` (folders are not valid Python packages).

    The workflow folder is placed on ``sys.path`` so that ``graph.py`` can import
    its sibling modules, then a uniquely named module spec loads it without
    colliding with identically named files in other workflow folders.
    """
    sys.path.insert(0, str(workflow_dir))
    try:
        spec_name = f"{workflow_dir.name.replace('-', '_')}_graph"
        spec = importlib.util.spec_from_file_location(spec_name, workflow_dir / "graph.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec_name] = module
        spec.loader.exec_module(module)
        return module.app
    finally:
        sys.path.remove(str(workflow_dir))


def render_all() -> None:
    for workflow_dir in WORKFLOW_DIRS:
        dir_path = PROJECT_ROOT / workflow_dir
        output_path = dir_path / "graph.png"

        try:
            app = load_compiled_workflow(dir_path)
            app.get_graph().draw_png(str(output_path))
        except ImportError as exc:
            print(f"[skip] {workflow_dir}: could not import ({exc})")
            continue
        except Exception as exc:
            if "pygraphviz" in str(exc):
                print(
                    "[error] Graph rendering requires pygraphviz: "
                    "install the Graphviz system package and run "
                    "`pip install pygraphviz`."
                )
                sys.exit(1)
            print(f"[error] {workflow_dir}: rendering failed ({exc})")
            continue

        print(f"[ok] {workflow_dir}: graph saved to {output_path}")


if __name__ == "__main__":
    render_all()
