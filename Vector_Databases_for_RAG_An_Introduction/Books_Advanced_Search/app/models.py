from pydantic import BaseModel


class BookSearchResult(BaseModel):
    id: str
    title: str
    author: str
    genre: str
    year: int
    rating: float
    distance: float | None = None
