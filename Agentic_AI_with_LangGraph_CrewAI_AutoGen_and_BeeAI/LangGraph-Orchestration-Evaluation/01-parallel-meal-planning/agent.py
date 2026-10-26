from graph import orchestrator_worker

state = orchestrator_worker.invoke({"meals": "Steak and eggs, tacos, and chili"})

print(state["final_meal_guide"])
