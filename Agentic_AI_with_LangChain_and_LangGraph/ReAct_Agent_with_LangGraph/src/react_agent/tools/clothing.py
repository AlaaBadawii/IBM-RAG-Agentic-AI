"""Keyword-based clothing recommendation tool.

Note: the tool's registered name is ``remommend_clothing`` (a misspelling kept
intentionally so the model-facing tool name does not change).
"""

from langchain.tools import tool


@tool
def remommend_clothing(weather: str) -> str:
    """Return a clothing recommendation for a weather description.

    The function scans the input for keywords or temperature indicators (for
    example ``"snow"``, ``"freezing"``, ``"rain"``, ``"hot"``, ``"85"``) and
    returns simple, practical advice.

    :param weather: A brief description of the weather (e.g. "Overcast, 64.9°F").
    :return: A string with clothing recommendations suitable for the weather.
    """

    weather = weather.lower()

    if "snow" in weather or "freezing" in weather:
        return "Wear a heavy coat, gloves, and boots."
    elif "rain" in weather or "wet" in weather:
        return "Bring a raincoat and waterproof shoes."
    elif "hot" in weather or "85" in weather:
        return "T-shirt, shorts, and sunscreen recommended."
    elif "cold" in weather or "50" in weather:
        return "Wear a warm jacket or sweater."
    else:
        return "A light jacket should be fine."
