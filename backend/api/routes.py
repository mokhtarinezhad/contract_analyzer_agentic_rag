"""
API route handlers.

Endpoints:
  POST /analyze            — Upload PDF, start async analysis, return job_id
  GET  /results/{job_id}   — Poll for analysis results
  GET  /jobs               — List all jobs (for debugging)
  GET  /metrics/summary    — KPI summary for dashboard
  GET  /metrics/history    — Historical trends
  POST /chat               — Conversational query over uploaded contract
  DELETE /contracts/{id}   — Clean up a contract's vector store
"""

from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from backend.agents.orchestrator import analyse_contract
from backend.llm_factory import ALL_MODELS, DEFAULT_MODEL, get_llm
from backend.compliance.schemas import (
    ChatRequest,
    ChatResponse,
    ContractAnalysisResponse,
    JobStatus,
    RelevantQuote,
)
from backend.observability.logger import get_logger, new_trace_id
from backend.observability.metrics_store import (
    create_job,
    create_law_reference,
    delete_law_reference,
    get_analyses_df,
    get_compliance_distribution_df,
    get_confidence_trend_df,
    get_job,
    get_kpi_summary,
    get_latency_trend_df,
    get_law_reference,
    get_question_results_df,
    list_jobs,
    list_law_references,
    update_job,
)
from backend.rag.vector_store import delete_collection, delete_law_collection, safe_law_collection_name

logger = get_logger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────
# Analysis endpoints
# ─────────────────────────────────────────────

@router.post(
    "/analyze",
    summary="Upload a PDF contract and start compliance analysis",
    response_description="Job ID for polling results",
)
async def analyze_contract_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF contract file"),
    model: str = Form(DEFAULT_MODEL, description="LLM model to use for analysis"),
    law_id: str = Form("", description="Law library ID to check against (empty = default ESA)"),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    if model not in ALL_MODELS:
        model = DEFAULT_MODEL

    # Resolve the law collection name
    law_collection_name: str | None = None
    if law_id:
        law_ref = get_law_reference(law_id)
        if law_ref is None:
            raise HTTPException(status_code=404, detail=f"Law '{law_id}' not found in library")
        if law_ref["status"] != "ready":
            raise HTTPException(status_code=400, detail=f"Law '{law_id}' is not ready (status: {law_ref['status']})")
        law_collection_name = law_ref["collection_name"]

    job_id = str(uuid.uuid4())
    trace_id = new_trace_id()
    contract_id = str(uuid.uuid4())

    create_job(
        job_id=job_id,
        trace_id=trace_id,
        contract_id=contract_id,
        filename=file.filename,
        status=JobStatus.PENDING.value,
    )

    # Save PDF to temp file
    pdf_content = await file.read()
    tmp_dir = Path(tempfile.gettempdir()) / "contract_analyzer"
    tmp_dir.mkdir(exist_ok=True)
    pdf_path = str(tmp_dir / f"{contract_id}.pdf")
    with open(pdf_path, "wb") as f:
        f.write(pdf_content)

    logger.info(
        "analysis_job_created",
        job_id=job_id,
        trace_id=trace_id,
        filename=file.filename,
        law_id=law_id or "default",
        size_bytes=len(pdf_content),
    )

    # Run analysis in background
    background_tasks.add_task(
        _run_analysis_background,
        job_id=job_id,
        pdf_path=pdf_path,
        filename=file.filename,
        contract_id=contract_id,
        trace_id=trace_id,
        model=model,
        law_collection_name=law_collection_name,
    )

    return {
        "job_id": job_id,
        "trace_id": trace_id,
        "contract_id": contract_id,
        "status": JobStatus.PENDING.value,
        "law_id": law_id or "default",
        "message": f"Analysis started. Poll GET /api/v1/results/{job_id} for status.",
    }


