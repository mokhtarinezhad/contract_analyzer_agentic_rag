"""
ChromaDB vector store wrapper.

One collection per contract analysis run (keyed by contract_id).
Supports:
  - Adding chunks with metadata
  - Semantic search (cosine similarity via ChromaDB's built-in)
  - Keyword/section-targeted filtered search
  - Full collection cleanup

ChromaDB is run in-process (no server needed) with disk persistence.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional

from backend.config import settings
from backend.ingestion.chunker import DocumentChunk
from backend.observability.logger import get_logger

logger = get_logger(__name__)

_client = None  # singleton ChromaDB client


def _get_client():
    global _client
    if _client is None:
        import chromadb  # type: ignore
        persist_path = str(Path(settings.chroma_persist_dir).resolve())
        Path(persist_path).mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=persist_path)
        logger.info("chromadb_client_ready", persist_dir=persist_path)
    return _client


# ─────────────────────────────────────────────
# Collection management
# ─────────────────────────────────────────────

def get_or_create_collection(contract_id: str):
    """Return the ChromaDB collection for this contract. Creates if absent."""
    client = _get_client()
    collection_name = _safe_collection_name(contract_id)
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},  # cosine distance for similarity search
    )
    return collection


def delete_collection(contract_id: str) -> None:
    """Remove a contract's collection (cleanup after session)."""
    client = _get_client()
    name = _safe_collection_name(contract_id)
    try:
        client.delete_collection(name)
        logger.info("collection_deleted", contract_id=contract_id)
    except Exception as exc:
        logger.warning("collection_delete_failed", contract_id=contract_id, error=str(exc))


def _safe_collection_name(contract_id: str) -> str:
    """ChromaDB collection names must be 3–63 chars, alphanumeric + hyphens."""
    cleaned = "".join(c if c.isalnum() or c == "-" else "-" for c in contract_id)
    return f"contract-{cleaned}"[:63]


# ─────────────────────────────────────────────
# Index chunks
# ─────────────────────────────────────────────

def index_chunks(
    contract_id: str,
    chunks: List[DocumentChunk],
    embeddings: List[List[float]],
    trace_id: str = "unknown",
) -> None:
    """
    Add document chunks and their embeddings to the collection.

    Args:
        contract_id:  Unique ID for this contract analysis.
        chunks:       DocumentChunk list from the chunker.
        embeddings:   Corresponding embedding vectors (same order as chunks).
        trace_id:     Logging correlation.
    """
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"Chunks ({len(chunks)}) and embeddings ({len(embeddings)}) must have equal length"
        )

    t0 = time.perf_counter()
    collection = get_or_create_collection(contract_id)

    ids = [c.chunk_id for c in chunks]
    documents = [c.text for c in chunks]
    metadatas = [c.to_metadata_dict() for c in chunks]

    # ChromaDB upsert handles duplicate IDs gracefully
    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    duration_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "chunks_indexed",
        trace_id=trace_id,
        contract_id=contract_id,
        num_chunks=len(chunks),
        duration_ms=round(duration_ms, 2),
    )


# ─────────────────────────────────────────────
# Retrieval
# ─────────────────────────────────────────────

def semantic_search(
    contract_id: str,
    query_embedding: List[float],
    top_k: int = 5,
    section_filter: Optional[str] = None,
    trace_id: str = "unknown",
) -> List[dict]:
    """
    Retrieve top-k chunks by cosine similarity.

    Args:
        contract_id:     Which contract's collection to search.
        query_embedding: Embedded query vector.
        top_k:           Number of results to return.
        section_filter:  Optional section title substring to restrict results.
        trace_id:        Logging correlation.

    Returns:
        List of dicts with keys: chunk_id, text, section_title, distance, metadata.
    """
    t0 = time.perf_counter()
    collection = get_or_create_collection(contract_id)

    # ChromaDB `where` does not support substring/LIKE on string fields, so
    # section filtering runs as a post-filter on the over-fetched result set.
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k * 2, collection.count() or 1),
        include=["documents", "metadatas", "distances"],
    )

    hits = _parse_query_results(results)

    # Post-filter by section if requested
    if section_filter:
        filtered = [
            h for h in hits
            if section_filter.lower() in (h.get("section_title") or "").lower()
        ]
        hits = filtered if filtered else hits  # fallback to all if filter too restrictive

    hits = hits[:top_k]

    duration_ms = (time.perf_counter() - t0) * 1000
    logger.debug(
        "semantic_search_complete",
        trace_id=trace_id,
        query_len=len(query_embedding),
        top_k=top_k,
        returned=len(hits),
        section_filter=section_filter,
        duration_ms=round(duration_ms, 2),
    )

    return hits


def get_chunk_by_id(contract_id: str, chunk_id: str) -> Optional[dict]:
    """Fetch a specific chunk by ID (used by evaluator for hallucination check)."""
    collection = get_or_create_collection(contract_id)
    result = collection.get(ids=[chunk_id], include=["documents", "metadatas"])
    if result["documents"]:
        return {
            "chunk_id": chunk_id,
            "text": result["documents"][0],
            "metadata": result["metadatas"][0] if result["metadatas"] else {},
        }
    return None


def get_all_chunks(contract_id: str) -> List[dict]:
    """Return all chunks for a contract (used by chat feature)."""
    collection = get_or_create_collection(contract_id)
    count = collection.count()
    if count == 0:
        return []
    result = collection.get(include=["documents", "metadatas"])
    chunks = []
    for i, doc in enumerate(result["documents"]):
        chunks.append({
            "chunk_id": result["ids"][i],
            "text": doc,
            "metadata": result["metadatas"][i] if result["metadatas"] else {},
        })
    return chunks


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _parse_query_results(results: dict) -> List[dict]:
    """Convert ChromaDB query output into a flat list of dicts."""
    hits = []
    if not results or not results.get("documents"):
        return hits

    docs = results["documents"][0]
    metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
    dists = results["distances"][0] if results.get("distances") else [0.0] * len(docs)
    ids = results["ids"][0] if results.get("ids") else [""] * len(docs)

    for chunk_id, doc, meta, dist in zip(ids, docs, metas, dists):
        hits.append({
            "chunk_id": chunk_id,
            "text": doc,
            "section_title": (meta or {}).get("section_title", ""),
            "contains_table": (meta or {}).get("contains_table", False),
            "page_numbers": (meta or {}).get("page_numbers", ""),
            "distance": dist,
            "similarity": 1.0 - dist,  # convert distance to similarity
            "metadata": meta or {},
        })

    # Sort by similarity descending
    hits.sort(key=lambda x: x["similarity"], reverse=True)
    return hits
