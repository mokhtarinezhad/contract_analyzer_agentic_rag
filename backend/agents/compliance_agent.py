"""
Compliance Agent.

Given the retrieved chunks from the Router Agent, this agent:
  1. Analyses all sub-criteria against the retrieved evidence.
  2. Determines the compliance state (Fully / Partially / Non-Compliant).
  3. Extracts verbatim quotes with section references.
  4. Provides a calibrated confidence score.
  5. Returns a structured ComplianceResult.

Output is validated by Pydantic before being passed to the Evaluator Agent.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from backend.compliance.questions import ComplianceQuestion
from backend.compliance.schemas import (
    ComplianceResult,
    ComplianceState,
    RelevantQuote,
    SubCriterionResult,
)
from backend.config import settings
from backend.observability.logger import get_logger

logger = get_logger(__name__)

_COMPLIANCE_SYSTEM_PROMPT = """You are a senior compliance analyst reviewing a security contract.
You will be given:
1. A compliance requirement with specific sub-criteria.
2. Relevant contract excerpts retrieved from the document.

Your task:
- Evaluate EACH sub-criterion against the provided contract text.
- Determine the overall compliance state.
- Extract VERBATIM quotes from the provided contract text only — do NOT paraphrase or invent text.
- Assign a calibrated confidence score (0.0–1.0) reflecting certainty of your determination.

Compliance state rules:
- "Fully Compliant": ALL sub-criteria are clearly addressed in the contract language.
- "Partially Compliant": SOME but not all sub-criteria are addressed, OR language is ambiguous.
- "Non-Compliant": Key sub-criteria are absent or explicitly excluded.

Confidence calibration:
- 0.90–1.00: Explicit, unambiguous contract language directly addressing all/most criteria.
- 0.70–0.89: Clear language but some gaps or minor ambiguity.
- 0.50–0.69: Implied coverage or significant ambiguity.
- Below 0.50: Very weak or absent evidence.

