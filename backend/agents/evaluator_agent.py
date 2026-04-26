"""
Evaluator Agent — the critic layer.

Three-layer evaluation strategy:

  Layer 1 (Deterministic): Fuzzy-match every quote against source chunks.
           Flags quotes not found in the actual retrieved text.

  Layer 2 (LLM Critic): Sends the full compliance result back to the LLM
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

from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from backend.compliance.schemas import (
    ComplianceResult,
    ComplianceState,
    EvaluatorAssessment,
    EvaluatorVerdict,
)
from backend.config import settings
from backend.llm_factory import get_llm
from backend.observability.logger import get_logger

logger = get_logger(__name__)

_EVALUATOR_SYSTEM_PROMPT = """You are a senior QA analyst and employment lawyer reviewing an ESA compliance determination for accuracy and completeness.
You will receive:
1. The ESA compliance question and its sub-criteria (with ESA section references).
2. The analyst's determination (state, confidence, quotes, rationale, gap summary).
3. The original CONTRACT excerpts that were provided to the analyst.
4. The original ESA ACT excerpts that were provided to the analyst.

Evaluate the determination on these dimensions:
A. COMPLETENESS: Has each sub-criterion been addressed? Are any skipped without justification?
B. CONSISTENCY: Does the compliance state logically match the evidence cited?
   - "Fully Compliant" requires the contract to explicitly meet the ESA minimum — not just silence.
   - "Partially Compliant" is appropriate when the contract is silent (ESA default applies) or ambiguous.
   - "Non-Compliant" requires explicit violation (below minimum or void waiver).
C. CONFIDENCE CALIBRATION: Is the confidence score appropriate given the evidence quality?
D. GROUNDEDNESS: Do the quoted texts actually appear in the provided excerpts?
   - Contract quotes must appear in CONTRACT excerpts.
   - Act quotes must appear in ACT excerpts.
   - Fabricated or paraphrased quotes must be flagged.
E. ESA ACCURACY: Does the analyst correctly apply the ESA requirements?
   - Wrong ESA section cited?
   - ESA threshold incorrectly stated (e.g., overtime at wrong hour)?
   - Severance formula incorrect?

Return ONLY a valid JSON object (no markdown, no commentary):
{
  "verdict": "PASS" | "FAIL" | "PASS_WITH_FLAGS",
  "issues": ["<specific issue 1>", "<specific issue 2>"],
  "confidence_adjustment": <float -0.3 to 0.3, positive means increase>,
  "critique": "<overall critique for the analyst if verdict is FAIL>"
}

Verdict guidelines:
- PASS: determination is accurate, well-grounded, and ESA requirements correctly applied.
- PASS_WITH_FLAGS: minor issues noted but overall determination is sound.
- FAIL: significant issues requiring re-analysis (wrong state, fabricated quotes, incorrect ESA application, major sub-criterion missed).
"""


def run_evaluator_agent(
    compliance_result: ComplianceResult,
    retrieved_chunks: List[dict],
    question_full_text: str,
    sub_criteria_descriptions: List[str],
    trace_id: str,
    model: str | None = None,
    act_chunks: Optional[List[dict]] = None,
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
    # Contract quotes verified against contract chunks; act quotes against act chunks
    contract_source_texts = [c.get("text", "") for c in retrieved_chunks]
    act_source_texts = [c.get("text", "") for c in (act_chunks or [])]

    contract_quote_texts = [q.text for q in compliance_result.relevant_quotes if q.source == "contract"]
    act_quote_texts = [q.text for q in compliance_result.relevant_quotes if q.source == "act"]

    hallucination_flags = _check_hallucinations(
        quotes=contract_quote_texts,
        source_texts=contract_source_texts,
        threshold=settings.hallucination_match_threshold,
        trace_id=trace_id,
        question_id=compliance_result.question_id,
    )
    # Also check act quotes against act text
    act_hallucinations = _check_hallucinations(
        quotes=act_quote_texts,
        source_texts=act_source_texts,
        threshold=settings.hallucination_match_threshold,
        trace_id=trace_id,
        question_id=compliance_result.question_id,
    )
    hallucination_flags = hallucination_flags + act_hallucinations

    # ── Layer 2: LLM critic ──
    llm_assessment, input_tokens, output_tokens = _run_llm_critic(
        compliance_result=compliance_result,
        retrieved_chunks=retrieved_chunks,
        question_full_text=question_full_text,
        sub_criteria_descriptions=sub_criteria_descriptions,
        trace_id=trace_id,
        model=model,
        act_chunks=act_chunks,
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
    model: str | None = None,
    act_chunks: Optional[List[dict]] = None,
) -> tuple[EvaluatorAssessment, int, int]:
    """Call the LLM via LangChain to critically review the compliance determination."""
    llm = get_llm(model, max_tokens=512)

    # Format the original contract excerpts
    contract_context_parts = []
    for i, chunk in enumerate(retrieved_chunks[:6], 1):
        section = chunk.get("section_title", "Unknown")
        contract_context_parts.append(f"[Contract Excerpt {i} | {section}]\n{chunk.get('text', '')[:400]}")
    contract_context = "\n\n".join(contract_context_parts) or "No contract excerpts."

    # Format the original act excerpts
    act_context_parts = []
    for i, chunk in enumerate((act_chunks or [])[:4], 1):
        section = chunk.get("section_title") or chunk.get("metadata", {}).get("title", "ESA")
        act_context_parts.append(f"[ESA Excerpt {i} | {section}]\n{chunk.get('text', '')[:400]}")
    act_context = "\n\n".join(act_context_parts) or "No ESA excerpts."

    sub_criteria_text = "\n".join(
        f"  - {desc}" for desc in sub_criteria_descriptions
    )

    # Format quotes for review — show source
    contract_quotes_text = "\n".join(
        f'  [{i+1}] (CONTRACT) "{q.text[:200]}" ({q.section_reference})'
        for i, q in enumerate(compliance_result.contract_quotes[:4])
    ) or "  No contract quotes."
    act_quotes_text = "\n".join(
        f'  [{i+1}] (ACT) "{q.text[:200]}" ({q.section_reference})'
        for i, q in enumerate(compliance_result.act_quotes[:4])
    ) or "  No act quotes."

    user_content = (
        f"## ESA Compliance Question\n{question_full_text}\n\n"
        f"## Sub-criteria\n{sub_criteria_text}\n\n"
        f"## Analyst's Determination\n"
        f"- State: {compliance_result.compliance_state.value}\n"
        f"- Confidence: {compliance_result.confidence:.0%}\n"
        f"- Gap Summary: {compliance_result.gap_summary[:300]}\n"
        f"- Rationale: {compliance_result.rationale[:600]}\n\n"
        f"## Contract Quotes Cited\n{contract_quotes_text}\n\n"
        f"## ESA Act Quotes Cited\n{act_quotes_text}\n\n"
        f"## Original Contract Excerpts\n{contract_context}\n\n"
        f"## Original ESA Act Excerpts\n{act_context}"
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
