"""
Hybrid retriever: semantic search + section-targeted boost.

For each sub-criterion query, we:
1. Embed the query.
2. Run semantic search (cosine similarity).
3. Optionally boost chunks from predicted sections.
4. Return merged, deduplicated top-k results.

This two-pass approach catches evidence that is semantically distant
from the query wording but structurally predictable (e.g., a table
cell in Exhibit G3A that says "admin 14+ chars" won't score highly
on "password length requirements" alone).
"""

from __future__ import annotations

import time
from typing import List, Optional

from backend.config import settings
from backend.ingestion.embedder import embed_query
from backend.observability.logger import get_logger
from backend.rag.vector_store import semantic_search

logger = get_logger(__name__)


def retrieve_for_query(
    contract_id: str,
    query: str,
    top_k: int = 5,
    likely_sections: Optional[List[str]] = None,
    trace_id: str = "unknown",
) -> List[dict]:
    """
    Retrieve the most relevant chunks for a single sub-criterion query.

    Args:
        contract_id:     Which contract's ChromaDB collection to search.
        query:           Natural-language sub-criterion query string.
        top_k:           Final number of chunks to return.
        likely_sections: Section title keywords to boost (from Router hint).
        trace_id:        Logging correlation.

    Returns:
        Deduplicated list of chunk dicts, sorted by relevance.
    """
    t0 = time.perf_counter()

    query_vec = embed_query(query)

    # Pass 1: broad semantic search (2× top_k to allow for dedup + filtering)
    broad_results = semantic_search(
        contract_id=contract_id,
        query_embedding=query_vec,
        top_k=top_k * 2,
        trace_id=trace_id,
    )

    # Pass 2: section-targeted search for each hinted section
    section_hits: List[dict] = []
    if likely_sections:
        for section_hint in likely_sections[:3]:  # cap to 3 sections per query
            targeted = semantic_search(
                contract_id=contract_id,
                query_embedding=query_vec,
                top_k=top_k,
                section_filter=section_hint,
                trace_id=trace_id,
            )
            section_hits.extend(targeted)

    # Merge: section hits take priority, fill remainder with broad hits
    merged = _merge_and_dedup(section_hits, broad_results, top_k=top_k)

    duration_ms = (time.perf_counter() - t0) * 1000
    logger.debug(
        "retrieval_complete",
        trace_id=trace_id,
        query=query[:80],
        broad_hits=len(broad_results),
        section_hits=len(section_hits),
        final_hits=len(merged),
        duration_ms=round(duration_ms, 2),
    )

    return merged


def retrieve_for_question(
    contract_id: str,
    sub_criterion_queries: List[dict],  # [{sub_id, query, likely_sections}]
    top_k_per_criterion: int = 3,
    trace_id: str = "unknown",
) -> List[dict]:
    """
    Run retrieval for all sub-criteria of one compliance question.

    Args:
        contract_id:            Which contract's collection.
        sub_criterion_queries:  List of dicts from the Router Agent.
        top_k_per_criterion:    Chunks per sub-criterion query.
        trace_id:               Logging correlation.

    Returns:
        Merged, deduplicated list of chunks covering all sub-criteria.
    """
    all_hits: List[dict] = []

    for sc_query in sub_criterion_queries:
        hits = retrieve_for_query(
            contract_id=contract_id,
            query=sc_query["query"],
            top_k=top_k_per_criterion,
            likely_sections=sc_query.get("likely_sections", []),
            trace_id=trace_id,
        )
        # Tag each hit with which sub-criterion retrieved it
        for hit in hits:
            hit["retrieved_for_criterion"] = sc_query.get("sub_id", "")
        all_hits.extend(hits)

    # Final dedup across all sub-criteria
    merged = _merge_and_dedup(all_hits, [], top_k=top_k_per_criterion * len(sub_criterion_queries))

    logger.info(
        "question_retrieval_complete",
        trace_id=trace_id,
        num_sub_criteria=len(sub_criterion_queries),
        total_chunks_retrieved=len(merged),
    )

    return merged


def retrieve_from_act(
    query: str,
    top_k: int = 3,
    trace_id: str = "unknown",
    collection_name: Optional[str] = None,
) -> List[dict]:
    """
    Retrieve the most relevant law sections for a given query.

    collection_name: ChromaDB collection to search. Defaults to the legacy
                     eao-act-reference collection if not provided.
    Returns chunks tagged with source='act'.
    """
    target = collection_name or settings.esa_act_collection_name
    query_vec = embed_query(query)
    hits = semantic_search(
        contract_id=target,
        query_embedding=query_vec,
        top_k=top_k,
        trace_id=trace_id,
    )
    for hit in hits:
        hit["source"] = "act"
        hit["section_title"] = hit.get("section_title") or hit.get("metadata", {}).get("title", "Law")
    return hits


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _merge_and_dedup(
    priority: List[dict],
    fallback: List[dict],
    top_k: int,
) -> List[dict]:
    """
    Merge two ranked lists, dedup by chunk_id, return top_k.
    Items from `priority` appear first.
    """
    seen: set = set()
    result: List[dict] = []

    for hit in priority + fallback:
        chunk_id = hit.get("chunk_id", "")
        if chunk_id and chunk_id not in seen:
            seen.add(chunk_id)
            result.append(hit)

    return result[:top_k]
