"""CrewAI tools used by NourishBot agents.

Each tool wraps either a watsonx.ai vision model or a lightweight text model.
The tools are intentionally small and single-purpose so agents can choose when
to invoke them.
"""

import base64
import os

import requests
from ibm_watsonx_ai.foundation_models import ModelInference
from langchain.tools import tool

from src.watsonx import (
    TEXT_MODEL_ID,
    VISION_MODEL_ID,
    get_watsonx_credentials,
    get_watsonx_project_id,
)

NUTRIENT_ANALYSIS_PROMPT = """
    You are an expert nutritionist. Your task is to analyze the food items displayed in the image and provide a detailed nutritional assessment using the following format:
1. **Identification**: List each identified food item clearly, one per line.
2. **Portion Size & Calorie Estimation**: For each identified food item, specify the portion size and provide an estimated number of calories. Use bullet points with the following structure:
- **[Food Item]**: [Portion Size], [Number of Calories] calories
Example:
*   **Salmon**: 6 ounces, 210 calories
*   **Asparagus**: 3 spears, 25 calories
3. **Total Calories**: Provide the total number of calories for all food items.
Example:
Total Calories: [Number of Calories]
4. **Nutrient Breakdown**: Include a breakdown of key nutrients such as **Protein**, **Carbohydrates**, **Fats**, **Vitamins**, and **Minerals**. Use bullet points, and for each nutrient provide details about the contribution of each food item.
Example:
*   **Protein**: Salmon (35g), Asparagus (3g), Tomatoes (1g) = [Total Protein]
5. **Health Evaluation**: Evaluate the healthiness of the meal in one paragraph.
6. **Disclaimer**: Include the following exact text as a disclaimer:
The nutritional information and calorie estimates provided are approximate and are based on general food data.
Actual values may vary depending on factors such as portion size, specific ingredients, preparation methods, and individual variations.
For precise dietary advice or medical guidance, consult a qualified nutritionist or healthcare provider.
Format your response exactly like the template above to ensure consistency.
"""


def _load_image_as_base64(image_input: str) -> str:
    """Read a local image path or remote URL and return base64-encoded bytes."""
    if image_input.startswith("http"):
        response = requests.get(image_input, timeout=30)
        response.raise_for_status()
        image_bytes = response.content
    else:
        if not os.path.isfile(image_input):
            raise FileNotFoundError(f"No file found at path: {image_input}")
        with open(image_input, "rb") as file:
            image_bytes = file.read()

    return base64.b64encode(image_bytes).decode("utf-8")


def _build_vision_model() -> ModelInference:
    """Create a watsonx.ai vision model client."""
    return ModelInference(
        model_id=VISION_MODEL_ID,
        credentials=get_watsonx_credentials(),
        project_id=get_watsonx_project_id(),
        params={"max_tokens": 300},
    )


def _run_vision_prompt(prompt: str, image_input: str) -> str:
    """Send a text prompt plus an image to the vision model."""
    encoded_image = _load_image_as_base64(image_input)
    model = _build_vision_model()

    response = model.chat(
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/jpeg;base64," + encoded_image
                        },
                    },
                ],
            }
        ]
    )

    return response["choices"][0]["message"]["content"]


class ExtractIngredientsTool:
    """Extract a raw ingredient list from a food image."""

    @tool("Extract ingredients")
    def extract_ingredient(image_input: str) -> str:
        """Extract ingredients from a food item image.

        :param image_input: The image file path (local) or URL (remote).
        :return: A list of ingredients extracted from the image.
        """
        return _run_vision_prompt(
            "Extract ingredients from the food item image",
            image_input,
        )


class FilterIngredientsTool:
    """Normalize a raw ingredient string into a clean list."""

    @tool("Filter ingredients")
    def filter_ingredients(raw_ingredients: str) -> list[str]:
        """Process raw ingredient data and remove noise.

        :param raw_ingredients: Raw ingredients as a string.
        :return: A list of cleaned and relevant ingredients.
        """
        return [
            ingredient.strip().lower()
            for ingredient in raw_ingredients.split(",")
            if ingredient.strip()
        ]


class DietaryFilterTool:
    """Filter ingredients against a user-provided dietary restriction."""

    @tool("Filter based on dietary restrictions")
    def filter_based_on_restrictions(
        ingredients: list[str],
        dietary_restrictions: str | None = None,
    ) -> list[str]:
        """Use a text model to remove ingredients that violate a restriction.

        :param ingredients: List of ingredients.
        :param dietary_restrictions: Dietary restriction (e.g., vegan, keto).
            Defaults to None, in which case the list is returned unchanged.
        :return: Filtered list of ingredients that comply with the restriction.
        """
        if not dietary_restrictions:
            return ingredients

        model = ModelInference(
            model_id=TEXT_MODEL_ID,
            credentials=get_watsonx_credentials(),
            project_id=get_watsonx_project_id(),
            params={"max_tokens": 150},
        )

        prompt = f"""
        You are an AI nutritionist specialized in dietary restrictions.
        Given the following list of ingredients: {', '.join(ingredients)},
        and the dietary restriction: {dietary_restrictions},
        remove any ingredient that does not comply with this restriction.
        Return only the compliant ingredients as a comma-separated list with no additional commentary.
        """

        response = model.chat(
            messages=[
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}],
                }
            ]
        )

        filtered = response["choices"][0]["message"]["content"].strip().lower()
        return [item.strip() for item in filtered.split(",") if item.strip()]


class NutrientAnalysisTool:
    """Estimate calories and nutrients from a plated-dish image."""

    @tool("Analyze nutritional values and calories of the dish from uploaded image")
    def analyze_image(image_input: str) -> str:
        """Return a nutrient breakdown and calorie estimate for an image.

        :param image_input: The image file path (local) or URL (remote).
        :return: A string with nutrient breakdown and calorie information.
        """
        return _run_vision_prompt(NUTRIENT_ANALYSIS_PROMPT, image_input)
