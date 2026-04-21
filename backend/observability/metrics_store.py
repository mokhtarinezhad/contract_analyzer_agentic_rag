"""
SQLite-backed metrics store for KPI dashboard.

Tables:
  analyses           — one row per completed contract analysis
  question_results   — one row per compliance question per analysis (5 per analysis)
  agent_spans        — timing for each pipeline stage

All writes are async-safe via a threading.Lock.
Reads return pandas DataFrames for easy Streamlit charting.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from backend.config import settings
from backend.observability.logger import get_logger

logger = get_logger(__name__)

_lock = threading.Lock()


# ─────────────────────────────────────────────
# Schema DDL
# ─────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS analyses (
    trace_id            TEXT PRIMARY KEY,
    contract_id         TEXT NOT NULL,
    filename            TEXT NOT NULL,
    analysis_timestamp  TEXT NOT NULL,
    total_duration_ms   REAL,
    pdf_parse_ms        REAL,
    embedding_ms        REAL,
    retrieval_ms        REAL,
    llm_ms              REAL,
    evaluation_ms       REAL,
    total_input_tokens  INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    estimated_cost_usd  REAL DEFAULT 0.0,
    model_used          TEXT,
    retry_count         INTEGER DEFAULT 0,
    avg_confidence      REAL,
    status              TEXT DEFAULT 'completed'
);

CREATE TABLE IF NOT EXISTS question_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id        TEXT NOT NULL,
    question_id     INTEGER NOT NULL,
    question_title  TEXT NOT NULL,
    compliance_state TEXT NOT NULL,
    confidence      REAL NOT NULL,
    retry_count     INTEGER DEFAULT 0,
    evaluator_verdict TEXT,
    hallucination_flags INTEGER DEFAULT 0,
    sub_criteria_coverage REAL DEFAULT 0.0,
    FOREIGN KEY (trace_id) REFERENCES analyses(trace_id)
);

CREATE TABLE IF NOT EXISTS agent_spans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id    TEXT NOT NULL,
    span_id     TEXT,
    agent_name  TEXT NOT NULL,
    question_id INTEGER,
    duration_ms REAL,
    timestamp   TEXT NOT NULL,
    FOREIGN KEY (trace_id) REFERENCES analyses(trace_id)
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id         TEXT PRIMARY KEY,
    trace_id       TEXT NOT NULL,
    contract_id    TEXT,
    filename       TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending',
    progress_pct   INTEGER DEFAULT 0,
    current_step   TEXT DEFAULT '',
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    error_message  TEXT,
    result_json    TEXT
);

CREATE INDEX IF NOT EXISTS idx_analyses_timestamp  ON analyses(analysis_timestamp);
CREATE INDEX IF NOT EXISTS idx_qr_trace            ON question_results(trace_id);
CREATE INDEX IF NOT EXISTS idx_spans_trace         ON agent_spans(trace_id);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at     ON jobs(created_at);
"""

_MIGRATIONS = [
    "ALTER TABLE analyses ADD COLUMN full_result_json TEXT",
]


# ─────────────────────────────────────────────
# Connection helper
# ─────────────────────────────────────────────

def _get_db_path() -> str:
    Path(settings.metrics_db_path).parent.mkdir(parents=True, exist_ok=True)
    return settings.metrics_db_path


@contextmanager
def _conn():
    """Thread-safe SQLite connection context manager."""
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they don't exist. Safe to call multiple times."""
    with _lock, _conn() as conn:
        conn.executescript(_DDL)
        for migration in _MIGRATIONS:
            try:
                conn.execute(migration)
            except sqlite3.OperationalError:
                pass  # column already exists
    logger.info("metrics_db_initialized", path=_get_db_path())


# ─────────────────────────────────────────────
# Write operations
# ─────────────────────────────────────────────

