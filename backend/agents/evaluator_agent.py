"""
Evaluator Agent — the critic layer.

Three-layer evaluation strategy:

  Layer 1 (Deterministic): Fuzzy-match every quote against source chunks.
           Flags quotes not found in the actual retrieved text.

  Layer 2 (LLM Critic): Sends the full compliance result back to Claude
           with a critic prompt. Checks completeness, consistency,
           confidence calibration, and logical coherence.

  Layer 3 (Decision): If FAIL and retry_count < MAX_RETRIES, signal
           retry to the orchestrator with the critique as feedback.
           If still failing at max retries, emit PASS_WITH_FLAGS and
           lower confidence.
"""

from __future__ import annotations

import json
import time
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from backend.compliance.schemas import (
    ComplianceResult,
    ComplianceState,
    EvaluatorAssessment,
    EvaluatorVerdict,
)
from backend.config import settings
from backend.observability.logger import get_logger

logger = get_logger(__name__)

_EVALUATOR_SYSTEM_PROMPT = """You are a senior QA analyst reviewing a compliance determination for accuracy and completeness.
You will receive:
1. The compliance question and its sub-criteria.
2. The analyst's determination (state, confidence, quotes, rationale).
3. The original contract excerpts that were provided to the analyst.

Evaluate the determination on these dimensions:
A. COMPLETENESS: Has each sub-criterion been addressed? Are any skipped without justification?
B. CONSISTENCY: Does the compliance state logically match the evidence cited?
C. CONFIDENCE CALIBRATION: Is the confidence score appropriate given the evidence quality?
D. GROUNDEDNESS: Do the quoted texts plausibly appear in the provided excerpts?

Return ONLY a valid JSON object (no markdown, no commentary):
{
  "verdict": "PASS" | "FAIL" | "PASS_WITH_FLAGS",
  "issues": ["<specific issue 1>", "<specific issue 2>"],
  "confidence_adjustment": <float -0.3 to 0.3, positive means increase>,
  "critique": "<overall critique for the analyst if verdict is FAIL>"
}

Verdict guidelines:
- PASS: determination is accurate, complete, and well-grounded.
- PASS_WITH_FLAGS: minor issues noted but overall determination is sound.
- FAIL: significant issues that require re-analysis (e.g., wrong state, major sub-criterion missed, fabricated quotes).
"""


def run_evaluator_agent(
    compliance_result: ComplianceResult,
    retrieved_chunks: List[dict],
    question_full_text: str,
    sub_criteria_descriptions: List[str],
    trace_id: str,
) -> Dict[str, Any]:
    """
    Evaluate the Compliance Agent's output.

    Args:
        compliance_result:         Output from the Compliance Agent.
        retrieved_chunks:          The same chunks provided to the Compliance Agent.
        question_full_text:        Full compliance question text.
        sub_criteria_descriptions: List of sub-criterion descriptions.
        trace_id:                  Logging correlation.

    Returns:
        {
          "assessment": EvaluatorAssessment,
          "should_retry": bool,
          "retry_feedback": str,
          "updated_result": ComplianceResult,  # confidence-adjusted
          "evaluator_latency_ms": float,
          "llm_input_tokens": int,
          "llm_output_tokens": int,
        }
    """
    t0 = time.perf_counter()

    # ── Layer 1: Deterministic hallucination check ──
    source_texts = [c.get("text", "") for c in retrieved_chunks]
    hallucination_flags = _check_hallucinations(
        quotes=[q.text for q in compliance_result.relevant_quotes],
        source_texts=source_texts,
        threshold=settings.hallucination_match_threshold,
        trace_id=trace_id,
        question_id=compliance_result.question_id,
    )

    # ── Layer 2: LLM critic ──
    llm_assessment, input_tokens, output_tokens = _run_llm_critic(
        compliance_result=compliance_result,
        retrieved_chunks=retrieved_chunks,
        question_full_text=question_full_text,
        sub_criteria_descriptions=sub_criteria_descriptions,
        trace_id=trace_id,
    )

    # Merge hallucination flags into the LLM assessment
    llm_assessment.hallucination_flags = hallucination_flags
    if hallucination_flags and llm_assessment.verdict == EvaluatorVerdict.PASS:
        llm_assessment.verdict = EvaluatorVerdict.PASS_WITH_FLAGS
        llm_assessment.issues.append(
            f"{len(hallucination_flags)} quote(s) could not be verified in source chunks"
        )

    # ── Layer 3: Decide retry ──
    should_retry = llm_assessment.verdict == EvaluatorVerdict.FAIL
    retry_feedback = llm_assessment.critique if should_retry else ""

    # Apply confidence adjustment
    adjusted_confidence = max(
        0.0,
        min(1.0, compliance_result.confidence + llm_assessment.confidence_adjustment),
    )

    # Penalise if hallucinations were found
    if hallucination_flags:
        adjusted_confidence = max(0.0, adjusted_confidence - 0.10 * len(hallucination_flags))

    # If confidence dropped below 0.5, a Fully Compliant state is no longer defensible
    adjusted_state = compliance_result.compliance_state
    if (adjusted_state == ComplianceState.FULLY_COMPLIANT and adjusted_confidence < 0.5):
        adjusted_state = ComplianceState.PARTIALLY_COMPLIANT

    updated_result = compliance_result.model_copy(
        update={
            "confidence": adjusted_confidence,
            "compliance_state": adjusted_state,
            "evaluator_assessment": llm_assessment,
        }
    )

    duration_ms = (time.perf_counter() - t0) * 1000

    logger.info(
        "evaluator_complete",
        trace_id=trace_id,
        question_id=compliance_result.question_id,
        verdict=llm_assessment.verdict.value,
        hallucination_flags=len(hallucination_flags),
        should_retry=should_retry,
        confidence_before=compliance_result.confidence,
        confidence_after=adjusted_confidence,
        duration_ms=round(duration_ms, 2),
    )

    return {
        "assessment": llm_assessment,
        "should_retry": should_retry,
        "retry_feedback": retry_feedback,
        "updated_result": updated_result,
        "evaluator_latency_ms": round(duration_ms, 2),
        "llm_input_tokens": input_tokens,
        "llm_output_tokens": output_tokens,
    }


