"""
Router Agent.

Responsibilities:
  1. Decompose each compliance question into sub-criterion queries.
  2. Predict which contract sections are most likely to contain evidence.
  3. Execute hybrid retrieval for all sub-criteria.
  4. Return a RouterDecision with retrieved chunks ready for the Compliance Agent.

Uses Claude to generate the sub-criterion query plan, then calls the
retriever for actual chunk fetching.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from backend.compliance.questions import ComplianceQuestion
from backend.config import settings
from backend.observability.logger import get_logger
from backend.rag.retriever import retrieve_for_question

logger = get_logger(__name__)

_ROUTER_SYSTEM_PROMPT = """You are a senior compliance analyst and information retrieval specialist.
Your task is to analyse a compliance question and plan targeted retrieval queries
for each of its sub-criteria so that downstream analysis is grounded in the most
relevant contract language.

For each sub-criterion provided, you must:
1. Write a concise, specific retrieval query (1–2 sentences) that will surface the most relevant contract text.
2. List the contract section titles or exhibit references most likely to contain evidence.

Return ONLY a valid JSON array (no commentary, no markdown fences) where each element has:
{
  "sub_id": "<criterion ID>",
  "query": "<retrieval query string>",
  "likely_sections": ["<section title>", ...]
}
"""


def run_router_agent(
    question: ComplianceQuestion,
    contract_id: str,
    trace_id: str,
    top_k_per_criterion: int = 3,
) -> Dict[str, Any]:
    """
    Plan and execute retrieval for one compliance question.

    Returns:
        {
          "question_id": int,
          "sub_criterion_queries": [...],
          "retrieved_chunks": [...],
          "router_latency_ms": float,
          "llm_input_tokens": int,
          "llm_output_tokens": int,
        }
    """
    t0 = time.perf_counter()
    llm = ChatAnthropic(model=settings.llm_model, max_tokens=1024, api_key=settings.anthropic_api_key)

    sub_criteria_text = "\n".join(
        f"  - [{sc.id}] {sc.description} (keywords: {', '.join(sc.keywords[:4])})"
        for sc in question.sub_criteria
    )

    user_message = (
        f"Compliance Question: {question.title}\n\n"
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
        model=settings.llm_model,
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

    # Parse the LLM's query plan
    sub_criterion_queries = _parse_query_plan(raw_text, question, trace_id)

    logger.info(
        "router_query_plan",
        trace_id=trace_id,
        question_id=question.id,
        num_queries=len(sub_criterion_queries),
        queries=[q["sub_id"] for q in sub_criterion_queries],
    )

    # Execute retrieval for all sub-criteria
    retrieved_chunks = retrieve_for_question(
        contract_id=contract_id,
        sub_criterion_queries=sub_criterion_queries,
        top_k_per_criterion=top_k_per_criterion,
        trace_id=trace_id,
    )

    total_duration = (time.perf_counter() - t0) * 1000

    logger.info(
        "router_complete",
        trace_id=trace_id,
        question_id=question.id,
        chunks_retrieved=len(retrieved_chunks),
        router_latency_ms=round(total_duration, 2),
    )

    return {
        "question_id": question.id,
        "sub_criterion_queries": sub_criterion_queries,
        "retrieved_chunks": retrieved_chunks,
        "router_latency_ms": round(total_duration, 2),
        "llm_input_tokens": input_tokens,
        "llm_output_tokens": output_tokens,
    }


def _parse_query_plan(
    raw_text: str,
    question: ComplianceQuestion,
    trace_id: str,
) -> List[Dict[str, Any]]:
    """
    Parse the LLM's JSON query plan.
    Falls back to keyword-based queries if parsing fails.
    """
    # Strip markdown code fences if present
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned

    try:
        plan = json.loads(cleaned)
        if isinstance(plan, list) and all("sub_id" in p and "query" in p for p in plan):
            # Merge in the hinted sections from our question definition
            for item in plan:
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

    # Fallback: generate a basic query per sub-criterion using keywords
    return [
        {
            "sub_id": sc.id,
            "query": f"{sc.description}. Keywords: {', '.join(sc.keywords[:4])}",
            "likely_sections": question.likely_sections,
        }
        for sc in question.sub_criteria
    ]
