"""Gradio front end for NourishBot.

The UI collects an image, an optional dietary restriction, and a workflow
choice, then delegates to the matching CrewAI crew.
"""

import logging
import tempfile
from pathlib import Path

import gradio as gr

from src.crew import NourishBotAnalysisCrew, NourishBotRecipeCrew

logger = logging.getLogger(__name__)
DEFAULT_PROGRESS = gr.Progress(track_tqdm=True)


def _as_dict(value):
    """Return a plain dict for dicts or Pydantic models."""
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return {}


def _extract_json_payload(final_output):
    """Extract the structured JSON payload from a CrewOutput dictionary.

    CrewAI 0.75's ``CrewOutput.to_dict()`` already returns the final task's JSON
    payload. This helper also handles nested shapes so the formatters remain
    robust if the output is wrapped differently.
    """
    final_output = _as_dict(final_output)
    if not final_output:
        return {}

    for key in ("json_dict", "pydantic"):
        payload = _as_dict(final_output.get(key))
        if payload:
            return payload

    for task_output in reversed(final_output.get("tasks_output") or []):
        task_output = _as_dict(task_output)
        payload = _as_dict(task_output.get("json_dict") or task_output.get("pydantic"))
        if payload:
            return payload

    return final_output


def format_recipe_output(final_output):
    """Format recipe suggestions as Markdown tables and sections.

    :param final_output: The output from the NourishBotRecipe workflow.
    :return: Formatted output as a Markdown string.
    """
    payload = _extract_json_payload(final_output)
    recipes = payload.get("recipes") or []

    output = "## 🍽 Recipe Ideas\n\n"
    if not recipes:
        return output + "No recipes could be generated."

    for index, recipe in enumerate(recipes, 1):
        recipe = _as_dict(recipe)
        output += f"### {index}. {recipe.get('title', 'Untitled recipe')}\n\n"

        output += "**Ingredients:**\n"
        output += "| Ingredient |\n"
        output += "|------------|\n"
        for ingredient in recipe.get("ingredients") or []:
            output += f"| {ingredient} |\n"
        output += "\n"

        output += f"**Instructions:**\n{recipe.get('instructions', 'N/A')}\n\n"
        output += (
            f"**Calorie Estimate:** {recipe.get('calorie_estimate', 'N/A')} kcal\n\n"
        )
        output += "---\n\n"

    return output


def format_analysis_output(final_output):
    """Format nutritional analysis as Markdown tables and sections.

    :param final_output: The JSON output from the NourishBotAnalysis workflow.
    :return: Formatted output as a Markdown string.
    """
    payload = _extract_json_payload(final_output)
    nutrients = _as_dict(payload.get("nutrients"))

    output = "## 🥗 Nutritional Analysis\n\n"

    if dish := payload.get("dish"):
        output += f"**Dish:** {dish}\n\n"
    if portion := payload.get("portion_size"):
        output += f"**Portion Size:** {portion}\n\n"
    if estimated_calories := payload.get("estimated_calories"):
        output += f"**Estimated Calories:** {estimated_calories} calories\n\n"
    if total_calories := payload.get("total_calories"):
        output += f"**Total Calories:** {total_calories} calories\n\n"

    output += "**Nutrient Breakdown:**\n\n"
    output += "| **Nutrient**       | **Amount** |\n"
    output += "|--------------------|------------|\n"

    for macro in ("protein", "carbohydrates", "fats"):
        if value := nutrients.get(macro):
            output += f"| **{macro.capitalize()}** | {value} |\n"

    vitamins = nutrients.get("vitamins") or []
    if vitamins:
        output += "\n**Vitamins:**\n\n"
        output += "| **Vitamin** | **%DV** |\n"
        output += "|-------------|--------|\n"
        for vitamin in vitamins:
            vitamin = _as_dict(vitamin)
            output += (
                f"| {vitamin.get('name', 'N/A')} "
                f"| {vitamin.get('percentage_dv', 'N/A')} |\n"
            )

    minerals = nutrients.get("minerals") or []
    if minerals:
        output += "\n**Minerals:**\n\n"
        output += "| **Mineral** | **Amount** |\n"
        output += "|-------------|-----------|\n"
        for mineral in minerals:
            mineral = _as_dict(mineral)
            output += (
                f"| {mineral.get('name', 'N/A')} "
                f"| {mineral.get('amount', 'N/A')} |\n"
            )

    if health_evaluation := payload.get("health_evaluation"):
        output += f"\n**Health Evaluation:**\n\n{health_evaluation}\n"

    return output


