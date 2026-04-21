"""
Structured JSON logging via structlog.

Every log event is emitted as a single JSON line with:
  - timestamp (ISO-8601)
  - level
  - trace_id   (per-request UUID, correlates all spans for one analysis)
  - span_id    (per-operation UUID)
  - event      (short snake_case label)
  - logger     (module name)
  - + arbitrary key-value context fields

Usage:
    from backend.observability.logger import get_logger
    logger = get_logger(__name__)
    logger.info("embedding_complete", trace_id=tid, duration_ms=123.4)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import structlog

_configured = False


def _ensure_log_dir(log_path: str) -> None:
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)


def configure_logging(
    log_level: str | None = None,
    log_file: str | None = None,
) -> None:
    """
    Call once at application startup (api/main.py or app.py).
    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _configured
    if _configured:
        return

    from backend.config import settings
    level_str = (log_level or settings.log_level).upper()
    level = getattr(logging, level_str, logging.INFO)

    log_file = log_file or settings.log_file_path
    _ensure_log_dir(log_file)

    # Shared processors applied to every log event
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # File handler — JSON lines
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setLevel(level)

    # Console handler — human-readable during dev
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    logging.basicConfig(
        format="%(message)s",
        level=level,
        handlers=[file_handler, console_handler],
    )

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Attach JSON renderer to stdlib handlers
    json_renderer = structlog.processors.JSONRenderer()

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=json_renderer,
        foreign_pre_chain=shared_processors,
    )

    for handler in logging.root.handlers:
        handler.setFormatter(formatter)

    _configured = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to the given module name."""
    configure_logging()  # idempotent
    return structlog.get_logger(name)


# ─────────────────────────────────────────────
# Trace / Span context helpers
# ─────────────────────────────────────────────

import uuid
import contextlib


def new_trace_id() -> str:
    return str(uuid.uuid4())


def new_span_id() -> str:
    return str(uuid.uuid4())[:8]


@contextlib.contextmanager
def log_span(
    logger_: Any,
    event: str,
    trace_id: str,
    **extra: Any,
):
    """
    Context manager that logs span start and end with duration.

    Usage:
        with log_span(logger, "llm_call", trace_id=tid, question_id=1) as span:
            result = call_llm(...)
    """
    import time

    span_id = new_span_id()
    t0 = time.perf_counter()

    logger_.debug(f"{event}_start", trace_id=trace_id, span_id=span_id, **extra)

    try:
        yield {"trace_id": trace_id, "span_id": span_id}
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger_.info(
            f"{event}_end",
            trace_id=trace_id,
            span_id=span_id,
            duration_ms=duration_ms,
            **extra,
        )
    except Exception as exc:
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger_.error(
            f"{event}_error",
            trace_id=trace_id,
            span_id=span_id,
            duration_ms=duration_ms,
            error=str(exc),
            **extra,
        )
        raise
