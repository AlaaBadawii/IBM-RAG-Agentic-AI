from graph import app

png_data = app.get_graph().draw_mermaid_png()

with open("graph_plot.png", "wb") as f:
    f.write(png_data)

print("Graph plot saved as graph_plot.png")
