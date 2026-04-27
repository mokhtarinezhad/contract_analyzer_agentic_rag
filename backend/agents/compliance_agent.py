"""
Compliance Agent.

Given retrieved contract chunks AND ESA act chunks from the Router Agent:
  1. Analyses all sub-criteria against both sources.
  2. Determines the compliance state (Fully / Partially / Non-Compliant).
  3. Extracts verbatim quotes from BOTH the contract AND the ESA act text.
  4. Provides a calibrated confidence score.
  5. Identifies gaps between contract terms and ESA requirements.
  6. Returns a structured ComplianceResult with source-labelled quotes.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from backend.compliance.eao_questions import ESAComplianceQuestion
from backend.compliance.schemas import (
    ComplianceResult,
    ComplianceState,
    RelevantQuote,
    SubCriterionResult,
)
from backend.config import settings
from backend.llm_factory import get_llm, invoke_with_retry
from backend.observability.logger import get_logger

logger = get_logger(__name__)

_COMPLIANCE_SYSTEM_PROMPT = """You are a senior employment lawyer reviewing an employment contract for compliance with the Employment Standards Act of Ontario (ESA), 2000.

You will be given:
1. An ESA compliance question with specific sub-criteria and section references.
2. CONTRACT EXCERPTS — verbatim text from the uploaded employment contract.
3. ACT EXCERPTS — authoritative text from the ESA for the relevant sections.

Your task:
- Evaluate EACH sub-criterion by comparing the CONTRACT text against the ESA REQUIREMENT.
- Determine the overall compliance state.
- Extract VERBATIM quotes from BOTH sources:
  * Contract quotes: exact text from the employment contract (source: "contract")
  * Act quotes: the exact ESA statutory language that defines the requirement (source: "act")
- Identify any GAPS — where the contract is silent, below the ESA minimum, or attempts to waive rights.
- Assign a calibrated confidence score (0.0–1.0).

Compliance state rules:
- "Fully Compliant": ALL sub-criteria clearly met; contract language equals or exceeds ESA minimum.
- "Partially Compliant": SOME sub-criteria met, OR contract is SILENT (ESA minimum applies by law but not stated), OR language is ambiguous.
- "Non-Compliant": Contract EXPLICITLY gives less than ESA minimum, includes a void waiver of ESA rights, or uses 'for cause' standards below ESA threshold.

CRITICAL ANTI-HALLUCINATION RULES:
- Quote ONLY text that actually appears in the provided excerpts.
- Do NOT paraphrase or invent contract or act language.
- If the contract is silent on a point, state that explicitly — do not fabricate a quote.
- A silent contract is NOT automatically non-compliant; the ESA minimum applies by law.

Confidence calibration:
- 0.90–1.00: Explicit, unambiguous language in both contract and act confirming compliance.
- 0.70–0.89: Clear language but minor gaps or ambiguity.
- 0.50–0.69: Contract silent on point (ESA default applies) or significant ambiguity.
- Below 0.50: Contract appears below ESA minimum or evidence very weak.