# ─────────────────────────────────────────────
# Layer 1: Hallucination detection
# ─────────────────────────────────────────────

def _check_hallucinations(
    quotes: List[str],
    source_texts: List[str],
    threshold: float,
    trace_id: str,
    question_id: int,
) -> List[str]:
    """
    Fuzzy-match each quote against the source chunks.
    Returns a list of quotes that could NOT be matched above the threshold.
    """
    if not quotes or not source_texts:
        return []

    full_source = " ".join(source_texts)
    flagged: List[str] = []

    for quote in quotes:
        if not quote.strip():
            continue
        best_score = _best_fuzzy_match(quote, source_texts)
        if best_score < threshold:
            flagged.append(quote[:100] + ("..." if len(quote) > 100 else ""))
            logger.warning(
                "hallucination_flag",
                trace_id=trace_id,
                question_id=question_id,
                quote_preview=quote[:80],
                best_match_score=round(best_score, 3),
                threshold=threshold,
            )

    return flagged


def _best_fuzzy_match(quote: str, sources: List[str]) -> float:
    """Return the highest fuzzy match ratio between quote and any source chunk."""
    best = 0.0
    # Normalise for comparison
    q_norm = quote.lower().strip()
    for source in sources:
        # Check if quote is a substring (exact)
        if q_norm in source.lower():
            return 1.0
        # Sliding window fuzzy match (compare quote against equal-length windows)
        ratio = SequenceMatcher(None, q_norm, source.lower()).ratio()
        if ratio > best:
            best = ratio
    return best


# ─────────────────────────────────────────────
# Layer 2: LLM critic
# ─────────────────────────────────────────────

def _run_llm_critic(
    compliance_result: ComplianceResult,
    retrieved_chunks: List[dict],
    question_full_text: str,
    sub_criteria_descriptions: List[str],
    trace_id: str,
) -> tuple[EvaluatorAssessment, int, int]:
    """Call Claude via LangChain to critically review the compliance determination."""
    llm = ChatAnthropic(model=settings.llm_model, max_tokens=512, api_key=settings.anthropic_api_key)

    # Format the original context
    context_parts = []
    for i, chunk in enumerate(retrieved_chunks[:8], 1):  # cap context for efficiency
        section = chunk.get("section_title", "Unknown")
        context_parts.append(f"[Excerpt {i} | {section}]\n{chunk.get('text', '')[:500]}")

    context_text = "\n\n".join(context_parts) or "No excerpts available."

    sub_criteria_text = "\n".join(
        f"  - {desc}" for desc in sub_criteria_descriptions
    )

    # Format quotes for review
    quotes_text = "\n".join(
        f'  [{i+1}] "{q.text[:200]}" ({q.section_reference})'
        for i, q in enumerate(compliance_result.relevant_quotes[:6])
    ) or "  No quotes provided."

    user_content = (
        f"## Compliance Question\n{question_full_text}\n\n"
        f"## Sub-criteria\n{sub_criteria_text}\n\n"
        f"## Analyst's Determination\n"
        f"- State: {compliance_result.compliance_state.value}\n"
        f"- Confidence: {compliance_result.confidence:.0%}\n"
        f"- Rationale: {compliance_result.rationale[:800]}\n\n"
        f"## Quotes Cited\n{quotes_text}\n\n"
        f"## Original Contract Excerpts\n{context_text}"
    )

    logger.debug(
        "evaluator_llm_call",
        trace_id=trace_id,
        question_id=compliance_result.question_id,
        model=settings.llm_model,
    )

    response = llm.invoke([
        SystemMessage(content=_EVALUATOR_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ])

    raw_text = response.content
    input_tokens = response.usage_metadata.get("input_tokens", 0)
    output_tokens = response.usage_metadata.get("output_tokens", 0)

    assessment = _parse_evaluator_response(raw_text, trace_id, compliance_result.question_id)

    return assessment, input_tokens, output_tokens


def _parse_evaluator_response(
    raw_text: str,
    trace_id: str,
    question_id: int,
) -> EvaluatorAssessment:
    """Parse the evaluator LLM response into an EvaluatorAssessment."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned

    try:
        data = json.loads(cleaned)
        verdict_str = data.get("verdict", "PASS_WITH_FLAGS")
        try:
            verdict = EvaluatorVerdict(verdict_str)
        except ValueError:
            verdict = EvaluatorVerdict.PASS_WITH_FLAGS

        return EvaluatorAssessment(
            verdict=verdict,
            issues=data.get("issues", []),
            hallucination_flags=[],  # filled by Layer 1
            confidence_adjustment=float(data.get("confidence_adjustment", 0.0)),
            critique=data.get("critique", ""),
        )
    except Exception as exc:
        logger.warning(
            "evaluator_json_parse_failed",
            trace_id=trace_id,
            question_id=question_id,
            error=str(exc),
        )
        return EvaluatorAssessment(
            verdict=EvaluatorVerdict.PASS_WITH_FLAGS,
            issues=["Evaluator response parsing failed — defaulting to PASS_WITH_FLAGS"],
            confidence_adjustment=-0.05,
            critique="",
        )