async def _run_analysis_background(
    job_id: str,
    pdf_path: str,
    filename: str,
    contract_id: str,
    trace_id: str,
    model: str = DEFAULT_MODEL,
    law_collection_name: str | None = None,
) -> None:
    """Background task that runs the full analysis pipeline."""
    _valid_statuses = {s.value for s in JobStatus}

    async def _update_job(status: str, pct: int):
        resolved = status if status in _valid_statuses else JobStatus.ANALYZING.value
        update_job(
            job_id=job_id,
            status=resolved,
            progress_pct=pct,
            current_step=status,
        )

    async def _on_question_complete(partial_results, done: int, total: int, pct: int):
        partial_payload = {
            "results": [r.model_dump(mode="json") for r in partial_results],
            "partial": True,
            "completed_count": done,
            "total_count": total,
            "processing_metadata": {},
        }
        update_job(
            job_id=job_id,
            status=JobStatus.ANALYZING.value,
            progress_pct=pct,
            current_step=f"analyzed_{done}_of_{total}",
            result_json=json.dumps(partial_payload, default=str),
        )

    try:
        await _update_job(JobStatus.PARSING_PDF.value, 5)

        result: ContractAnalysisResponse = await analyse_contract(
            pdf_path=pdf_path,
            filename=filename,
            contract_id=contract_id,
            trace_id=trace_id,
            job_update_callback=_update_job,
            on_question_complete=_on_question_complete,
            model=model,
            law_collection_name=law_collection_name,
        )

        update_job(
            job_id=job_id,
            status=JobStatus.COMPLETED.value,
            progress_pct=100,
            current_step=JobStatus.COMPLETED.value,
            result_json=json.dumps(result.model_dump(mode="json"), default=str),
        )

        logger.info(
            "analysis_job_completed",
            job_id=job_id,
            trace_id=trace_id,
        )

    except Exception as exc:
        logger.error(
            "analysis_job_failed",
            job_id=job_id,
            trace_id=trace_id,
            error=str(exc),
        )
        update_job(
            job_id=job_id,
            status=JobStatus.FAILED.value,
            error_message=str(exc),
        )


