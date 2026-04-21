#!/usr/bin/env python3
"""
Live log monitor for Contract Analyzer.

Tails logs/app.jsonl in real time, filters noise, and prints clean colored output.

Usage:
    python tools/log_live.py                   # default log file
    python tools/log_live.py --file logs/app.jsonl
    python tools/log_live.py --trace <trace_id>   # filter to one trace
    python tools/log_live.py --verbose            # include HTTP polling lines
"""

import argparse
import json
import sys
import time
from pathlib import Path

# ── ANSI colours ──────────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"

BLACK   = "\033[30m"
RED     = "\033[31m"
GREEN   = "\033[32m"
YELLOW  = "\033[33m"
BLUE    = "\033[34m"
MAGENTA = "\033[35m"
CYAN    = "\033[36m"
WHITE   = "\033[37m"

BG_RED    = "\033[41m"
BG_GREEN  = "\033[42m"
BG_YELLOW = "\033[43m"
BG_BLUE   = "\033[44m"

# ── Noise filter ──────────────────────────────────────────────────────────────

NOISY_LOGGERS = {
    "matplotlib.font_manager",
    "matplotlib",
    "httpx",
    "huggingface_hub.utils._http",
    "huggingface_hub",
    "sentence_transformers.base.model",
    "sentence_transformers",
    "unstructured",
    "unstructured.nlp.tokenize",
    "unstructured_inference",
    "pikepdf._core",
}

NOISY_EVENTS = {
    "http_request_start",
    "http_request_end",
}

# ── Pipeline stage definitions ────────────────────────────────────────────────

STAGE_MAP = {
    # Startup
    "api_startup_complete":      ("STARTUP",    CYAN,    "🚀"),
    "metrics_db_initialized":    ("STARTUP",    DIM,     "💾"),
    # Ingestion
    "analysis_job_created":      ("JOB",        BLUE,    "📋"),
    "analysis_pipeline_start":   ("PIPELINE",   BLUE,    "▶ "),
    "pdf_parse_start":           ("PARSE",      YELLOW,  "📄"),
    "pdf_parse_complete":        ("PARSE",      YELLOW,  "📄"),
    "chunking_complete":         ("CHUNK",      YELLOW,  "✂ "),
    "embedding_model_loading":   ("EMBED",      MAGENTA, "🔢"),
    "embedding_model_ready":     ("EMBED",      MAGENTA, "🔢"),
    "embedding_complete":        ("EMBED",      MAGENTA, "🔢"),
    "chromadb_client_ready":     ("INDEX",      MAGENTA, "🗄 "),
    "chunks_indexed":            ("INDEX",      MAGENTA, "🗄 "),
    # Router agent
    "router_llm_call_start":     ("ROUTER",     CYAN,    "🔀"),
    "router_llm_call_complete":  ("ROUTER",     CYAN,    "🔀"),
    "router_query_plan":         ("ROUTER",     BOLD+CYAN, "🔀"),
    # Compliance agent
    "compliance_agent_llm_call": ("COMPLIANCE", GREEN,   "🤖"),
    "compliance_agent_complete": ("COMPLIANCE", GREEN,   "🤖"),
    # Evaluator
    "evaluator_complete":        ("EVALUATOR",  BOLD+YELLOW, "🧐"),
    # Pipeline end
    "analysis_pipeline_complete":("DONE",       BOLD+GREEN,  "✅"),
    "analysis_job_failed":       ("ERROR",      BOLD+RED,    "❌"),
    # Errors
    "analysis_job_error":        ("ERROR",      BOLD+RED,    "❌"),
}

LEVEL_COLOR = {
    "debug":   DIM,
    "info":    WHITE,
    "warning": YELLOW,
    "error":   RED,
    "critical": BG_RED + WHITE,
}


