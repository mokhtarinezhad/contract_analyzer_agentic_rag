"""
ESA Act Ingestor.

Indexes the Employment Standards Act of Ontario text into a persistent
ChromaDB collection (eao-act-reference). This collection is permanent —
it persists across all contract analyses and only needs to be (re)built
once via `python setup_act.py`.
"""

from __future__ import annotations

import time
from typing import List

from backend.compliance.eao_act_text import get_section_texts_for_ingestion
from backend.config import settings
from backend.ingestion.embedder import embed_texts
from backend.observability.logger import get_logger

logger = get_logger(__name__)


def ingest_eao_act(force: bool = False) -> int:
    """
    Embed and index all ESA sections into the permanent act reference collection.

    Args:
        force: If True, delete and re-index the collection even if it exists.

    Returns:
        Number of sections indexed.
    """
    import chromadb
    from pathlib import Path

    persist_path = str(Path(settings.chroma_persist_dir).resolve())
    Path(persist_path).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=persist_path)

    collection_name = settings.esa_act_collection_name

    if force:
        try:
            client.delete_collection(collection_name)
            logger.info("act_collection_deleted_for_reingest", collection=collection_name)
        except Exception:
            pass

    # Check if already indexed
    try:
        existing = client.get_collection(collection_name)
        count = existing.count()
        if count > 0 and not force:
            logger.info(
                "act_collection_already_indexed",
                collection=collection_name,
                num_sections=count,
            )
            return count
    except Exception:
        pass

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    sections = get_section_texts_for_ingestion()

    logger.info(
        "act_ingest_start",
        collection=collection_name,
        num_sections=len(sections),
    )

    t0 = time.perf_counter()

    texts_to_embed = [
        f"{s['part']} — {s['title']}\n\n{s['text']}"
        for s in sections
    ]
    embeddings = embed_texts(texts_to_embed, trace_id="act-ingest")

    ids = [s["chunk_id"] for s in sections]
    documents = texts_to_embed
    metadatas = [
        {
            "section_id": s["section_id"],
            "title": s["title"],
            "part": s["part"],
            "source": "eao_act",
        }
        for s in sections
    ]

    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    duration_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "act_ingest_complete",
        collection=collection_name,
        num_sections=len(sections),
        duration_ms=round(duration_ms, 2),
    )

    return len(sections)


def act_collection_exists() -> bool:
    """Return True if the ESA act collection has been indexed."""
    import chromadb
    from pathlib import Path

    persist_path = str(Path(settings.chroma_persist_dir).resolve())
    try:
        client = chromadb.PersistentClient(path=persist_path)
        col = client.get_collection(settings.esa_act_collection_name)
        return col.count() > 0
    except Exception:
        return False
