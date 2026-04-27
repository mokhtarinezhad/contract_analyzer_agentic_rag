"""
Contract Classifier Agent.

Reads a broad sample of the uploaded contract and determines which ESA
compliance questions are applicable. Always-applicable questions are
always included. Conditional questions are included only when the
contract signals relevance (per each question's applicability_note).

Returns a list of question IDs to run through the pipeline.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from backend.compliance.eao_questions import (
    get_always_applicable_questions,
    get_conditional_questions,
)
from backend.config import settings
from backend.llm_factory import get_llm, invoke_with_retry
from backend.observability.logger import get_logger
from backend.rag.vector_store import get_all_chunks

logger = get_logger(__name__)

_CLASSIFIER_SYSTEM_PROMPT = """You are a senior employment lawyer and contract analyst.
You will be given:
1. A representative sample of an employment contract's text.
2. A list of CONDITIONAL ESA compliance questions — each with an applicability condition.

Your task: For each conditional question, decide whether the contract TRIGGERS that question.
Read the applicability condition carefully. Answer YES only if the contract clearly contains
the relevant content, employment type, or employer characteristic described in the condition.
Answer NO if the contract gives no indication the condition is met.

Return ONLY a valid JSON object mapping question IDs to true/false (no commentary, no markdown):
{
  "ESA-HOURS-05": true,
  "ESA-PAY-05": false,
  ...
}
"""


def run_classifier_agent(
    contract_id: str,
    trace_id: str,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Determine which ESA questions apply to this specific contract.

    Args:
        contract_id:  The contract's ChromaDB collection ID.
        trace_id:     Logging correlation.
        model:        LLM model to use.

    Returns:
        {
          "applicable_question_ids": List[str],
          "always_applicable_ids": List[str],
          "conditional_triggered_ids": List[str],
          "classifier_latency_ms": float,
          "llm_input_tokens": int,
          "llm_output_tokens": int,
        }
    """
    t0 = time.perf_counter()
    active_model = model or settings.llm_model
    llm = get_llm(active_model, max_tokens=1024)

    always_qs = get_always_applicable_questions()
    conditional_qs = get_conditional_questions()

    always_ids = [q.id for q in always_qs]

    # Get a broad sample of contract chunks for context
    contract_text = _get_contract_sample(contract_id)

    if not conditional_qs:
        duration_ms = (time.perf_counter() - t0) * 1000
        return {
            "applicable_question_ids": always_ids,
            "always_applicable_ids": always_ids,
            "conditional_triggered_ids": [],
            "classifier_latency_ms": round(duration_ms, 2),
            "llm_input_tokens": 0,
            "llm_output_tokens": 0,
        }

    conditional_descriptions = "\n\n".join(
        f"[{q.id}] {q.title}\n"
        f"  Applicability condition: {q.applicability_note}"
        for q in conditional_qs
    )

    user_message = (
        f"## Contract Sample (representative excerpt)\n\n{contract_text}\n\n"
        f"## Conditional ESA Questions to Evaluate\n\n{conditional_descriptions}\n\n"
        "For each question ID above, return true if the contract triggers the condition, "
        "false otherwise. Return a JSON object."
    )

    logger.info(
        "classifier_llm_call_start",
        trace_id=trace_id,
        num_conditional_questions=len(conditional_qs),
        contract_sample_chars=len(contract_text),
        model=active_model,
    )

    response = invoke_with_retry(llm, [
        SystemMessage(content=_CLASSIFIER_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ])

    input_tokens = response.usage_metadata.get("input_tokens", 0)
    output_tokens = response.usage_metadata.get("output_tokens", 0)

    triggered_ids = _parse_classifier_response(
        response.content,
        conditional_qs,
        trace_id,
    )

    applicable_ids = always_ids + triggered_ids

    duration_ms = (time.perf_counter() - t0) * 1000

    logger.info(
        "classifier_complete",
        trace_id=trace_id,
        always_applicable=len(always_ids),
        conditional_triggered=len(triggered_ids),
        total_applicable=len(applicable_ids),
        triggered_ids=triggered_ids,
        classifier_latency_ms=round(duration_ms, 2),
    )

    return {
        "applicable_question_ids": applicable_ids,
        "always_applicable_ids": always_ids,
        "conditional_triggered_ids": triggered_ids,
        "classifier_latency_ms": round(duration_ms, 2),
        "llm_input_tokens": input_tokens,
        "llm_output_tokens": output_tokens,
    }


def _get_contract_sample(contract_id: str, max_chars: int = 8000) -> str:
    """Get a representative text sample from the contract for classification."""
    chunks = get_all_chunks(contract_id)
    if not chunks:
        return "No contract text available."

    # Take every Nth chunk to get a broad cross-section
    step = max(1, len(chunks) // 20)
    sampled = chunks[::step][:20]

    parts = []
    total = 0
    for chunk in sampled:
        text = chunk.get("text", "").strip()
        if not text:
            continue
        section = chunk.get("metadata", {}).get("section_title") or "—"
        part = f"[{section}]\n{text}"
        total += len(part)
        parts.append(part)
        if total >= max_chars:
            break

    return "\n\n---\n\n".join(parts) or "No contract text available."


def _parse_classifier_response(
    raw_text: str,
    conditional_qs,
    trace_id: str,
) -> List[str]:
    """Parse the classifier LLM response into a list of triggered question IDs."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned

    conditional_ids = {q.id for q in conditional_qs}

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return [
                qid for qid, triggered in data.items()
                if triggered and qid in conditional_ids
            ]
    except (json.JSONDecodeError, TypeError):
        logger.warning(
            "classifier_json_parse_failed",
            trace_id=trace_id,
            raw_text=raw_text[:300],
        )

    # Fallback: keyword-based classification using applicability notes
    logger.info("classifier_using_keyword_fallback", trace_id=trace_id)
    return _keyword_classify(conditional_qs, raw_text)


def _keyword_classify(conditional_qs, contract_sample: str) -> List[str]:
    """Simple keyword-based fallback classifier."""
    contract_lower = contract_sample.lower()
    triggered = []

    keyword_triggers = {
        "ESA-HOURS-05": ["after hours", "on call", "available", "24/7", "respond immediately",
                         "monitoring", "25 employees", "large employer"],
        "ESA-PAY-05": ["part-time", "part time", "casual", "temporary", "seasonal",
                       "per diem", "contract employee"],
        "ESA-BENEFIT-01": ["benefits", "group insurance", "health plan", "dental", "vision",
                           "pension", "rrsp", "life insurance", "disability insurance"],
        "ESA-CLASS-02": ["probation", "probationary", "trial period", "90 days", "3 months",
                         "initial period"],
        "ESA-MONITOR-01": ["monitoring", "electronic monitoring", "tracking", "gps", "location",
                            "productivity software", "computer use", "surveillance"],
        "ESA-LEAVE-08": ["military", "reserve", "canadian forces", "armed forces", "reservist"],
    }

    for q in conditional_qs:
        triggers = keyword_triggers.get(q.id, [])
        if any(kw in contract_lower for kw in triggers):
            triggered.append(q.id)

    return triggered