You must call the submit_compliance_result tool with your analysis. Do not return plain text.
"""

_COMPLIANCE_TOOL = {
    "name": "submit_compliance_result",
    "description": "Submit the structured ESA compliance analysis result.",
    "parameters": {
        "type": "object",
        "properties": {
            "compliance_state": {
                "type": "string",
                "enum": ["Fully Compliant", "Partially Compliant", "Non-Compliant"],
                "description": "Overall ESA compliance state for this requirement.",
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Calibrated confidence score (0.0–1.0).",
            },
            "rationale": {
                "type": "string",
                "description": (
                    "Detailed reasoning comparing contract language against ESA requirements. "
                    "Reference specific ESA sections and contract clauses. "
                    "Explain what the contract says, what the ESA requires, and whether the contract meets the standard."
                ),
            },
            "relevant_quotes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Exact verbatim quote from the contract or ESA act."},
                        "section_reference": {"type": "string", "description": "Reference, e.g. 'Section 4.2 — Termination' or 'ESA s.57'."},
                        "page_number": {"type": ["integer", "null"]},
                        "source": {
                            "type": "string",
                            "enum": ["contract", "act"],
                            "description": "'contract' for quotes from the uploaded contract, 'act' for ESA statutory text.",
                        },
                    },
                    "required": ["text", "section_reference", "source"],
                },
            },
            "sub_criteria_results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "criterion_id": {"type": "string"},
                        "description": {"type": "string"},
                        "found": {"type": "boolean"},
                        "evidence_summary": {
                            "type": "string",
                            "description": "What the contract says (or doesn't say) about this sub-criterion, vs. what the ESA requires.",
                        },
                        "esa_section": {"type": "string"},
                    },
                    "required": ["criterion_id", "description", "found", "evidence_summary"],
                },
            },
            "act_sections_cited": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of ESA section references cited, e.g. ['ESA s.57', 'ESA s.64'].",
            },
            "gap_summary": {
                "type": "string",
                "description": (
                    "Summary of what is MISSING or INADEQUATE in the contract relative to ESA requirements. "
                    "If fully compliant, state 'No gaps identified.' "
                    "If silent, note that ESA minimum applies by law. "
                    "If below minimum, identify the specific shortfall."
                ),
            },
        },
        "required": [
            "compliance_state", "confidence", "rationale",
            "relevant_quotes", "sub_criteria_results",
            "act_sections_cited", "gap_summary",
        ],
    },
}


def run_compliance_agent(
    question: ESAComplianceQuestion,
    retrieved_chunks: List[dict],
    trace_id: str,
    act_chunks: Optional[List[dict]] = None,
    evaluator_feedback: Optional[str] = None,
    previous_result: Optional[ComplianceResult] = None,
    retry_count: int = 0,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run the ESA compliance analysis for one question.

    Args:
        question:           The ESAComplianceQuestion being analysed.
        retrieved_chunks:   Contract chunks from the Router Agent.
        trace_id:           Logging correlation.
        act_chunks:         ESA act chunks from the Router Agent.
        evaluator_feedback: If this is a retry, the evaluator's critique.
        previous_result:    The ComplianceResult from the previous attempt.
        retry_count:        Current retry attempt number.
        model:              LLM model override.
    """
    t0 = time.perf_counter()
    active_model = model or settings.llm_model
    llm = get_llm(active_model, max_tokens=2048)
    llm_with_tools = llm.bind_tools(
        [_COMPLIANCE_TOOL],
        tool_choice="submit_compliance_result",
    )

    contract_context = _format_contract_chunks(retrieved_chunks)
    act_context = _format_act_chunks(act_chunks or [])
    sub_criteria_text = _format_sub_criteria(question)

    first_user_message = (
        f"## ESA Compliance Requirement: {question.title}\n"
        f"**ESA Parts:** {', '.join(question.esa_parts)}\n"
        f"**ESA Sections:** {', '.join(question.esa_sections)}\n\n"
        f"**Full requirement text:**\n{question.full_text}\n\n"
        f"**Sub-criteria to evaluate:**\n{sub_criteria_text}\n\n"
        f"## CONTRACT EXCERPTS (from uploaded employment contract)\n\n{contract_context}\n\n"
        f"## ESA ACT EXCERPTS (from Employment Standards Act, 2000)\n\n{act_context}"
    )

    if evaluator_feedback and previous_result:
        messages = [
            SystemMessage(content=_COMPLIANCE_SYSTEM_PROMPT),
            HumanMessage(content=first_user_message),
            AIMessage(content=json.dumps(previous_result.model_dump(mode="json"), indent=2)),
            HumanMessage(content=(
                f"## Evaluator Feedback\n\n"
                f"Your previous analysis was flagged with these issues:\n{evaluator_feedback}\n\n"
                "Please produce a corrected analysis using the tool, addressing each issue. "
                "Ensure all quotes are verbatim from the provided excerpts."
            )),
        ]
    else:
        messages = [
            SystemMessage(content=_COMPLIANCE_SYSTEM_PROMPT),
            HumanMessage(content=first_user_message),
        ]

    logger.info(
        "compliance_agent_llm_call",
        trace_id=trace_id,
        question_id=question.id,
        question_title=question.title,
        num_contract_chunks=len(retrieved_chunks),
        num_act_chunks=len(act_chunks or []),
        is_retry=retry_count > 0,
        retry_count=retry_count,
        model=active_model,
    )

    response = invoke_with_retry(llm_with_tools, messages)

    duration_ms = (time.perf_counter() - t0) * 1000
    input_tokens = response.usage_metadata.get("input_tokens", 0)
    output_tokens = response.usage_metadata.get("output_tokens", 0)

    logger.info(
        "compliance_agent_llm_complete",
        trace_id=trace_id,
        question_id=question.id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        duration_ms=round(duration_ms, 2),
    )

    result = _parse_and_validate(response, question, trace_id)

    logger.info(
        "compliance_agent_complete",
        trace_id=trace_id,
        question_id=question.id,
        compliance_state=result.compliance_state.value,
        confidence=result.confidence,
        num_contract_quotes=len(result.contract_quotes),
        num_act_quotes=len(result.act_quotes),
        act_sections_cited=result.act_sections_cited,
        sub_criteria_coverage=f"{result.sub_criteria_coverage:.0%}",
    )

    return {
        "compliance_result": result,
        "compliance_latency_ms": round(duration_ms, 2),
        "llm_input_tokens": input_tokens,
        "llm_output_tokens": output_tokens,
    }