def format_extras(entry: dict) -> str:
    """Pick the most interesting fields to show after the event name."""
    skip = {"event", "logger", "level", "timestamp", "trace_id", "span_id", "request_id"}
    parts = []
    priority = ["question_id", "question_title", "duration_ms", "total_chunks",
                "total_elements", "num_chunks", "confidence", "verdict",
                "compliance_state", "retry_count", "hallucination_flags",
                "status_code", "error", "filename", "model",
                "total_input_tokens", "total_output_tokens", "estimated_cost_usd"]
    shown = set()
    for key in priority:
        if key in entry and key not in skip:
            val = entry[key]
            if key == "duration_ms":
                val = f"{val/1000:.2f}s"
            elif key == "estimated_cost_usd":
                val = f"${val:.4f}"
            elif key == "confidence":
                val = f"{val:.0%}"
            parts.append(f"{DIM}{key}{RESET}={CYAN}{val}{RESET}")
            shown.add(key)
    for key, val in entry.items():
        if key not in skip and key not in shown and not isinstance(val, (dict, list)):
            parts.append(f"{DIM}{key}{RESET}={val}")
    return "  ".join(parts)


def render_line(entry: dict, trace_filter: str | None, verbose: bool) -> str | None:
    logger   = entry.get("logger", "")
    event    = entry.get("event", "")
    level    = entry.get("level", "info").lower()
    ts       = entry.get("timestamp", "")[:19].replace("T", " ")
    trace_id = entry.get("trace_id", "")
    short_tid = trace_id[:8] if trace_id else "--------"

    # Trace filter
    if trace_filter and trace_id and not trace_id.startswith(trace_filter):
        return None

    # Noise filter
    if not verbose:
        if any(logger.startswith(n) for n in NOISY_LOGGERS):
            return None
        if event in NOISY_EVENTS:
            return None

    # Look up stage styling
    stage, color, emoji = STAGE_MAP.get(event, ("SYS", DIM, "  "))

    # Level colour override for errors
    if level in ("error", "critical", "warning") and level != "info":
        color = LEVEL_COLOR.get(level, WHITE)

    extras = format_extras(entry)

    stage_str  = f"{color}{stage:<11}{RESET}"
    time_str   = f"{DIM}{ts}{RESET}"
    tid_str    = f"{DIM}[{short_tid}]{RESET}"
    event_str  = f"{color}{BOLD}{emoji} {event}{RESET}"

    return f"{time_str} {tid_str} {stage_str} {event_str}  {extras}"


def tail_file(path: Path, trace_filter: str | None, verbose: bool) -> None:
    print(f"\n{BOLD}{CYAN}Contract Analyzer — Live Log Monitor{RESET}")
    print(f"{DIM}Watching: {path}   |   Ctrl+C to stop{RESET}")
    if trace_filter:
        print(f"{YELLOW}Filtering to trace: {trace_filter}{RESET}")
    print("─" * 100)

    with open(path, "r", encoding="utf-8") as f:
        f.seek(0, 2)  # seek to end for live tail
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                print(f"{DIM}{line}{RESET}")
                continue

            rendered = render_line(entry, trace_filter, verbose)
            if rendered:
                print(rendered, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Live log monitor for Contract Analyzer")
    parser.add_argument("--file", default="logs/app.jsonl", help="Path to log file")
    parser.add_argument("--trace", default=None, help="Filter to a specific trace_id prefix")
    parser.add_argument("--verbose", action="store_true", help="Include HTTP polling and library noise")
    args = parser.parse_args()

    log_path = Path(args.file)
    if not log_path.exists():
        print(f"{RED}Log file not found: {log_path}{RESET}")
        print(f"{DIM}Start the API server first:  uvicorn backend.api.main:app --reload{RESET}")
        sys.exit(1)

    try:
        tail_file(log_path, args.trace, args.verbose)
    except KeyboardInterrupt:
        print(f"\n{DIM}Monitor stopped.{RESET}")


if __name__ == "__main__":
    main()
