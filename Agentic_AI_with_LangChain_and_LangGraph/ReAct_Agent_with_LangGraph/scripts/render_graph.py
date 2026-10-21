"""Render the compiled ReAct graph to ``graph_plot.png``.

This is a developer utility rather than part of the importable package. It
requires network access because ``draw_mermaid_png()`` calls a remote Mermaid
renderer.

Usage (from the repository root, with the package installed)::

    python scripts/render_graph.py
"""

from pathlib import Path

from react_agent.graph import graph

OUTPUT = Path(__file__).resolve().parents[1] / "graph_plot.png"


def main() -> None:
    png_data = graph.get_graph().draw_mermaid_png()
    OUTPUT.write_bytes(png_data)
    print(f"Graph plot saved as {OUTPUT}")


if __name__ == "__main__":
    main()
