"""
Central configuration — committed to git.

Contains all non-secret settings with their defaults.
Change values here to tune behaviour across deployments.

Secrets (ANTHROPIC_API_KEY) live in .env only and are never committed.

Usage:
    from backend.config import settings
    model = settings.llm_model
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── LLM ──────────────────────────────────────────────────────────────
    anthropic_api_key: str = ""  # loaded from .env — never commit the value
    openai_api_key: str = ""     # loaded from .env — never commit the value
    llm_model: str = "claude-sonnet-4-6"
    # Options: claude-sonnet-4-6 | claude-opus-4-7 | claude-haiku-4-5-20251001
    #          gpt-4o | gpt-4o-mini | gpt-4-turbo

    # ── PDF Parsing ───────────────────────────────────────────────────────
    pdf_parse_strategy: str = "hi_res"
    # Options: hi_res (deep learning + OCR) | fast (pdfminer, no layout) | auto
    pdf_ocr_enabled: bool = False
    pdf_ocr_language: str = "eng"
    # ISO 639-2 language code(s), e.g. "eng", "eng+fra"

    # ── Embeddings ────────────────────────────────────────────────────────
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_model_cache_dir: str = "./data/models"

    # ── Vector Store ──────────────────────────────────────────────────────
    chroma_persist_dir: str = "./data/chroma_db"

    # ── Metrics / Logging ─────────────────────────────────────────────────
    metrics_db_path: str = "./data/metrics.db"
    log_file_path: str = "./logs/app.jsonl"
    log_level: str = "INFO"

    # ── FastAPI ───────────────────────────────────────────────────────────
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # ── Evaluator thresholds ──────────────────────────────────────────────
    evaluator_min_confidence: float = 0.60
    max_retry_count: int = 2
    hallucination_match_threshold: float = 0.80

    # ── ESA Reference Knowledge Base ─────────────────────────────────────
    esa_act_collection_name: str = "eao-act-reference"

    # ── MCP Server ────────────────────────────────────────────────────────
    mcp_server_host: str = "127.0.0.1"
    mcp_server_port: int = 8001
    api_base_url: str = "http://localhost:8000/api/v1"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