You must call the submit_compliance_result tool with your analysis. Do not return plain text.
"""

# Tool schema — the LLM is forced to call this, guaranteeing valid structured output
_COMPLIANCE_TOOL = {
    "name": "submit_compliance_result",
    "description": "Submit the structured compliance analysis result.",
    "input_schema": {
        "type": "object",
        "properties": {
            "compliance_state": {
                "type": "string",
                "enum": ["Fully Compliant", "Partially Compliant", "Non-Compliant"],
                "description": "Overall compliance state for this requirement.",
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Calibrated confidence score (0.0–1.0).",
            },
            "rationale": {
                "type": "string",
                "description": "Detailed reasoning referencing specific contract language and each sub-criterion.",
            },
            "relevant_quotes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Exact verbatim quote from the contract."},
                        "section_reference": {"type": "string", "description": "Section or exhibit reference."},
                        "page_number": {"type": ["integer", "null"]},
                    },
                    "required": ["text", "section_reference"],
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
                        "evidence_summary": {"type": "string"},
                    },
                    "required": ["criterion_id", "description", "found", "evidence_summary"],
                },
            },
        },
        "required": ["compliance_state", "confidence", "rationale", "relevant_quotes", "sub_criteria_results"],
    },
}


def run_compliance_agent(
    question: ComplianceQuestion,
    retrieved_chunks: List[dict],
    trace_id: str,
    evaluator_feedback: Optional[str] = None,
    previous_result: Optional[ComplianceResult] = None,
    retry_count: int = 0,
) -> Dict[str, Any]:
    """
    Run the compliance analysis for one question.

    Args:
        question:           The ComplianceQuestion being analysed.
        retrieved_chunks:   Chunks from the Router Agent.
        trace_id:           Logging correlation.
        evaluator_feedback: If this is a retry, the evaluator's critique.
        previous_result:    The ComplianceResult from the previous attempt (for retry context).
        retry_count:        Current retry attempt number.

    Returns:
        Dict containing a validated ComplianceResult plus token usage.
    """
    t0 = time.perf_counter()
    llm = ChatAnthropic(model=settings.llm_model, max_tokens=2048, api_key=settings.anthropic_api_key)
    llm_with_tools = llm.bind_tools(
        [_COMPLIANCE_TOOL],
        tool_choice={"type": "tool", "name": "submit_compliance_result"},
    )

    context_text = _format_chunks_for_prompt(retrieved_chunks)
    sub_criteria_text = _format_sub_criteria(question)

    first_user_message = (
        f"## Compliance Requirement: {question.title}\n\n"
        f"**Full requirement:**\n{question.full_text}\n\n"
        f"**Sub-criteria to evaluate:**\n{sub_criteria_text}\n\n"
        f"## Retrieved Contract Excerpts\n\n{context_text}"
    )

    # Build multi-turn conversation on retry so the LLM sees its previous answer
    if evaluator_feedback and previous_result:
        messages = [
            SystemMessage(content=_COMPLIANCE_SYSTEM_PROMPT),
            HumanMessage(content=first_user_message),
            AIMessage(content=json.dumps(previous_result.model_dump(mode="json"), indent=2)),
            HumanMessage(content=(
                f"## Evaluator Feedback\n\n"
                f"Your previous analysis was flagged with these issues:\n{evaluator_feedback}\n\n"
                "Please produce a corrected analysis using the tool, addressing each issue above."
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
        num_chunks=len(retrieved_chunks),
        is_retry=retry_count > 0,
        retry_count=retry_count,
        model=settings.llm_model,
    )

    response = llm_with_tools.invoke(messages)

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
        num_quotes=len(result.relevant_quotes),
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

def _format_chunks_for_prompt(chunks: List[dict]) -> str:
    """Format retrieved chunks as numbered, labelled context."""
    if not chunks:
        return "No relevant contract excerpts were retrieved."

    parts = []
    for i, chunk in enumerate(chunks, 1):
        section = chunk.get("section_title") or "Unknown Section"
        pages = chunk.get("page_numbers") or ""
        page_str = f" (page {pages})" if pages else ""
        text = chunk.get("text", "").strip()
        parts.append(f"[Excerpt {i} | {section}{page_str}]\n{text}")

    return "\n\n---\n\n".join(parts)


def _format_sub_criteria(question: ComplianceQuestion) -> str:
    lines = []
    for sc in question.sub_criteria:
        lines.append(f"  [{sc.id}] {sc.description}")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Output parsing and validation
# ─────────────────────────────────────────────

def _parse_and_validate(
    response: Any,
    question: ComplianceQuestion,
    trace_id: str,
) -> ComplianceResult:
    """Extract the tool call result and build a validated ComplianceResult.

    Because we use tool_choice=forced, the API guarantees a tool_use block
    with schema-valid input. Any exception here is a code bug, not an LLM
    formatting issue.
    """
    # LangChain surfaces tool calls via response.tool_calls — guaranteed present
    # because we used tool_choice forcing
    if not response.tool_calls:
        raise ValueError(
            f"No tool_calls in response for question {question.id} — "
            "unexpected API response structure (code bug, not LLM output)"
        )

    raw_args = response.tool_calls[0]["args"]
    # LangChain may return args as a JSON string or a dict depending on version
    if isinstance(raw_args, str):
        try:
            data = json.loads(raw_args)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Tool call args is a string but not valid JSON for question {question.id}: {exc}"
            ) from exc
    else:
        data = raw_args

    try:
        quotes = [
            RelevantQuote(
                text=q["text"],
                section_reference=q.get("section_reference", "Unknown"),
                page_number=q.get("page_number"),
            )
            for q in data.get("relevant_quotes", [])
            if q.get("text", "").strip()
        ]

        sc_results = [
            SubCriterionResult(
                criterion_id=sc["criterion_id"],
                description=sc["description"],
                found=bool(sc["found"]),
                evidence_summary=sc["evidence_summary"],
            )
            for sc in data.get("sub_criteria_results", [])
        ]

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
        )

    except (KeyError, TypeError, AttributeError) as exc:
        logger.error(
            "compliance_result_build_error",
            trace_id=trace_id,
            question_id=question.id,
            error=str(exc),
        )
        raise ValueError(
            f"Failed to build ComplianceResult for question {question.id}: {exc} "
            "(code bug — tool schema mismatch)"
        ) from exc