def analyze_food(
    image,
    dietary_restrictions,
    workflow_type,
    progress=DEFAULT_PROGRESS,
):
    """Run the selected NourishBot workflow for the Gradio interface.

    :param image: Uploaded image (PIL format).
    :param dietary_restrictions: Dietary restriction string (e.g., "vegan").
    :param workflow_type: Workflow type ("recipe" or "analysis").
    :return: Formatted Markdown result.
    """
    if image is None:
        return "### Please upload an image first."

    dietary_restrictions = (dietary_restrictions or "").strip()
    progress(0.0, desc="Preparing image")

    with tempfile.TemporaryDirectory() as temp_dir:
        image_path = Path(temp_dir) / "uploaded_image.jpg"
        image.convert("RGB").save(image_path, format="JPEG")

        inputs = {
            "uploaded_image": str(image_path),
            "dietary_restrictions": dietary_restrictions,
            "workflow_type": workflow_type,
        }

        if workflow_type == "recipe":
            crew_instance = NourishBotRecipeCrew()
        elif workflow_type == "analysis":
            crew_instance = NourishBotAnalysisCrew()
        else:
            return "Invalid workflow type. Choose 'recipe' or 'analysis'."

        try:
            progress(0.25, desc="Running NourishBot crew")
            final_output = crew_instance.crew().kickoff(inputs=inputs).to_dict()
        except Exception as exc:
            logger.exception("NourishBot workflow failed")
            return f"### Workflow error\n\n`{exc}`"

    progress(1.0, desc="Formatting result")
    if workflow_type == "recipe":
        return format_recipe_output(final_output)
    return format_analysis_output(final_output)


css = """
.title {
    font-size: 1.5em !important;
    text-align: center !important;
    color: #FFD700;
}

.text {
    text-align: center;
}
"""

js = """
function createGradioAnimation() {
    var container = document.createElement('div');
    container.id = 'gradio-animation';
    container.style.fontSize = '2em';
    container.style.fontWeight = 'bold';
    container.style.textAlign = 'center';
    container.style.marginBottom = '20px';
    container.style.color = '#eba93f';

    var text = 'Welcome to your AI NourishBot!';
    for (var i = 0; i < text.length; i++) {
        (function(i){
            setTimeout(function(){
                var letter = document.createElement('span');
                letter.style.opacity = '0';
                letter.style.transition = 'opacity 0.1s';
                letter.innerText = text[i];

                container.appendChild(letter);

                setTimeout(function() {
                    letter.style.opacity = '0.9';
                }, 50);
            }, i * 250);
        })(i);
    }

    var gradioContainer = document.querySelector('.gradio-container');
    gradioContainer.insertBefore(container, gradioContainer.firstChild);

    return 'Animation created';
}
"""

with gr.Blocks(theme=gr.themes.Citrus(), css=css, js=js) as demo:
    gr.Markdown("# How it works", elem_classes="title")
    gr.Markdown(
        "Upload an image of your fridge or pantry contents, enter any dietary "
        "restriction, select the 'recipe' workflow, and click 'Analyze' to get "
        "recipe ideas.",
        elem_classes="text",
    )
    gr.Markdown(
        "Upload an image of a complete dish, leave the dietary restriction "
        "blank, select the 'analysis' workflow, and click 'Analyze' to get "
        "nutritional insights.",
        elem_classes="text",
    )
    gr.Markdown(
        "You can also select one of the examples below to autofill the inputs, "
        "then click 'Analyze'.",
        elem_classes="text",
    )

    with gr.Row():
        with gr.Column(scale=1, min_width=400):
            gr.Markdown("## Inputs", elem_classes="title")
            image_input = gr.Image(type="pil", label="Upload Image")
            dietary_input = gr.Textbox(
                label="Dietary Restrictions (optional)",
                placeholder="e.g., vegan",
            )
            workflow_radio = gr.Radio(
                ["recipe", "analysis"],
                label="Workflow Type",
            )
            submit_btn = gr.Button("Analyze")

        with gr.Column(scale=2, min_width=600):
            gr.Examples(
                examples=[
                    ["examples/food-1.jpg", "vegan", "recipe"],
                    ["examples/food-2.jpg", "", "analysis"],
                    ["examples/food-3.jpg", "keto", "recipe"],
                    ["examples/food-4.jpg", "", "analysis"],
                ],
                inputs=[image_input, dietary_input, workflow_radio],
                label=(
                    "Try an example: select one to autofill the inputs, then "
                    "click Analyze"
                ),
            )
            gr.Markdown("## Results will appear here...", elem_classes="title")
            result_display = gr.Markdown(
                "<div style='border: 1px solid #ccc; "
                "padding: 1rem; text-align: center; "
                "color: #666;'>No results yet</div>",
                height=500,
            )

    submit_btn.click(
        fn=analyze_food,
        inputs=[image_input, dietary_input, workflow_radio],
        outputs=result_display,
    )

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=5000)
