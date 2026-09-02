import chromadb
from chromadb.utils import embedding_functions

from data.employee import EMPLOYEES_DATA

# Define an Embedding function
ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

# Create an instance of Chromadb to establish conn with chromadb
client = chromadb.Client()

# Define a name of the collection where data will be stored
collection_name = "employee_collection"

# main function
def main():
    try:
        # creating a collection usingg chromadb client instance
        collection = client.create_collection(
            name=collection_name,
            metadata={"desription": "A collection for storing employee data"},
            # configure the collection with cosine destance and embedding function
            configuration={
                "hnsw":{"space":"cosine"},
                "embedding_function":ef
            }
        )

        print(f"🎉 Collection created Successfully: {collection.name}")

        employees = EMPLOYEES_DATA

        # create comprehensive text documents for each employee
        employee_documents = []
        for employee in employees:
            document = f"{employee['role']} with {employee['experience']} years of experience in {employee['department']}. "
            document += f"Skills: {employee['skills']}. Located in {employee['location']}. "
            document += f"Employment type: {employee['employment_type']}."
            employee_documents.append(document)

        # adding data to collection
        collection.add(
            ids=[employee["id"] for employee in employees],
            documents=employee_documents,
            metadatas=[
                {
                    "name": employee["name"],
                    "department": employee["department"],
                    "role": employee["role"],
                    "experience": employee["experience"],
                    "location": employee["location"],
                    "employment_type": employee["employment_type"],
                } for employee in employees
            ],
        )

        # retrive all items from the specified collection
        all_items = collection.get()

        print("Collection contents:")
        print(f"Number of documents: {len(all_items['documents']) if all_items['documents'] else 0}")

        def perform_advanced_search(collection, all_items):
            try:
                print("==== Similarty search Example ====")
                # Example 1: Searching for Python developer
                print("\n1. Searching for Python developers:")
                query_text = "Python developer with web development experience"

                results = collection.query(
                    query_texts= [query_text],
                    n_results=3 
                )

                print(f"Query: {query_text}")
                for i, (doc_id, document, distance) in enumerate(zip(
                    results['ids'][0], results['documents'][0], results['distances'][0]
                )):
                    metadata = results['metadatas'][0][i]
                    print(f"  {i+1}. {metadata['name']} ({doc_id}) - Distance: {distance:.4f}")
                    print(f"     Role: {metadata['role']}, Department: {metadata['department']}")
                    print(f"     Document: {document[:100]}...")

                # Example 2: Search for Leadership roles
                print("\n2. Searching for leadership and management rules")
                query_text = "team leader manager with experience"
                results = collection.query(
                    query_texts= [query_text],
                    n_results= 3
                )

                print(f"Querying: {query_text}")

                for i, (doc_id, document, distance) in enumerate(zip(
                    results['ids'][0], results['documents'][0], results['distances'][0]
                )):
                    metadata = results['metadatas'][0][i]
                    print(f"   {i+1}. {metadata['name']} ({doc_id}) - Distance: {distance:.4f}")
                    print(f"     Role: {metadata['role']}, Experience: {metadata['experience']} years")


                # Example 3. Metadata filtering
                print("=== Metadata Filtering Examples ===")
                print("\n3. Finding all Engeeniring employees:")
                results = collection.get(
                    where={"department": "Engineering"}
                )

                print(f"Found {len(results['ids'])} Engineering Employee")
                for i, doc_id in enumerate(results['ids']):
                    metadata = results['metadatas'][i]
                    print(
                        f"  - {metadata['name']}: {metadata['role']} ({metadata['experience']} years)"
                    )

                print("\n4. Finding employees with 10+ years experience:")
                results = collection.get(
                    where={"experience": {"$gte": 10}}
                )
                print(f"Found {len(results['ids'])} senior employees:")
                for i, doc_id in enumerate(results['ids']):
                    metadata = results['metadatas'][i]
                    print(f"  - {metadata['name']}: {metadata['role']} ({metadata['experience']} years)")


                # Example 3: Filter by location
                print("\n5. Finding employees in California:")
                results = collection.get(
                    where={"location": {"$in": ["San Francisco", "Los Angeles"]}}
                )

                print(f"Found {len(results['ids'])} employees in California:")
                for i, doc_id in enumerate(results['ids']):
                    metadata = results['metadatas'][i]
                    print(f"  - {metadata['name']}: {metadata['location']}")


                print("\n=== Combined Search: Similarity + Metadata Filtering ===")

                print('\n6. Finding senior Python developer in major tech cities:')
                query_text = "Senior Python developer full stack"

                results = collection.query(
                    query_texts= [query_text],
                    n_results= 5,
                    where= {
                        "$and": [
                            {"experience": {"$gte": 8}},
                            {"location": {"$in": ["San Francisco", "New York", "Seattle"]}}
                        ]
                    }
                )

                print(f"Query: '{query_text}' with filters (8+ years, major tech cities)")
                print(f"Found {len(results['ids'][0])} matching employees:")
                for i, (doc_id, document, distance) in enumerate(zip(
                    results['ids'][0], results['documents'][0], results['distances'][0]
                )):
                    metadata = results['metadatas'][0][i]
                    print(f"  {i+1}. {metadata['name']} ({doc_id}) - Distance: {distance:.4f}")
                    print(f"     {metadata['role']} in {metadata['location']} ({metadata['experience']} years)")
                    print(f"     Document snippet: {document[:80]}...")

                if not results or not results["ids"] or len(results["ids"][0]) == 0:
                    # Log a message if no similar documents are found for the query term
                    print(f'No documents found similar to "{query_text}"')
                    return

                # Log the header for the top 3 similar documents based on the query term
                print(f'Top 3 similar documents to "{query_text}":')
                # Loop through the top 3 results and log the document details
                for i in range(min(3, len(results["ids"][0]))):
                    # Extract the document ID and similarity score from the results
                    doc_id = results["ids"][0][i]
                    score = results["distances"][0][i]
                    # Retrieve the document text corresponding to the current ID from the results
                    text = results["documents"][0][i]
                    # Check if the text is available; if not, log 'Text not available'
                    if not text:
                        print(
                            f' - ID: {doc_id}, Text: "Text not available", Score: {score:.4f}'
                        )
                    else:
                        print(f' - ID: {doc_id}, Text: "{text}", Score: {score:.4f}')
            except (ValueError, RuntimeError) as e:
                print(f"Error during advanced search: {e}")

        perform_advanced_search(collection, all_items)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
