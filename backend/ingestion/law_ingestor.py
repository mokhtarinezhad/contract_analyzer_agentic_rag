"""
Law PDF ingestor — parses, chunks, embeds, and indexes a law reference PDF
into its own persistent ChromaDB collection.

The collection name is derived as `law-{sanitized_law_id}` so it never
conflicts with contract collections (prefix "contract-").
"""

from __future__ import annotations

import time
from typing import Optional

from backend.ingestion.chunker import chunk_elements
from backend.ingestion.embedder import embed_texts
from backend.ingestion.pdf_parser import parse_pdf
from backend.observability.logger import get_logger, new_trace_id
from backend.observability.metrics_store import (
    create_law_reference,
    update_law_reference,
)
from backend.rag.vector_store import (
    get_or_create_law_collection,
    safe_law_collection_name,
)

logger = get_logger(__name__)


def ingest_law_pdf(
    pdf_path: str,
    law_id: str,
    display_name: str,
    filename: str,
    trace_id: Optional[str] = None,
) -> dict:
    """
    Full ingestion pipeline for a law reference PDF.

    Args:
        pdf_path:     Absolute path to the uploaded PDF.
        law_id:       Stable identifier (e.g. "ontario-law-2026").
        display_name: Human-readable label shown in the UI selector.
        filename:     Original upload filename.
        trace_id:     Logging correlation ID.

    Returns:
        {"law_id": str, "collection_name": str, "chunk_count": int, "duration_ms": float}
    """
    if trace_id is None:
        trace_id = new_trace_id()

    collection_name = safe_law_collection_name(law_id)
    t0 = time.perf_counter()

    create_law_reference(
        law_id=law_id,
        display_name=display_name,
        collection_name=collection_name,
        filename=filename,
        status="indexing",
    )

    logger.info("law_ingest_start", trace_id=trace_id, law_id=law_id,
                collection_name=collection_name)

    # Parse
    elements = parse_pdf(pdf_path, trace_id=trace_id)

    # Chunk
    chunks = chunk_elements(elements, trace_id=trace_id)
    if not chunks:
        update_law_reference(law_id=law_id, status="failed")
        raise ValueError(f"Law PDF '{filename}' produced no text chunks")

    # Embed
    texts = [c.embedding_text if c.embedding_text else c.text for c in chunks]
    embeddings = embed_texts(texts, trace_id=trace_id)

    # Index into the law collection (upsert — safe to re-run)
    collection = get_or_create_law_collection(law_id)
    ids = [c.chunk_id for c in chunks]
    documents = [c.text for c in chunks]
    metadatas = [c.to_metadata_dict() for c in chunks]
    collection.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)

    chunk_count = len(chunks)
    duration_ms = (time.perf_counter() - t0) * 1000

    update_law_reference(law_id=law_id, status="ready", chunk_count=chunk_count)

    logger.info("law_ingest_complete", trace_id=trace_id, law_id=law_id,
                chunk_count=chunk_count, duration_ms=round(duration_ms, 2))

    return {
        "law_id": law_id,
        "collection_name": collection_name,
        "chunk_count": chunk_count,
        "duration_ms": round(duration_ms, 2),
    }