def record_analysis(
    trace_id: str,
    contract_id: str,
    filename: str,
    total_duration_ms: float,
    pdf_parse_ms: float = 0,
    embedding_ms: float = 0,
    retrieval_ms: float = 0,
    llm_ms: float = 0,
    evaluation_ms: float = 0,
    total_input_tokens: int = 0,
    total_output_tokens: int = 0,
    estimated_cost_usd: float = 0.0,
    model_used: str = "",
    retry_count: int = 0,
    avg_confidence: float = 0.0,
    status: str = "completed",
    full_result_json: Optional[str] = None,
) -> None:
    with _lock, _conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO analyses (
                trace_id, contract_id, filename, analysis_timestamp,
                total_duration_ms, pdf_parse_ms, embedding_ms, retrieval_ms,
                llm_ms, evaluation_ms, total_input_tokens, total_output_tokens,
                estimated_cost_usd, model_used, retry_count, avg_confidence, status,
                full_result_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                trace_id, contract_id, filename,
                datetime.utcnow().isoformat(),
                total_duration_ms, pdf_parse_ms, embedding_ms, retrieval_ms,
                llm_ms, evaluation_ms, total_input_tokens, total_output_tokens,
                estimated_cost_usd, model_used, retry_count, avg_confidence, status,
                full_result_json,
            ),
        )


def record_question_result(
    trace_id: str,
    question_id: int,
    question_title: str,
    compliance_state: str,
    confidence: float,
    retry_count: int = 0,
    evaluator_verdict: Optional[str] = None,
    hallucination_flags: int = 0,
    sub_criteria_coverage: float = 0.0,
) -> None:
    with _lock, _conn() as conn:
        conn.execute(
            """
            INSERT INTO question_results (
                trace_id, question_id, question_title, compliance_state,
                confidence, retry_count, evaluator_verdict,
                hallucination_flags, sub_criteria_coverage
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                trace_id, question_id, question_title, compliance_state,
                confidence, retry_count, evaluator_verdict,
                hallucination_flags, sub_criteria_coverage,
            ),
        )


def record_agent_span(
    trace_id: str,
    agent_name: str,
    duration_ms: float,
    question_id: Optional[int] = None,
    span_id: Optional[str] = None,
) -> None:
    with _lock, _conn() as conn:
        conn.execute(
            """
            INSERT INTO agent_spans (trace_id, span_id, agent_name, question_id, duration_ms, timestamp)
            VALUES (?,?,?,?,?,?)
            """,
            (trace_id, span_id, agent_name, question_id, duration_ms, datetime.utcnow().isoformat()),
        )


# ─────────────────────────────────────────────
# Job persistence (replaces the in-memory _jobs dict)
# ─────────────────────────────────────────────

def create_job(
    job_id: str,
    trace_id: str,
    contract_id: str,
    filename: str,
    status: str = "pending",
) -> None:
    now = datetime.utcnow().isoformat()
    with _lock, _conn() as conn:
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, trace_id, contract_id, filename,
                status, progress_pct, current_step,
                created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (job_id, trace_id, contract_id, filename, status, 0, "", now, now),
        )


def update_job(
    job_id: str,
    status: Optional[str] = None,
    progress_pct: Optional[int] = None,
    current_step: Optional[str] = None,
    error_message: Optional[str] = None,
    result_json: Optional[str] = None,
) -> None:
    """Partial update — only non-None fields are written."""
    fields: list[str] = []
    values: list = []

    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if progress_pct is not None:
        fields.append("progress_pct = ?")
        values.append(progress_pct)
    if current_step is not None:
        fields.append("current_step = ?")
        values.append(current_step)
    if error_message is not None:
        fields.append("error_message = ?")
        values.append(error_message)
    if result_json is not None:
        fields.append("result_json = ?")
        values.append(result_json)

    if not fields:
        return

    fields.append("updated_at = ?")
    values.append(datetime.utcnow().isoformat())
    values.append(job_id)

    with _lock, _conn() as conn:
        conn.execute(
            f"UPDATE jobs SET {', '.join(fields)} WHERE job_id = ?",
            values,
        )


def get_job(job_id: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        return dict(row) if row else None


def list_jobs(limit: int = 50) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# Read operations — return DataFrames for Streamlit
# ─────────────────────────────────────────────

def get_analyses_df(limit: int = 100) -> pd.DataFrame:
    with _conn() as conn:
        return pd.read_sql_query(
            f"SELECT * FROM analyses ORDER BY analysis_timestamp DESC LIMIT {limit}",
            conn,
        )


def get_question_results_df(trace_id: Optional[str] = None) -> pd.DataFrame:
    with _conn() as conn:
        if trace_id:
            return pd.read_sql_query(
                "SELECT * FROM question_results WHERE trace_id = ?",
                conn,
                params=(trace_id,),
            )
        return pd.read_sql_query(
            "SELECT * FROM question_results ORDER BY id DESC LIMIT 500",
            conn,
        )


def get_kpi_summary() -> dict:
    """Aggregate KPIs for the dashboard summary cards."""
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*)                        AS total_analyses,
                AVG(total_duration_ms)          AS avg_latency_ms,
                AVG(estimated_cost_usd)         AS avg_cost_usd,
                SUM(estimated_cost_usd)         AS total_cost_usd,
                AVG(avg_confidence)             AS avg_confidence,
                AVG(retry_count)                AS avg_retry_rate,
                SUM(total_input_tokens)         AS total_input_tokens,
                SUM(total_output_tokens)        AS total_output_tokens
            FROM analyses
            WHERE status = 'completed'
            """
        ).fetchone()

        if row is None or row["total_analyses"] == 0:
            return {
                "total_analyses": 0,
                "avg_latency_ms": 0,
                "avg_cost_usd": 0,
                "total_cost_usd": 0,
                "avg_confidence": 0,
                "avg_retry_rate": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
            }

        evaluator_row = conn.execute(
            """
            SELECT
                AVG(CASE WHEN hallucination_flags > 0 THEN 1.0 ELSE 0.0 END) AS hallucination_rate,
                AVG(CASE WHEN retry_count > 0 THEN 1.0 ELSE 0.0 END)         AS retry_rate
            FROM question_results
            """
        ).fetchone()

        return {
            "total_analyses": row["total_analyses"],
            "avg_latency_ms": round(row["avg_latency_ms"] or 0, 1),
            "avg_cost_usd": round(row["avg_cost_usd"] or 0, 4),
            "total_cost_usd": round(row["total_cost_usd"] or 0, 4),
            "avg_confidence": round((row["avg_confidence"] or 0) * 100, 1),
            "avg_retry_rate": round((evaluator_row["retry_rate"] or 0) * 100, 1),
            "hallucination_rate": round((evaluator_row["hallucination_rate"] or 0) * 100, 1),
            "total_input_tokens": row["total_input_tokens"] or 0,
            "total_output_tokens": row["total_output_tokens"] or 0,
        }