@router.get(
    "/results/{job_id}",
    summary="Poll for analysis results",
)
async def get_results(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    response = {
        "job_id": job["job_id"],
        "trace_id": job["trace_id"],
        "status": job["status"],
        "progress_pct": job.get("progress_pct") or 0,
        "current_step": job.get("current_step") or "",
        "filename": job["filename"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
    }

    if job["status"] == JobStatus.FAILED.value and job.get("error_message"):
        response["error"] = job["error_message"]

    # Return result for completed jobs, and partial results for in-progress jobs
    if job.get("result_json"):
        response["result"] = json.loads(job["result_json"])

    return JSONResponse(content=response)


@router.get("/jobs", summary="List all analysis jobs")
async def list_jobs_endpoint(limit: int = 50):
    return [
        {
            "job_id": j["job_id"],
            "filename": j["filename"],
            "status": j["status"],
            "progress_pct": j.get("progress_pct") or 0,
            "created_at": j["created_at"],
        }
        for j in list_jobs(limit=limit)
    ]


@router.delete("/contracts/{contract_id}", summary="Clean up a contract's vector store")
async def delete_contract(contract_id: str):
    delete_collection(contract_id)
    return {"message": f"Contract '{contract_id}' removed from vector store"}


# ─────────────────────────────────────────────
# Law library endpoints
# ─────────────────────────────────────────────

@router.get("/laws", summary="List all law references (all statuses)")
async def list_laws():
    return list_law_references(ready_only=False)


@router.post("/laws", summary="Upload and index a law reference PDF")
async def upload_law(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Law PDF file"),
    law_id: str = Form(..., description="Unique identifier, e.g. ontario-law-2026"),
    display_name: str = Form(..., description="Human-readable label shown in the UI"),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Sanitise law_id
    import re
    law_id_clean = re.sub(r"[^a-zA-Z0-9\-]", "-", law_id).strip("-")[:60]
    if not law_id_clean:
        raise HTTPException(status_code=400, detail="law_id must contain at least one alphanumeric character")

    pdf_content = await file.read()
    tmp_dir = Path(tempfile.gettempdir()) / "contract_analyzer" / "laws"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = str(tmp_dir / f"{law_id_clean}.pdf")
    with open(pdf_path, "wb") as f:
        f.write(pdf_content)

    trace_id = new_trace_id()

    logger.info("law_upload_received", law_id=law_id_clean, display_name=display_name,
                filename=file.filename, size_bytes=len(pdf_content), trace_id=trace_id)

    # Run ingestion in background so the HTTP response returns immediately
    from backend.ingestion.law_ingestor import ingest_law_pdf
    background_tasks.add_task(
        _run_law_ingestion_background,
        pdf_path=pdf_path,
        law_id=law_id_clean,
        display_name=display_name,
        filename=file.filename,
        trace_id=trace_id,
    )

    return {
        "law_id": law_id_clean,
        "display_name": display_name,
        "status": "indexing",
        "collection_name": safe_law_collection_name(law_id_clean),
        "message": "Law PDF accepted and indexing started. Poll GET /api/v1/laws to check status.",
    }


async def _run_law_ingestion_background(
    pdf_path: str,
    law_id: str,
    display_name: str,
    filename: str,
    trace_id: str,
) -> None:
    from backend.ingestion.law_ingestor import ingest_law_pdf
    from backend.observability.metrics_store import update_law_reference
    try:
        ingest_law_pdf(
            pdf_path=pdf_path,
            law_id=law_id,
            display_name=display_name,
            filename=filename,
            trace_id=trace_id,
        )
    except Exception as exc:
        logger.error("law_ingestion_failed", law_id=law_id, error=str(exc))
        update_law_reference(law_id=law_id, status="failed")


@router.get("/laws/{law_id}", summary="Get a single law reference")
async def get_law(law_id: str):
    law = get_law_reference(law_id)
    if law is None:
        raise HTTPException(status_code=404, detail=f"Law '{law_id}' not found")
    return law


@router.delete("/laws/{law_id}", summary="Remove a law reference and its vector store")
async def delete_law(law_id: str):
    law = get_law_reference(law_id)
    if law is None:
        raise HTTPException(status_code=404, detail=f"Law '{law_id}' not found")
    delete_law_collection(law_id)
    delete_law_reference(law_id)
    return {"message": f"Law '{law_id}' removed"}


# ─────────────────────────────────────────────
# Metrics endpoints
# ─────────────────────────────────────────────

@router.get("/metrics/summary", summary="KPI summary for dashboard")
async def metrics_summary():
    return get_kpi_summary()


@router.get("/metrics/history", summary="Historical analysis data")
async def metrics_history(days: int = 30):
    analyses_df = get_analyses_df(limit=200)
    latency_df = get_latency_trend_df(days=days)
    confidence_df = get_confidence_trend_df(days=days)
    distribution_df = get_compliance_distribution_df()

    return {
        "analyses": analyses_df.to_dict(orient="records"),
        "latency_trend": latency_df.to_dict(orient="records"),
        "confidence_trend": confidence_df.to_dict(orient="records"),
        "compliance_distribution": distribution_df.to_dict(orient="records"),
    }


@router.get("/metrics/questions", summary="Per-question result history")
async def metrics_questions():
    df = get_question_results_df()
    return df.to_dict(orient="records")


# ─────────────────────────────────────────────
# Chat endpoint (bonus feature)
# ─────────────────────────────────────────────

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Conversational query over an uploaded contract",
)
async def chat_with_contract(request: ChatRequest):
    """
    Allow free-form questions about the uploaded contract content.
    Uses the same vector store indexed during analysis.
    """
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
    from backend.config import settings
    from backend.ingestion.embedder import embed_query
    from backend.rag.vector_store import semantic_search

    trace_id = new_trace_id()

    logger.info(
        "chat_request",
        trace_id=trace_id,
        contract_id=request.contract_id,
        message_preview=request.message[:80],
    )

    query_vec = embed_query(request.message)
    chunks = semantic_search(
        contract_id=request.contract_id,
        query_embedding=query_vec,
        top_k=5,
        trace_id=trace_id,
    )

    context = "\n\n---\n\n".join(
        f"[{c.get('section_title', 'Contract')}]\n{c['text']}"
        for c in chunks
    )

    lc_messages = [
        SystemMessage(content=(
            "You are a contract analysis assistant. Answer questions strictly based on the "
            "provided contract excerpts. If information is not in the excerpts, say so clearly. "
            "Always reference the specific section when citing contract language."
        ))
    ]
    for m in request.history[-6:]:
        if m.role == "user":
            lc_messages.append(HumanMessage(content=m.content))
        else:
            lc_messages.append(AIMessage(content=m.content))

    lc_messages.append(HumanMessage(content=(
        f"Based on the following contract excerpts, please answer this question:\n\n"
        f"Question: {request.message}\n\n"
        f"Contract excerpts:\n{context}"
    )))

    llm = get_llm(settings.llm_model, max_tokens=1024)
    response = llm.invoke(lc_messages)
    reply = response.content

    sources = [
        RelevantQuote(
            text=c["text"][:200] + ("..." if len(c["text"]) > 200 else ""),
            section_reference=c.get("section_title") or "Unknown",
            page_number=None,
        )
        for c in chunks[:3]
    ]

    return ChatResponse(reply=reply, sources=sources, trace_id=trace_id)
