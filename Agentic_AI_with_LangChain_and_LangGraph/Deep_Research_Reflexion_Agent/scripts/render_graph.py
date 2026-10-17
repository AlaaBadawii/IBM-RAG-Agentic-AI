"""Render the compiled reflection graph to ``graph_plot.png``.

This is a developer utility rather than part of the importable agent package.
It requires network access because ``draw_mermaid_png()`` calls a remote Mermaid
renderer.

Usage (from the repository root, with the package installed)::

    python scripts/render_graph.py
"""

from deep_research_agent.graph import app


def main() -> None:
    png_data = app.get_graph().draw_mermaid_png()

    with open("graph_plot.png", "wb") as f:
        f.write(png_data)

    print("Graph plot saved as graph_plot.png")


if __name__ == "__main__":
    main()
