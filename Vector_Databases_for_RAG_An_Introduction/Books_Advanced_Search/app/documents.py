"""
Documents for the Books Advanced Search application.
"""


def build_book_document(book: dict) -> str:
    return f"""
The {book["title"]} by {book["author"]}.\n
{book["description"]}.\n
Themes: {book["themes"]}.\n
Setting: {book["setting"]}.\n
Genre: {book["genre"]}.\n
Published in {book["year"]}
With a {book["rating"]} rating.\n
"""


def build_book_documents(books: list[dict]) -> list[str]:
    book_documents = []
    for book in books:
        try:
            book_documents.append(build_book_document(book))
        except KeyError as e:
            print(f"Error at converting books to documents: {e}")

    return book_documents


def build_metadatas(books: list[dict]) -> list[dict]:
    metadatas = []

    for book in books:
        metadatas.append(
            {
                "title": book["title"],
                "author": book["author"],
                "genre": book["genre"],
                "year": int(book["year"]),
                "rating": float(book["rating"]),
                "pages": int(book["pages"])
            }
        )

    return metadatas
