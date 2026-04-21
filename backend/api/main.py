"""
FastAPI application entry point.

Configures:
- Logging (structlog)
- CORS
- API key authentication middleware
- Route registration
- Startup/shutdown lifecycle

Run with:
    uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from backend.observability.logger import configure_logging, get_logger
from backend.observability.metrics_store import init_db

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    logger.info("api_startup_complete", version="1.0.0")
    yield
    # Shutdown
    logger.info("api_shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Contract Analyzer API",
        description=(
            "Production-grade contract compliance analysis using Agentic RAG. "
            "Analyses PDF contracts against 5 compliance requirements and returns "
            "structured JSON with confidence scores, verbatim quotes, and rationale."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # tighten in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request logging middleware ─────────────────────────────────────────
    @app.middleware("http")
    async def log_requests(request: Request, call_next) -> Response:
        import time, uuid
        request_id = str(uuid.uuid4())[:8]
        t0 = time.perf_counter()
        logger.info(
            "http_request_start",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(
            "http_request_end",
            request_id=request_id,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response

    # ── Routes ────────────────────────────────────────────────────────────
    from backend.api.routes import router as api_router
    app.include_router(api_router, prefix="/api/v1")

    # ── Health check ──────────────────────────────────────────────────────
    @app.get("/health", tags=["Operations"])
    async def health():
        return {"status": "ok", "service": "contract-analyzer"}

    return app


app = create_app()
