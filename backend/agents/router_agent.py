"""
Router Agent.

Responsibilities:
  1. Decompose each ESA compliance question into sub-criterion queries.
  2. Execute hybrid retrieval against the contract (contract chunks).
  3. Execute retrieval against the ESA act reference (act chunks).
  4. Return both sets of chunks to the Compliance Agent.

Uses the LLM to generate the sub-criterion query plan, then calls the
retriever for actual chunk fetching from both sources.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from backend.compliance.eao_questions import ESAComplianceQuestion
from backend.config import settings
from backend.llm_factory import get_llm
from backend.observability.logger import get_logger
from backend.rag.retriever import retrieve_for_question, retrieve_from_act

logger = get_logger(__name__)

_ROUTER_SYSTEM_PROMPT = """You are a senior employment lawyer and information retrieval specialist.
Your task is to analyse an ESA compliance question and plan targeted retrieval queries
for each of its sub-criteria so that downstream analysis is grounded in the most
relevant contract language AND relevant ESA sections.

For each sub-criterion provided, you must:
1. Write a concise retrieval query for the CONTRACT (what contract language to look for).
2. Write a concise retrieval query for the ESA ACT (what statutory text to retrieve).
3. List the contract section titles or exhibit references most likely to contain evidence.

Return ONLY a valid JSON array (no commentary, no markdown fences) where each element has:
{
  "sub_id": "<criterion ID>",
  "contract_query": "<query to search the contract>",
  "act_query": "<query to search the ESA act text>",
  "likely_sections": ["<section title>", ...]
}
"""


def run_router_agent(
    question: ESAComplianceQuestion,
    contract_id: str,
    trace_id: str,
    top_k_per_criterion: int = 3,
    model: str | None = None,
    act_collection_name: str | None = None,
) -> Dict[str, Any]:
    """
    Plan and execute retrieval for one ESA compliance question.

    Returns:
        {
          "question_id": str,
          "sub_criterion_queries": [...],
          "retrieved_chunks": [...],      # contract chunks
          "act_chunks": [...],            # ESA act chunks
          "router_latency_ms": float,
          "llm_input_tokens": int,
          "llm_output_tokens": int,
        }
    """
    t0 = time.perf_counter()
    active_model = model or settings.llm_model
    llm = get_llm(active_model, max_tokens=1024)

    sub_criteria_text = "\n".join(
        f"  - [{sc.id}] {sc.description} (ESA: {sc.esa_section}, keywords: {', '.join(sc.keywords[:4])})"
        for sc in question.sub_criteria
    )

    user_message = (
        f"ESA Compliance Question: {question.title}\n"
        f"ESA Parts: {', '.join(question.esa_parts)}\n"
        f"ESA Sections: {', '.join(question.esa_sections)}\n\n"
        f"Full requirement text:\n{question.full_text}\n\n"
        f"Sub-criteria to create retrieval queries for:\n{sub_criteria_text}\n\n"
        f"Known likely contract sections: {', '.join(question.likely_sections[:6])}\n\n"
        "Generate the retrieval query plan as a JSON array."
    )

    logger.info(
        "router_llm_call_start",
        trace_id=trace_id,
        question_id=question.id,
        question_title=question.title,
        model=active_model,
    )

    llm_t0 = time.perf_counter()
    response = llm.invoke([
        SystemMessage(content=_ROUTER_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ])
    llm_duration = (time.perf_counter() - llm_t0) * 1000

    raw_text = response.content
    input_tokens = response.usage_metadata.get("input_tokens", 0)
    output_tokens = response.usage_metadata.get("output_tokens", 0)

    logger.info(
        "router_llm_call_complete",
        trace_id=trace_id,
        question_id=question.id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        llm_duration_ms=round(llm_duration, 2),
    )

    sub_criterion_queries = _parse_query_plan(raw_text, question, trace_id)

    logger.info(
        "router_query_plan",
        trace_id=trace_id,
        question_id=question.id,
        num_queries=len(sub_criterion_queries),
        queries=[q["sub_id"] for q in sub_criterion_queries],
    )

    # ── Retrieve from contract ──────────────────────────────────────────────
    contract_queries = [
        {
            "sub_id": q["sub_id"],
            "query": q["contract_query"],
            "likely_sections": q.get("likely_sections", question.likely_sections),
        }
        for q in sub_criterion_queries
    ]
    retrieved_chunks = retrieve_for_question(
        contract_id=contract_id,
        sub_criterion_queries=contract_queries,
        top_k_per_criterion=top_k_per_criterion,
        trace_id=trace_id,
    )
    for chunk in retrieved_chunks:
        chunk["source"] = "contract"

    # ── Retrieve from ESA act reference ────────────────────────────────────
    act_chunks: List[dict] = []
    seen_act_ids: set = set()
    for q in sub_criterion_queries:
        act_query = q.get("act_query", q.get("contract_query", ""))
        if not act_query:
            continue
        hits = retrieve_from_act(
            query=act_query,
            top_k=2,
            trace_id=trace_id,
            collection_name=act_collection_name,
        )
        for hit in hits:
            cid = hit.get("chunk_id", "")
            if cid not in seen_act_ids:
                seen_act_ids.add(cid)
                hit["source"] = "act"
                hit["retrieved_for_criterion"] = q["sub_id"]
                act_chunks.append(hit)

    total_duration = (time.perf_counter() - t0) * 1000

    logger.info(
        "router_complete",
        trace_id=trace_id,
        question_id=question.id,
        contract_chunks=len(retrieved_chunks),
        act_chunks=len(act_chunks),
        router_latency_ms=round(total_duration, 2),
    )

    return {
        "question_id": question.id,
        "sub_criterion_queries": sub_criterion_queries,
        "retrieved_chunks": retrieved_chunks,
        "act_chunks": act_chunks,
        "router_latency_ms": round(total_duration, 2),
        "llm_input_tokens": input_tokens,
        "llm_output_tokens": output_tokens,
    }


def _parse_query_plan(
    raw_text: str,
    question: ESAComplianceQuestion,
    trace_id: str,
) -> List[Dict[str, Any]]:
    """
    Parse the LLM's JSON query plan.
    Falls back to keyword-based queries if parsing fails.
    """
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned

    try:
        plan = json.loads(cleaned)
        if isinstance(plan, list) and all(
            "sub_id" in p and ("contract_query" in p or "query" in p)
            for p in plan
        ):
            for item in plan:
                # Handle both old-style 'query' and new-style 'contract_query'
                if "contract_query" not in item and "query" in item:
                    item["contract_query"] = item["query"]
                if "act_query" not in item:
                    item["act_query"] = f"{question.title} {item.get('contract_query', '')}"
                if not item.get("likely_sections"):
                    item["likely_sections"] = question.likely_sections
            return plan
    except (json.JSONDecodeError, KeyError):
        logger.warning(
            "router_json_parse_failed",
            trace_id=trace_id,
            question_id=question.id,
            raw_text=raw_text[:200],
        )

    # Fallback: generate a basic query per sub-criterion
    return [
        {
            "sub_id": sc.id,
            "contract_query": f"{sc.description}. Keywords: {', '.join(sc.keywords[:4])}",
            "act_query": f"ESA {sc.esa_section} {sc.description}",
            "likely_sections": question.likely_sections,
        }
        for sc in question.sub_criteria
    ]
