"""Vectors, stored and compared, for near-duplicate detection only.

Near-duplicate detection needs to compare a candidate post against posts that
were already published, and the comparison has to survive the process that
published them. That is the whole job of this module:

* :func:`pack_embedding` / :func:`unpack_embedding` — the stored form. A vector
  goes into SQLite as bytes; nothing here decides *what* an embedding is.
* :func:`cosine_similarity` — one comparison, and an explicit ``None`` when a
  vector has no direction to compare.

This is deliberately not a vector store. ``PLAN.md`` §6.1 rules out indexing
publishing history into Chroma, and a second persistent index of any kind would
recreate the loop that decision prevents. A few dozen BLOBs and a dot product
answer the question exactly.
"""
import math
import struct
from typing import Sequence

__all__ = [
    "cosine_similarity",
    "pack_embedding",
    "unpack_embedding",
]

#: Little-endian float32, prefixed by nothing: the length is the byte count
#: divided by four. Fixed width and explicit byte order so a stored vector
#: reads back identically on any machine and in any process.
_FLOAT = struct.Struct("<f")
_FLOAT_SIZE = _FLOAT.size


def pack_embedding(vector: Sequence[float]) -> bytes:
    """Render a vector as the bytes stored on a publication.

    Raises:
        ValueError: the vector is empty, or holds a value that is not a finite
            number. A NaN or an infinity would be stored happily and then
            quietly poison every later comparison, so it is refused at the
            boundary instead.
    """
    values = [float(value) for value in vector]
    if not values:
        raise ValueError("refusing to store an empty embedding")
    for value in values:
        if not math.isfinite(value):
            raise ValueError(
                f"refusing to store a non-finite embedding value ({value!r})"
            )
    return b"".join(_FLOAT.pack(value) for value in values)


def unpack_embedding(blob: bytes | None) -> tuple[float, ...] | None:
    """Read a stored vector back, or ``None`` when there is nothing to read.

    ``None`` is a real answer and not an error: a publication recorded before
    near-duplicate detection existed, or while no embedder was configured, has
    no vector. Returning ``None`` lets the caller report that it could not
    compare rather than treating "no vector" as "not a duplicate".
    """
    if blob is None:
        return None
    if len(blob) % _FLOAT_SIZE:
        raise ValueError(
            f"stored embedding is {len(blob)} bytes, which is not a whole "
            f"number of {_FLOAT_SIZE}-byte floats"
        )
    return tuple(
        _FLOAT.unpack_from(blob, offset)[0]
        for offset in range(0, len(blob), _FLOAT_SIZE)
    )


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float | None:
    """Cosine similarity of two vectors, or ``None`` if it is undefined.

    Undefined means one of the vectors has zero magnitude — an empty bag of
    words, or a stored vector that was never filled in. ``None`` rather than
    ``0.0`` for the same reason :func:`unpack_embedding` returns ``None``:
    "these have no direction in common" and "these point in unrelated
    directions" are different facts, and only one of them is evidence that two
    posts are unalike.
    """
    if len(left) != len(right):
        return None
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for a, b in zip(left, right):
        dot += a * b
        left_norm += a * a
        right_norm += b * b
    if left_norm <= 0.0 or right_norm <= 0.0:
        return None
    return dot / (math.sqrt(left_norm) * math.sqrt(right_norm))
