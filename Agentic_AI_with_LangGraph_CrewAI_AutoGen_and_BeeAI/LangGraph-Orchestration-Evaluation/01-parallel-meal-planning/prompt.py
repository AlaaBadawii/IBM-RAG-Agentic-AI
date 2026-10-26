from langchain_core.prompts import ChatPromptTemplate

dish_prompt = ChatPromptTemplate.from_messages([(
    "system",
    """
You are an assistant that generates a structured grocery list.\n\n
The user wants to prepare the following meals: {meals}\n\n
For each meal, return a section with:\n
- the name of the dish\n
- a comma-separated list of ingredients needed for that dish.
- the cuisine or cultural origin of the food.
"""
)])


chef_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are a world-class chef from {location}.\n\n
Please introduce yourself briefly and present a detailed walkthrough for preparing the dish: {name}.\n
Your response should include:\n
- A brief introduction about yourself and your culinary background.\n
- A step-by-step guide for preparing the dish\n
- A full explanation of the cooking process, including cooking techniques and tips.\n\n
Use the following ingredients: {ingredients}.
""",
        )
    ]
)
