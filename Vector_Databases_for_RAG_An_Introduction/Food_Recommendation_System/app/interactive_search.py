from shared_functions import *

# Global variable to store loaded food items
food_items = []
search_history = []


def main():
    """Main function for interactive CLI food recommendation system"""
    try:
        print("🍽️  Interactive Food Recommendation System")
        print("=" * 50)
        print("Loading food database...")

        # Load food data from file
        global food_items
        food_items = load_food_data("data/FoodDataSet.json")
        print(f"✅ Loaded {len(food_items)} food items successfully")

        # Create and populate search collection
        collection = create_similarity_search_collection(
            "interactive_food_search",
            {"description": "A collection for interactive food search"},
        )
        populate_similarty_collection(collection, food_items)

        # Start interactive chatbot
        interactive_food_chatbot(collection)

    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"❌ Error initializing system: {error}")


def interactive_food_chatbot(collection):
    """Interactive CLI chatbot for food recommendations"""
    print("\n" + "=" * 50)
    print("🤖 INTERACTIVE FOOD SEARCH CHATBOT")
    print("=" * 50)
    print("Commands:")
    print("  • Type any food name or description to search")
    print("  • 'help' - Show available commands")
    print("  • 'quit' or 'exit' - Exit the system")
    print("  • Ctrl+C - Emergency exit")
    print("-" * 50)

    while True:
        try:
            # Get user input
            user_input = input("\n🔍 Search for food: ").strip()

            # Handle empty input
            if not user_input:
                print("   Please enter a search term or 'help' for commands")
                continue

            # Handle exit commands
            if user_input.lower() in ["quit", "exit", "q"]:
                print("\n👋 Thank you for using the Food Recommendation System!")
                print("   Goodbye!")
                break

            # Handle help command
            elif user_input.lower() in ["help", "h"]:
                show_help_menu()

            # Handle search history command
            elif user_input.lower() in ["history", "h"]:
                show_search_history()

            # Handle food search
            else:
                search_history.append(user_input)
                handle_food_search(collection, user_input)

        except KeyboardInterrupt:
            print("\n\n👋 System interrupted. Goodbye!")
            break
        except (EOFError, ValueError, KeyError, TypeError) as e:
            print(f"❌ Error processing request: {e}")


def show_help_menu():
    """Display help information for users"""
    print("\n📖 HELP MENU")
    print("-" * 30)
    print("Search Examples:")
    print("  • 'chocolate dessert' - Find chocolate desserts")
    print("  • 'Italian food' - Find Italian cuisine")
    print("  • 'sweet treats' - Find sweet desserts")
    print("  • 'baked goods' - Find baked items")
    print("  • 'low calorie' - Find lower-calorie options")
    print("\nCommands:")
    print("  • 'help' - Show this help menu")
    print("  • 'quit' - Exit the system")
    print("  • 'history' - Show search history")


def handle_food_search(collection, query):
    """Handle food search queries and display results"""
    print(f"\n🔎 Searching for: '{query}'")
    print("   Please wait...")

    results = perform_similarity_search(collection, query)

    if not results:
        print("❌ No matching foods found.")
        print("💡 Try different keywords like:")
        print("   • Cuisine types: 'Italian', 'American'")
        print("   • Ingredients: 'chocolate', 'flour', 'cheese'")
        print("   • Descriptors: 'sweet', 'baked', 'dessert'")
        return

    print(f"   ✅ Found {len(results)} matching food items:")
    print("-" * 50)
    for idx, result in enumerate(results, start=1):
        i = idx
        percentage_score = result["similarity_score"] * 100

        print(f"\n{i}. 🍽️  {result['food_name']}")
        print(f"   📊 Match Score: {percentage_score:.1f}%")
        print(f"   🏷️  Cuisine: {result['cuisine_type']}")
        print(f"   🔥 Calories: {result['food_calories_per_serving']} per serving")
        print(f"   📝 Description: {result['food_description']}")

        # Add visual separator
        if i < len(results):
            print("   " + "-" * 50)

    print("-" * 50)

    # Provide suggestions for further exploration
    suggest_related_searches(results)


def suggest_related_searches(results):
    """Suggest related searches based on current results"""
    if not results:
        return

    # Extract cuisine types from results
    cuisines = {r["cuisine_type"] for r in results}

    print("\n💡 Related searches you might like:")
    for cuisine in list(cuisines)[:3]:  # Limit to 3 suggestions
        print(f"   • Try '{cuisine} dishes' for more {cuisine} options")

    # Suggest calorie-based searches
    avg_calories = sum([r["food_calories_per_serving"] for r in results]) / len(results)
    if avg_calories > 350:
        print("   • Try 'low calorie' for lighter options")
    else:
        print("   • Try 'hearty meal' for more substantial dishes")

def show_search_history():
    """Display the user's search history"""
    if not search_history:
        print("\n📜 No search history available.")
        return

    print("\n📜 Search History:")
    print("-" * 30)
    for idx, query in enumerate(search_history, start=1):
        print(f"{idx}. {query}")
    print("-" * 30)


if __name__ == "__main__":
    main()