def get_compliance_distribution_df() -> pd.DataFrame:
    """Distribution of compliance states per question — for bar/pie charts."""
    with _conn() as conn:
        return pd.read_sql_query(
            """
            SELECT question_title, compliance_state, COUNT(*) as count
            FROM question_results
            GROUP BY question_title, compliance_state
            ORDER BY question_title, compliance_state
            """,
            conn,
        )


def get_latency_trend_df(days: int = 30) -> pd.DataFrame:
    """Latency trend for line chart."""
    with _conn() as conn:
        return pd.read_sql_query(
            f"""
            SELECT
                date(analysis_timestamp)  AS date,
                AVG(total_duration_ms)    AS avg_latency_ms,
                MIN(total_duration_ms)    AS min_latency_ms,
                MAX(total_duration_ms)    AS max_latency_ms,
                COUNT(*)                  AS count
            FROM analyses
            WHERE analysis_timestamp >= datetime('now', '-{days} days')
            GROUP BY date(analysis_timestamp)
            ORDER BY date
            """,
            conn,
        )


def get_full_result(trace_id: str) -> Optional[str]:
    """Return the stored full_result_json for a given trace_id, or None."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT full_result_json FROM analyses WHERE trace_id = ?", (trace_id,)
        ).fetchone()
        return row["full_result_json"] if row else None


def get_confidence_trend_df(days: int = 30) -> pd.DataFrame:
    with _conn() as conn:
        return pd.read_sql_query(
            f"""
            SELECT
                date(a.analysis_timestamp)  AS date,
                q.question_title,
                AVG(q.confidence)           AS avg_confidence
            FROM question_results q
            JOIN analyses a ON a.trace_id = q.trace_id
            WHERE a.analysis_timestamp >= datetime('now', '-{days} days')
            GROUP BY date(a.analysis_timestamp), q.question_title
            ORDER BY date, q.question_title
            """,
            conn,
        )
