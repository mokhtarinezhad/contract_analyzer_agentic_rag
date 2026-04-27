"""
LangGraph Orchestrator — ESA Employment Contract Compliance Pipeline.

Pipeline:
  1. Parse PDF
  2. Chunk + Embed + Index (contract)
  3. Classify contract → select applicable ESA questions
  4. Run applicable questions concurrently (Router → Compliance → Evaluator)
  5. Collect, validate, and persist results

Graph topology (per question):
  START → router → compliance → evaluator ─┬─(PASS/PASS_WITH_FLAGS)─→ END
                                            └─(FAIL, retry < max)────→ compliance
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from backend.agents.classifier_agent import run_classifier_agent
from backend.agents.compliance_agent import run_compliance_agent
from backend.agents.evaluator_agent import run_evaluator_agent
from backend.agents.router_agent import run_router_agent
from backend.compliance.eao_questions import ESAComplianceQuestion, get_question_by_id
from backend.compliance.schemas import (
    ComplianceResult,
    ComplianceState,
    ContractAnalysisResponse,
    ProcessingMetadata,
)
from backend.config import settings
from backend.ingestion.chunker import DocumentChunk, chunk_elements
from backend.ingestion.embedder import embed_texts
from backend.ingestion.pdf_parser import parse_pdf
from backend.observability.logger import get_logger, new_trace_id
from backend.observability.metrics_store import (
    init_db,
    record_agent_span,
    record_analysis,
    record_question_result,
)
from backend.rag.vector_store import delete_collection, index_chunks

logger = get_logger(__name__)

_MAX_RETRIES = settings.max_retry_count

_MODEL_COSTS: Dict[str, tuple[float, float]] = {
    "claude-opus-4-7":           (15e-6, 75e-6),
    "claude-sonnet-4-6":         (3e-6,  15e-6),
    "claude-haiku-4-5-20251001": (1e-6,  5e-6),
    "gpt-4o":                    (2.5e-6, 10e-6),
    "gpt-4o-mini":               (0.15e-6, 0.6e-6),
    "gpt-4-turbo":               (10e-6,  30e-6),
}
_DEFAULT_COSTS = (3e-6, 15e-6)


def _cost_for_model(model_name: str) -> tuple[float, float]:
    return _MODEL_COSTS.get(model_name, _DEFAULT_COSTS)


# ─────────────────────────────────────────────
# Per-question LangGraph state
# ─────────────────────────────────────────────

class QuestionState(TypedDict):
    question: ESAComplianceQuestion
    contract_id: str
    trace_id: str
    model: str
    act_collection_name: str        # which law collection to query
    # Router output
    retrieved_chunks: List[dict]    # contract chunks
    act_chunks: List[dict]          # law act chunks
    sub_criterion_queries: List[dict]
    router_latency_ms: float
    # Compliance agent output
    compliance_result: Optional[ComplianceResult]
    compliance_latency_ms: float
    # Evaluator output
    should_retry: bool
    retry_feedback: str
    evaluator_latency_ms: float
    # Retry tracking
    retry_count: int
    # Token accumulator
    total_input_tokens: int
    total_output_tokens: int


# ─────────────────────────────────────────────
# LangGraph node functions
# ─────────────────────────────────────────────

def _router_node(state: QuestionState) -> QuestionState:
    result = run_router_agent(
        question=state["question"],
        contract_id=state["contract_id"],
        trace_id=state["trace_id"],
        model=state.get("model"),
        act_collection_name=state.get("act_collection_name") or None,
    )
    state["retrieved_chunks"] = result["retrieved_chunks"]
    state["act_chunks"] = result.get("act_chunks", [])
    state["sub_criterion_queries"] = result["sub_criterion_queries"]
    state["router_latency_ms"] = result["router_latency_ms"]
    state["total_input_tokens"] += result["llm_input_tokens"]
    state["total_output_tokens"] += result["llm_output_tokens"]

    record_agent_span(
        trace_id=state["trace_id"],
        agent_name="router",
        duration_ms=result["router_latency_ms"],
        question_id=state["question"].id,
    )
    return state


def _compliance_node(state: QuestionState) -> QuestionState:
    is_retry = state["retry_count"] > 0
    result = run_compliance_agent(
        question=state["question"],
        retrieved_chunks=state["retrieved_chunks"],
        act_chunks=state["act_chunks"],
        trace_id=state["trace_id"],
        evaluator_feedback=state.get("retry_feedback") if is_retry else None,
        previous_result=state.get("compliance_result") if is_retry else None,
        retry_count=state["retry_count"],
        model=state.get("model"),
    )
    cr: ComplianceResult = result["compliance_result"]
    cr = cr.model_copy(update={"retry_count": state["retry_count"]})
    state["compliance_result"] = cr
    state["compliance_latency_ms"] = result["compliance_latency_ms"]
    state["total_input_tokens"] += result["llm_input_tokens"]
    state["total_output_tokens"] += result["llm_output_tokens"]

    record_agent_span(
        trace_id=state["trace_id"],
        agent_name="compliance",
        duration_ms=result["compliance_latency_ms"],
        question_id=state["question"].id,
    )
    return state


def _evaluator_node(state: QuestionState) -> QuestionState:
    cr = state["compliance_result"]
    result = run_evaluator_agent(
        compliance_result=cr,
        retrieved_chunks=state["retrieved_chunks"],
        act_chunks=state["act_chunks"],
        question_full_text=state["question"].full_text,
        sub_criteria_descriptions=[sc.description for sc in state["question"].sub_criteria],
        trace_id=state["trace_id"],
        model=state.get("model"),
    )
    state["compliance_result"] = result["updated_result"]
    state["should_retry"] = result["should_retry"] and state["retry_count"] < _MAX_RETRIES
    state["retry_feedback"] = result["retry_feedback"]
    state["evaluator_latency_ms"] = result["evaluator_latency_ms"]
    state["total_input_tokens"] += result["llm_input_tokens"]
    state["total_output_tokens"] += result["llm_output_tokens"]

    if result["should_retry"] and state["retry_count"] < _MAX_RETRIES:
        state["retry_count"] += 1

    record_agent_span(
        trace_id=state["trace_id"],
        agent_name="evaluator",
        duration_ms=result["evaluator_latency_ms"],
        question_id=state["question"].id,
    )
    return state


def _should_retry(state: QuestionState) -> str:
    if state.get("should_retry", False):
        return "retry"
    return "done"


# ─────────────────────────────────────────────
# Build the per-question graph
# ─────────────────────────────────────────────

def _build_question_graph() -> Any:
    builder = StateGraph(QuestionState)

    builder.add_node("router", _router_node)
    builder.add_node("compliance", _compliance_node)
    builder.add_node("evaluator", _evaluator_node)

    builder.set_entry_point("router")
    builder.add_edge("router", "compliance")
    builder.add_edge("compliance", "evaluator")

    builder.add_conditional_edges(
        "evaluator",
        _should_retry,
        {
            "retry": "compliance",
            "done": END,
        },
    )

    return builder.compile()


_question_graph = None


def _get_question_graph():
    global _question_graph
    if _question_graph is None:
        _question_graph = _build_question_graph()
    return _question_graph


# ─────────────────────────────────────────────
# Run one question
# ─────────────────────────────────────────────

async def _run_single_question(
    question: ESAComplianceQuestion,
    contract_id: str,
    trace_id: str,
    model: str = "",
    act_collection_name: str = "",
) -> QuestionState:
    initial_state: QuestionState = {
        "question": question,
        "contract_id": contract_id,
        "trace_id": trace_id,
        "model": model or settings.llm_model,
        "act_collection_name": act_collection_name or settings.esa_act_collection_name,
        "retrieved_chunks": [],
        "act_chunks": [],
        "sub_criterion_queries": [],
        "router_latency_ms": 0.0,
        "compliance_result": None,
        "compliance_latency_ms": 0.0,
        "should_retry": False,
        "retry_feedback": "",
        "evaluator_latency_ms": 0.0,
        "retry_count": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
    }

    graph = _get_question_graph()

    loop = asyncio.get_event_loop()
    final_state = await loop.run_in_executor(
        None, lambda: graph.invoke(initial_state)
    )

    cr = final_state.get("compliance_result")
    if cr:
        record_question_result(
            trace_id=trace_id,
            question_id=question.id,
            question_title=question.title,
            compliance_state=cr.compliance_state.value,
            confidence=cr.confidence,
            retry_count=final_state.get("retry_count", 0),
            evaluator_verdict=(
                cr.evaluator_assessment.verdict.value
                if cr.evaluator_assessment else None
            ),
            hallucination_flags=len(
                cr.evaluator_assessment.hallucination_flags
                if cr.evaluator_assessment else []
            ),
            sub_criteria_coverage=cr.sub_criteria_coverage,
        )

    return final_state


# ─────────────────────────────────────────────
# Main entry point: full pipeline
# ─────────────────────────────────────────────

async def analyse_contract(
    pdf_path: str,
    filename: str,
    contract_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    job_update_callback=None,
    on_question_complete=None,
    model: Optional[str] = None,
    law_collection_name: Optional[str] = None,
) -> ContractAnalysisResponse:
    """
    Full end-to-end ESA compliance pipeline:
      PDF → parse → chunk → embed → index → classify → (N×parallel agents) → validate → return

    Args:
        pdf_path:             Path to the uploaded PDF.
        filename:             Original filename (for display).
        contract_id:          Unique ID for this contract (generated if None).
        trace_id:             Trace ID for logging (generated if None).
        job_update_callback:  Optional async callable(status, pct) for UI progress.
        model:                LLM model override.

    Returns:
        ContractAnalysisResponse with results for all applicable ESA questions.
    """
    init_db()

    if trace_id is None:
        trace_id = new_trace_id()
    if contract_id is None:
        contract_id = str(uuid.uuid4())

    logger.info(
        "analysis_pipeline_start",
        trace_id=trace_id,
        contract_id=contract_id,
        filename=filename,
    )

    pipeline_t0 = time.perf_counter()
    timings: Dict[str, float] = {}
    total_input_tokens = 0
    total_output_tokens = 0

    async def _update(status: str, pct: int) -> None:
        if job_update_callback:
            await job_update_callback(status, pct)

    # ── Step 1: Parse PDF ──────────────────────────────────────────────────
    await _update("parsing_pdf", 5)
    t = time.perf_counter()
    elements = parse_pdf(pdf_path, trace_id=trace_id)
    timings["pdf_parse_ms"] = (time.perf_counter() - t) * 1000

    # ── Step 2: Chunk ──────────────────────────────────────────────────────
    await _update("chunking", 15)
    chunks: List[DocumentChunk] = chunk_elements(elements, trace_id=trace_id)
    if not chunks:
        raise ValueError("PDF produced no text chunks — ensure the file is a text-based PDF")

    # ── Step 3: Embed ──────────────────────────────────────────────────────
    await _update("embedding", 25)
    t = time.perf_counter()
    texts = [c.embedding_text if c.embedding_text else c.text for c in chunks]
    embeddings = embed_texts(texts, trace_id=trace_id)
    timings["embedding_ms"] = (time.perf_counter() - t) * 1000

    # ── Step 4: Index in vector store ─────────────────────────────────────
    await _update("indexing", 35)
    t = time.perf_counter()
    index_chunks(
        contract_id=contract_id,
        chunks=chunks,
        embeddings=embeddings,
        trace_id=trace_id,
    )
    timings["retrieval_ms"] = (time.perf_counter() - t) * 1000

    # ── Step 5: Classify — determine applicable ESA questions ─────────────
    await _update("classifying", 42)
    active_model = model or settings.llm_model

    classifier_result = run_classifier_agent(
        contract_id=contract_id,
        trace_id=trace_id,
        model=active_model,
    )
    applicable_ids: List[str] = classifier_result["applicable_question_ids"]
    total_input_tokens += classifier_result["llm_input_tokens"]
    total_output_tokens += classifier_result["llm_output_tokens"]

    applicable_questions: List[ESAComplianceQuestion] = []
    for qid in applicable_ids:
        try:
            applicable_questions.append(get_question_by_id(qid))
        except ValueError:
            logger.warning("unknown_question_id", question_id=qid, trace_id=trace_id)

    skipped_count = len([]) # total ESA questions - applicable
    from backend.compliance.eao_questions import get_all_questions
    all_q_count = len(get_all_questions())
    skipped_count = all_q_count - len(applicable_questions)

    logger.info(
        "classification_complete",
        trace_id=trace_id,
        applicable_count=len(applicable_questions),
        skipped_count=skipped_count,
        conditional_triggered=classifier_result["conditional_triggered_ids"],
    )

    # ── Step 6: Run all applicable questions in parallel ──────────────────
    await _update("retrieving", 48)
    t = time.perf_counter()

    active_law_collection = law_collection_name or settings.esa_act_collection_name
    semaphore = asyncio.Semaphore(settings.max_concurrent_questions)
    total_questions = len(applicable_questions)

    async def _run_with_semaphore(q):
        async with semaphore:
            return await _run_single_question(
                q, contract_id, trace_id,
                model=active_model,
                act_collection_name=active_law_collection,
            )

    # ── Step 7: Collect results as each question finishes ─────────────────
    results: List[ComplianceResult] = []
    eval_ms_total = 0.0
    done_count = 0

    futs = [asyncio.ensure_future(_run_with_semaphore(q)) for q in applicable_questions]
    for fut in asyncio.as_completed(futs):
        state = await fut
        done_count += 1

        cr = state.get("compliance_result")
        if cr is None:
            q = state["question"]
            cr = ComplianceResult(
                question_id=q.id,
                question_title=q.title,
                compliance_question=q.full_text,
                compliance_state=ComplianceState.UNABLE_TO_DETERMINE,
                confidence=0.0,
                relevant_quotes=[],
                rationale="Pipeline error — manual review required.",
                gap_summary="Unable to complete analysis due to pipeline error.",
                esa_parts=q.esa_parts,
            )
        results.append(cr)
        total_input_tokens += state.get("total_input_tokens", 0)
        total_output_tokens += state.get("total_output_tokens", 0)
        eval_ms_total += state.get("evaluator_latency_ms", 0)

        # Fire partial-result callback so the UI can show incremental progress
        if on_question_complete:
            pct = 48 + int((done_count / total_questions) * 40)
            await on_question_complete(list(results), done_count, total_questions, pct)

    timings["llm_ms"] = (time.perf_counter() - t) * 1000
    timings["evaluation_ms"] = eval_ms_total
    total_duration_ms = (time.perf_counter() - pipeline_t0) * 1000

    in_cost, out_cost = _cost_for_model(active_model)
    estimated_cost = total_input_tokens * in_cost + total_output_tokens * out_cost
    avg_confidence = sum(r.confidence for r in results) / max(len(results), 1)

    logger.info(
        "analysis_pipeline_complete",
        trace_id=trace_id,
        contract_id=contract_id,
        total_duration_ms=round(total_duration_ms, 2),
        questions_analyzed=len(results),
        questions_skipped=skipped_count,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        estimated_cost_usd=round(estimated_cost, 4),
        avg_confidence=round(avg_confidence, 3),
        **{k: round(v, 2) for k, v in timings.items()},
    )

    # ── Step 8: Persist metrics ────────────────────────────────────────────
    import json as _json

    _response_obj = ContractAnalysisResponse(
        contract_id=contract_id,
        trace_id=trace_id,
        filename=filename,
        results=results,
        processing_metadata=ProcessingMetadata(
            trace_id=trace_id,
            total_duration_ms=total_duration_ms,
            pdf_parse_duration_ms=timings.get("pdf_parse_ms", 0),
            embedding_duration_ms=timings.get("embedding_ms", 0),
            retrieval_duration_ms=timings.get("retrieval_ms", 0),
            llm_duration_ms=timings.get("llm_ms", 0),
            evaluation_duration_ms=timings.get("evaluation_ms", 0),
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            estimated_cost_usd=estimated_cost,
            retry_count=sum(s.get("retry_count", 0) for s in question_states),
            model_used=active_model,
            chunks_retrieved_per_question=len(chunks),
            questions_analyzed=len(results),
            questions_skipped=skipped_count,
        ),
    )

    record_analysis(
        trace_id=trace_id,
        contract_id=contract_id,
        filename=filename,
        total_duration_ms=total_duration_ms,
        pdf_parse_ms=timings.get("pdf_parse_ms", 0),
        embedding_ms=timings.get("embedding_ms", 0),
        retrieval_ms=timings.get("retrieval_ms", 0),
        llm_ms=timings.get("llm_ms", 0),
        evaluation_ms=timings.get("evaluation_ms", 0),
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        estimated_cost_usd=estimated_cost,
        model_used=active_model,
        retry_count=sum(s.get("retry_count", 0) for s in question_states),
        avg_confidence=avg_confidence,
        full_result_json=_json.dumps(_response_obj.model_dump(mode="json")),
    )

    await _update("completed", 100)
    return _response_obj
