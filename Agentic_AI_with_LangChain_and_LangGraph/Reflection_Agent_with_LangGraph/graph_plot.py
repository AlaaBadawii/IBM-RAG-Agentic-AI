from graph import workflow

png_data = workflow.get_graph().draw_mermaid_png()

with open("reflection_graph.png", "wb") as f:
    f.write(png_data)

print("Graph saved to reflection_graph.png")
