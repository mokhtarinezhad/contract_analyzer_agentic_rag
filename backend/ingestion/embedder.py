"""
Embedding wrapper using sentence-transformers (local, free).

Encapsulates model loading (done once at startup), batch embedding,
and cosine similarity utilities used by the retriever.
"""

from __future__ import annotations

import time
from typing import List

import numpy as np

from backend.config import settings
from backend.observability.logger import get_logger

logger = get_logger(__name__)

_model = None  # lazy-loaded singleton


def _get_model():
    global _model
    if _model is None:
        logger.info("embedding_model_loading", model=settings.embedding_model)
        from sentence_transformers import SentenceTransformer  # type: ignore
        _model = SentenceTransformer(settings.embedding_model)
        logger.info("embedding_model_ready", model=settings.embedding_model)
    return _model


def embed_texts(
    texts: List[str],
    trace_id: str = "unknown",
    batch_size: int = 64,
    show_progress: bool = False,
) -> List[List[float]]:
    """
    Embed a list of strings and return a list of float vectors.

    Args:
        texts:          Strings to embed.
        trace_id:       For logging correlation.
        batch_size:     Batch size for the model (tune for VRAM/RAM).
        show_progress:  Show tqdm progress bar.

    Returns:
        List of embedding vectors (len == len(texts)).
    """
    if not texts:
        return []

    t0 = time.perf_counter()
    model = _get_model()

    embeddings: np.ndarray = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        convert_to_numpy=True,
        normalize_embeddings=True,  # unit-norm enables dot-product == cosine similarity
    )

    duration_ms = (time.perf_counter() - t0) * 1000

    logger.info(
        "embedding_complete",
        trace_id=trace_id,
        num_texts=len(texts),
        embedding_dim=embeddings.shape[1],
        duration_ms=round(duration_ms, 2),
    )

    return embeddings.tolist()


def embed_query(query: str) -> List[float]:
    """Embed a single query string (used at retrieval time)."""
    model = _get_model()
    vec: np.ndarray = model.encode(
        [query],
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return vec[0].tolist()


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Cosine similarity between two unit-norm vectors (dot product)."""
    a = np.array(vec_a)
    b = np.array(vec_b)
    return float(np.dot(a, b))