# ─────────────────────────────────────────────
# Prompt formatting helpers
# ─────────────────────────────────────────────

def _format_contract_chunks(chunks: List[dict]) -> str:
    if not chunks:
        return "No relevant contract excerpts were retrieved for this question."

    parts = []
    for i, chunk in enumerate(chunks, 1):
        section = chunk.get("section_title") or "Unknown Section"
        pages = chunk.get("page_numbers") or ""
        page_str = f" (page {pages})" if pages else ""
        text = chunk.get("text", "").strip()
        parts.append(f"[Contract Excerpt {i} | {section}{page_str}]\n{text}")

    return "\n\n---\n\n".join(parts)


def _format_act_chunks(chunks: List[dict]) -> str:
    if not chunks:
        return "No ESA act excerpts were retrieved for this question."

    parts = []
    for i, chunk in enumerate(chunks, 1):
        section = chunk.get("section_title") or chunk.get("metadata", {}).get("title", "ESA")
        text = chunk.get("text", "").strip()
        parts.append(f"[ESA Act Excerpt {i} | {section}]\n{text}")

    return "\n\n---\n\n".join(parts)


def _format_sub_criteria(question: ESAComplianceQuestion) -> str:
    lines = []
    for sc in question.sub_criteria:
        esa_ref = f" [{sc.esa_section}]" if sc.esa_section else ""
        lines.append(f"  [{sc.id}]{esa_ref} {sc.description}")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Output parsing and validation
# ─────────────────────────────────────────────

def _parse_and_validate(
    response: Any,
    question: ESAComplianceQuestion,
    trace_id: str,
) -> ComplianceResult:
    if not response.tool_calls:
        raise ValueError(
            f"No tool_calls in response for question {question.id} — "
            "unexpected API response structure"
        )

    raw_args = response.tool_calls[0]["args"]
    if isinstance(raw_args, str):
        try:
            data = json.loads(raw_args)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Tool call args is not valid JSON for question {question.id}: {exc}"
            ) from exc
    else:
        data = raw_args

    try:
        quotes = []
        for q in data.get("relevant_quotes", []):
            if isinstance(q, str):
                if q.strip():
                    quotes.append(RelevantQuote(text=q, section_reference="Unknown", source="contract"))
            elif isinstance(q, dict) and q.get("text", "").strip():
                quotes.append(RelevantQuote(
                    text=q["text"],
                    section_reference=q.get("section_reference", "Unknown"),
                    page_number=q.get("page_number"),
                    source=q.get("source", "contract"),
                ))

        sc_results = []
        for sc in data.get("sub_criteria_results", []):
            if isinstance(sc, dict):
                sc_results.append(SubCriterionResult(
                    criterion_id=sc.get("criterion_id", "unknown"),
                    description=sc.get("description", ""),
                    found=bool(sc.get("found", False)),
                    evidence_summary=sc.get("evidence_summary", ""),
                    esa_section=sc.get("esa_section", ""),
                ))

        state = ComplianceState(data["compliance_state"])
        confidence = max(0.0, min(1.0, float(data["confidence"])))

        return ComplianceResult(
            question_id=question.id,
            question_title=question.title,
            compliance_question=question.full_text,
            compliance_state=state,
            confidence=confidence,
            relevant_quotes=quotes,
            rationale=data["rationale"],
            sub_criteria_results=sc_results,
            retry_count=0,
            act_sections_cited=data.get("act_sections_cited", []),
            gap_summary=data.get("gap_summary", ""),
            esa_parts=question.esa_parts,
        )

    except (KeyError, TypeError, AttributeError) as exc:
        logger.error(
            "compliance_result_build_error",
            trace_id=trace_id,
            question_id=question.id,
            error=str(exc),
        )
        raise ValueError(
            f"Failed to build ComplianceResult for question {question.id}: {exc}"
        ) from exc
