import json
import logging
import re

import chromadb
import numpy as np
from chromadb.utils import embedding_functions

# Initialize ChromaDB client
client = chromadb.Client()

# Create logger
logger = logging.getLogger(__name__)


def load_food_data(file_path: str) -> list[dict]:
    """Load food data from JSON file"""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            food_data = json.load(file)

        # Ensure each item has required fields and normalize the structure
        for i, item in enumerate(food_data):
            # Normalize food_id to string
            if "food_id" not in item:
                item["food_id"] = str(i + 1)
            else:
                item["food_id"] = str(item["food_id"])

            # Ensure required fields exist
            if "food_ingredients" not in item:
                item["food_ingredients"] = []
            if "food_description" not in item:
                item["food_description"] = ""
            if "cuisine_type" not in item:
                item["cuisine_type"] = "Unknown"
            if "food_calories_per_serving" not in item:
                item["food_calories_per_serving"] = 0

            # Extract taste features from nested food_features if available
            if "food_features" in item and isinstance(item["food_features"], dict):
                taste_features = []
                for value in item["food_features"].values():
                    if value:
                        taste_features.append(str(value))
                item["taste_profile"] = ", ".join(taste_features)
            else:
                item["taste_profile"] = ""

        print(f"Successfully loaded {len(food_data)} food items from {file_path}")
        return food_data

    except (
        FileNotFoundError,
        OSError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ) as e:
        print(f"Error loading food data: {e}")
        return []


def create_similarity_search_collection(
    collection_name: str, collection_metadata: dict | None = None
):
    """Create chromadb collection with sentence transformers embeddings"""
    try:
        client.delete_collection(collection_name)
    except chromadb.errors.NotFoundError:
        logger.debug(
            "Collection %s did not exist before creation", collection_name
        )

    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    return client.create_collection(
        name=collection_name,
        metadata=collection_metadata,
        embedding_function=sentence_transformer_ef,
    )


def populate_similarty_collection(collection, food_items: list[dict]):
    """Populate collection with food data and generate embeddings"""
    documents = []
    metadatas = []
    ids = []

    user_ids = set()

    for i, food in enumerate(food_items):
        text = f"Name: {food['food_name']}."
        text += f" Description: {food.get('food_description', '')}."
        text += f" Ingredients: {', '.join(food.get('food_ingredients', []))}."
        text += f" Cuisine: {food.get('cuisine_type', 'Unknown')}."
        text += f"Cooking method: {food.get('cooking_method', '')}."

        taste_profile = food.get("taste_profile", "")
        if taste_profile:
            text += f" Taste profile: {taste_profile}."

        health_benefits = food.get("health_benefits", "")
        if health_benefits:
            text += f" Health benefits: {health_benefits}."

        if "food_nutritional_factors" in food:
            nutrition = food["food_nutritional_factors"]

            if isinstance(nutrition, dict):
                nutrition_info = ", ".join(
                    f"{key}: {value}" for key, value in nutrition.items()
                )
                text += f" Nutritional information: {nutrition_info}."
            else:
                logger.warning(
                    "Food item with ID %s has invalid nutritional information format.",
                    food.get("food_id", "Unknown"),
                )

        base_id = str(food.get("food_id", i))
        unique_id = base_id
        counter = 1
        while unique_id in user_ids:
            unique_id = f"{base_id}_{counter}"
            counter += 1
        user_ids.add(unique_id)

        ids.append(unique_id)
        documents.append(text)
        metadatas.append(
            {
                "name": food["food_name"],
                "description": food["food_description"],
                "ingredients": food["food_ingredients"],
                "cuisine_type": food["cuisine_type"],
                "calories": food["food_calories_per_serving"],
                "cooking_method": food["cooking_method"],
                "taste_profile": food["taste_profile"],
                "health_benefits": food.get("health_benefits", ""),
            }
        )

    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids,
    )

    print(f"Successfully populated collection with {len(food_items)} food items.")



def perform_similarity_search(collection, query: str, n_results: int = 5) -> list[dict]:
    """Perform similarity search and return formatted results"""
    try:
        results = collection.query(query_texts=[query], n_results=n_results)

        if not results or not results["ids"] or len(results["ids"][0]) == 0:
            return []

        formatted_results = []
        for i in range(len(results["ids"][0])):
            # Calculate similarity score (1 - distance)
            similarity_score = 1 - results["distances"][0][i]

            result = {
                "food_id": results["ids"][0][i],
                "food_name": results["metadatas"][0][i]["name"],
                "food_description": results["metadatas"][0][i]["description"],
                "cuisine_type": results["metadatas"][0][i]["cuisine_type"],
                "food_calories_per_serving": results["metadatas"][0][i]["calories"],
                "similarity_score": similarity_score,
                "distance": results["distances"][0][i],
            }
            formatted_results.append(result)

        return formatted_results

    except (KeyError, TypeError, ValueError):
        logger.exception("Error in similarity search")
        return []

def perform_similarity_search_with_metadata(
        collection, query: str, cuisine_filter: str | None = None,
        max_calories: int | None = None, n_results: int = 5) -> list[dict]:
    """Perform similarity search and return results with metadata"""
    where_clause = None

    filter_conditions = []
    if cuisine_filter or max_calories is not None:
        if cuisine_filter:
            filter_conditions.append({"cuisine_type": cuisine_filter})
        if max_calories is not None:
            filter_conditions.append({"food_calories_per_serving": {"$lte": max_calories}})

    if len(filter_conditions) == 1:
        where_clause = filter_conditions[0]
    elif len(filter_conditions) > 1:
        where_clause = {"$and": filter_conditions}


    try:
        results = collection.query(query_texts=[query], where=where_clause, n_results=n_results)

        if not results or not results["ids"] or len(results["ids"][0]) == 0:
            return []

        formatted_results = []
        for i in range(len(results["ids"][0])):
            # Calculate similarity score (1 - distance)
            similarity_score = 1 - results["distances"][0][i]

            result = {
                "food_id": results["ids"][0][i],
                "food_name": results["metadatas"][0][i]["name"],
                "food_description": results["metadatas"][0][i]["description"],
                "cuisine_type": results["metadatas"][0][i]["cuisine_type"],
                "food_calories_per_serving": results["metadatas"][0][i]["calories"],
                "similarity_score": similarity_score,
                "distance": results["distances"][0][i],
            }
            formatted_results.append(result)

        return formatted_results

    except (KeyError, TypeError, ValueError):
        logger.exception("Error in similarity search: %s")
        return []
