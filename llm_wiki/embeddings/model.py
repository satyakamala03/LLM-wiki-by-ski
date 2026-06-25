"""Nomic embedding model loader (Phase 4)."""

from __future__ import annotations

import os

# Must be set before sentence_transformers / transformers import (Keras 3 conflict).
os.environ["USE_TF"] = "0"
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")

from functools import lru_cache

EMBEDDING_MODEL_NAME = "nomic-ai/nomic-embed-text-v2-moe"
EMBEDDING_DIMENSIONS = 768
DOCUMENT_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL_NAME, trust_remote_code=True)


def embedding_dimensions() -> int:
    return EMBEDDING_DIMENSIONS


def embed_text(text: str) -> list[float]:
    """Embed document text for storage (768-dim)."""
    model = _get_model()
    prefixed = DOCUMENT_PREFIX + text.strip()
    vector = model.encode(prefixed, normalize_embeddings=True)
    return vector.tolist()


def embed_query(text: str) -> list[float]:
    """Embed a search query (768-dim)."""
    model = _get_model()
    prefixed = QUERY_PREFIX + text.strip()
    vector = model.encode(prefixed, normalize_embeddings=True)
    return vector.tolist()
