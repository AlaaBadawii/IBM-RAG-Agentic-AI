from pathlib import Path


def print_workflow_info(workflow, app=None, output_path=None):
    """ " Prints information about a workflow.

    Args:
        workflow: The workflow object to print information about.
        app: Optional application context for additional information.
        output_path: Optional PNG path for graph rendering. Defaults to
            ``graph.png`` in this file's directory.
    """
    print("WORKFLOW INFORMATION")
    print("====================")
    print(f"Nodes: {workflow.nodes}")
    print(f"Edges: {workflow.edges}")

    try:
        finish_points = workflow.finish_points
        print(f"Finish points: {finish_points}")
    except AttributeError:
        try:
            print(f"Finish point: {workflow.finish_point}")
        except AttributeError:
            print("Finish points attribute not directly accessible")

    # Generate a graph plot when an application context is provided.
    if app is not None:
        output_path = Path(output_path) if output_path else Path(__file__).parent / "graph.png"
        app.get_graph().draw_png(str(output_path))
        print(f"Graph saved to: {output_path}")
