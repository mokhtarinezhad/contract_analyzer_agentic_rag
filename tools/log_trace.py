#!/usr/bin/env python3
"""
Trace inspector for Contract Analyzer.

Replays a full analysis trace chronologically with clean, narrated output.
Perfect for walking through exactly what the system did during a demo or presentation.

Usage:
    python tools/log_trace.py                        # list recent traces
    python tools/log_trace.py <trace_id_or_prefix>   # full trace walkthrough
    python tools/log_trace.py --file logs/app.jsonl <trace_id>
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

# ── ANSI colours ──────────────────────────────────────────────────────────────

RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
RED     = "\033[31m"
GREEN   = "\033[32m"
YELLOW  = "\033[33m"
BLUE    = "\033[34m"
MAGENTA = "\033[35m"
CYAN    = "\033[36m"
WHITE   = "\033[37m"
BG_RED  = "\033[41m"
BG_GREEN = "\033[42m"

# ── Stage grouping ────────────────────────────────────────────────────────────

STAGES = [
    ("📋  JOB CREATED",       ["analysis_job_created"]),
    ("📄  PDF PARSING",        ["pdf_parse_start", "pdf_parse_complete"]),
    ("✂   CHUNKING",           ["chunking_complete"]),
    ("🔢  EMBEDDING",          ["embedding_model_loading", "embedding_model_ready",
                                "embedding_complete"]),
    ("🗄   INDEXING",           ["chromadb_client_ready", "chunks_indexed"]),
    ("🔀  ROUTER AGENT",       ["router_llm_call_start", "router_llm_call_complete",
                                "router_query_plan"]),
    ("🤖  COMPLIANCE AGENT",   ["compliance_agent_llm_call", "compliance_agent_complete",
                                "compliance_agent_start"]),
    ("🧐  EVALUATOR",          ["evaluator_complete", "evaluator_start",
                                "evaluator_llm_call"]),
    ("✅  PIPELINE COMPLETE",  ["analysis_pipeline_complete"]),
    ("❌  ERRORS",             ["analysis_job_failed", "analysis_job_error",
                                "compliance_agent_error", "evaluator_error"]),
]

COMPLIANCE_STATES = {
    "Fully Compliant":    f"{BG_GREEN}{BOLD} FULLY COMPLIANT    {RESET}",
    "Partially Compliant": f"{YELLOW}{BOLD} PARTIALLY COMPLIANT {RESET}",
    "Non-Compliant":      f"{BG_RED}{BOLD} NON-COMPLIANT       {RESET}",
    "Unable to Determine": f"{DIM} UNABLE TO DETERMINE {RESET}",
}

VERDICT_STYLE = {
    "PASS":            f"{GREEN}{BOLD}PASS{RESET}",
    "PASS_WITH_FLAGS": f"{YELLOW}{BOLD}PASS WITH FLAGS{RESET}",
    "FAIL":            f"{RED}{BOLD}FAIL{RESET}",
}


def load_trace(path: Path, trace_prefix: str) -> list[dict]:
    events = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            tid = entry.get("trace_id", "")
            if tid and tid.startswith(trace_prefix):
                events.append(entry)
    return sorted(events, key=lambda e: e.get("timestamp", ""))


def list_recent_traces(path: Path, n: int = 10) -> None:
    traces: dict[str, dict] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            tid = entry.get("trace_id")
            if not tid:
                continue
            if tid not in traces:
                traces[tid] = {"first_ts": entry.get("timestamp", ""), "filename": "", "events": 0}
            traces[tid]["events"] += 1
            if entry.get("filename"):
                traces[tid]["filename"] = entry["filename"]

    if not traces:
        print(f"{YELLOW}No traces found in log file.{RESET}")
        return

    recent = sorted(traces.items(), key=lambda x: x[1]["first_ts"], reverse=True)[:n]
    print(f"\n{BOLD}Recent traces (most recent first):{RESET}\n")
    print(f"  {'TRACE ID':<38} {'STARTED':<20} {'FILE':<30} {'EVENTS'}")
    print("  " + "─" * 95)
    for tid, info in recent:
        ts = info["first_ts"][:19].replace("T", " ")
        fn = info["filename"][:28] or "(unknown)"
        print(f"  {CYAN}{tid}{RESET}  {DIM}{ts}{RESET}  {fn:<30}  {info['events']}")
    print(f"\n{DIM}Run:  python tools/log_trace.py <trace_id>{RESET}\n")


def render_event(entry: dict) -> None:
    event   = entry.get("event", "")
    ts      = entry.get("timestamp", "")[:19].replace("T", " ")
    level   = entry.get("level", "info").lower()
    span_id = entry.get("span_id", "")

    time_str = f"{DIM}{ts}{RESET}"
    span_str = f"{DIM}[{span_id or '--------'}]{RESET}" if span_id else "          "

    # Special rendering for key events
    if event == "pdf_parse_complete":
        chunks   = entry.get("total_elements", "?")
        tables   = entry.get("table_count", "?")
        titles   = entry.get("title_count", "?")
        dur      = entry.get("duration_ms", 0) / 1000
        print(f"  {time_str} {span_str}  {YELLOW}pdf_parse_complete{RESET}")
        print(f"    {DIM}→ {chunks} elements  ({tables} tables, {titles} section titles)  in {dur:.1f}s{RESET}")

    elif event == "chunking_complete":
        total = entry.get("total_chunks", "?")
        tables = entry.get("table_chunks", "?")
        text   = entry.get("text_chunks", "?")
        avg    = entry.get("avg_words", 0)
        print(f"  {time_str} {span_str}  {YELLOW}chunking_complete{RESET}")
        print(f"    {DIM}→ {total} chunks  ({tables} table chunks, {text} text chunks)  avg {avg:.0f} words/chunk{RESET}")

    elif event == "embedding_complete":
        n   = entry.get("num_texts", "?")
        dim = entry.get("embedding_dim", "?")
        dur = entry.get("duration_ms", 0) / 1000
        print(f"  {time_str} {span_str}  {MAGENTA}embedding_complete{RESET}")
        print(f"    {DIM}→ {n} texts embedded  dim={dim}  in {dur:.1f}s{RESET}")

    elif event == "chunks_indexed":
        n   = entry.get("num_chunks", "?")
        dur = entry.get("duration_ms", 0) / 1000
        print(f"  {time_str} {span_str}  {MAGENTA}chunks_indexed{RESET}")
        print(f"    {DIM}→ {n} chunks written to ChromaDB  in {dur:.1f}s{RESET}")

    elif event == "router_llm_call_start":
        qid   = entry.get("question_id", "?")
        title = entry.get("question_title", "")
        model = entry.get("model", "")
        print(f"  {time_str} {span_str}  {CYAN}router_llm_call_start{RESET}  "
              f"Q{qid}: {BOLD}{title}{RESET}  {DIM}model={model}{RESET}")

    elif event == "router_query_plan":
        qid    = entry.get("question_id", "?")
        title  = entry.get("question_title", "")
        plan   = entry.get("query_plan") or entry.get("sub_queries") or entry.get("plan") or {}
        print(f"  {time_str} {span_str}  {BOLD}{CYAN}router_query_plan{RESET}  Q{qid}: {BOLD}{title}{RESET}")
        if isinstance(plan, dict):
            for k, v in plan.items():
                print(f"    {DIM}→ [{k}] {v}{RESET}")
        elif isinstance(plan, list):
            for item in plan:
                print(f"    {DIM}→ {item}{RESET}")
        else:
            print(f"    {DIM}→ {plan}{RESET}")

    elif event == "router_llm_call_complete":
        qid  = entry.get("question_id", "?")
        dur  = entry.get("duration_ms", 0) / 1000
        toks = entry.get("input_tokens", 0)
        print(f"  {time_str} {span_str}  {CYAN}router_llm_call_complete{RESET}  "
              f"Q{qid}  {DIM}{dur:.2f}s  tokens_in={toks}{RESET}")

    elif event in ("compliance_agent_llm_call", "compliance_agent_start"):
        qid     = entry.get("question_id", "?")
        title   = entry.get("question_title", "")
        retry   = entry.get("retry_count", 0)
        retry_s = f"  {YELLOW}[retry #{retry}]{RESET}" if retry else ""
        print(f"  {time_str} {span_str}  {GREEN}compliance_agent_llm_call{RESET}  "
              f"Q{qid}: {BOLD}{title}{RESET}{retry_s}")

    elif event == "compliance_agent_complete":
        qid   = entry.get("question_id", "?")
        state = entry.get("compliance_state", "")
        conf  = entry.get("confidence", 0)
        dur   = entry.get("duration_ms", 0) / 1000
        badge = COMPLIANCE_STATES.get(state, state)
        print(f"  {time_str} {span_str}  {GREEN}compliance_agent_complete{RESET}  "
              f"Q{qid}  {badge}  conf={BOLD}{conf:.0%}{RESET}  {DIM}{dur:.2f}s{RESET}")

    elif event == "evaluator_complete":
        qid      = entry.get("question_id", "?")
        title    = entry.get("question_title", "")
        verdict  = entry.get("verdict", "")
        conf_adj = entry.get("confidence_adjustment", None)
        hall_raw  = entry.get("hallucination_flags", [])
        retry     = entry.get("retry_count", 0)
        verdict_s = VERDICT_STYLE.get(verdict, f"{BOLD}{verdict}{RESET}")
        conf_s    = f"  {DIM}conf_adj={conf_adj:+.0%}{RESET}" if conf_adj is not None else ""
        hall_count = hall_raw if isinstance(hall_raw, int) else len(hall_raw)
        hall_s    = f"  {RED}hallucination_flags={hall_count}{RESET}" if hall_count else ""
        retry_s   = f"  {YELLOW}retries={retry}{RESET}" if retry else ""
        print(f"  {time_str} {span_str}  {BOLD}{YELLOW}evaluator_complete{RESET}  "
              f"Q{qid}: {title}  →  {verdict_s}{conf_s}{hall_s}{retry_s}")
        if isinstance(hall_raw, list) and hall_raw:
            for flag in hall_raw:
                print(f"    {RED}⚠  {flag}{RESET}")

    elif event == "analysis_pipeline_complete":
        dur   = entry.get("total_duration_ms", 0) / 1000
        cost  = entry.get("estimated_cost_usd", 0)
        tin   = entry.get("total_input_tokens", 0)
        tout  = entry.get("total_output_tokens", 0)
        retry = entry.get("total_retry_count", 0)
        print(f"\n  {time_str}  {BG_GREEN}{BOLD} PIPELINE COMPLETE {RESET}")
        print(f"    {DIM}duration   : {RESET}{BOLD}{dur:.1f}s{RESET}")
        print(f"    {DIM}cost       : {RESET}{BOLD}${cost:.4f}{RESET}")
        print(f"    {DIM}tokens     : {RESET}in={tin:,}  out={tout:,}")
        print(f"    {DIM}retries    : {RESET}{retry}")

    elif event in ("analysis_job_failed", "analysis_job_error"):
        err = entry.get("error", "unknown error")
        print(f"  {time_str} {span_str}  {BG_RED}{BOLD} FAILED {RESET}  {RED}{err}{RESET}")

    else:
        # Generic fallback
        skip  = {"event", "logger", "level", "timestamp", "trace_id", "span_id", "request_id"}
        extra = {k: v for k, v in entry.items() if k not in skip and not isinstance(v, (dict, list))}
        extra_s = "  ".join(f"{DIM}{k}={RESET}{v}" for k, v in extra.items())
        color = RED if level in ("error", "critical") else (YELLOW if level == "warning" else DIM)
        print(f"  {time_str} {span_str}  {color}{event}{RESET}  {extra_s}")


def render_trace(events: list[dict], trace_id: str) -> None:
    print(f"\n{BOLD}{'═'*100}{RESET}")
    print(f"{BOLD}  CONTRACT ANALYZER — TRACE WALKTHROUGH{RESET}")
    print(f"  {DIM}trace_id: {RESET}{CYAN}{trace_id}{RESET}")

    if events:
        t_start = events[0].get("timestamp", "")[:19].replace("T", " ")
        t_end   = events[-1].get("timestamp", "")[:19].replace("T", " ")
        print(f"  {DIM}started:  {RESET}{t_start}   {DIM}ended: {RESET}{t_end}")

    print(f"{BOLD}{'═'*100}{RESET}\n")

    # Group events by stage for section headers
    by_event = {e.get("event", ""): e for e in events}
    printed_stages: set[str] = set()

    stage_for_event: dict[str, str] = {}
    for stage_label, stage_events in STAGES:
        for ev in stage_events:
            stage_for_event[ev] = stage_label

    current_stage = None
    for entry in events:
        ev = entry.get("event", "")
        stage = stage_for_event.get(ev)

        if stage and stage != current_stage:
            current_stage = stage
            print(f"\n  {BOLD}{BLUE}── {stage} {'─'*(90-len(stage))}{RESET}")

        render_event(entry)

    # Summary table of compliance results
    comp_events = [e for e in events if e.get("event") == "evaluator_complete"]
    if comp_events:
        print(f"\n  {BOLD}{BLUE}── COMPLIANCE SUMMARY {'─'*77}{RESET}")
        print(f"  {'Q':<4} {'Question':<45} {'Verdict':<20} {'Conf Adj':<10} {'Retries'}")
        print("  " + "─" * 95)
        for e in sorted(comp_events, key=lambda x: x.get("question_id", 0)):
            qid     = e.get("question_id", "?")
            title   = (e.get("question_title") or "")[:43]
            verdict = e.get("verdict", "")
            conf_adj = e.get("confidence_adjustment", 0) or 0
            retries  = e.get("retry_count", 0)
            verdict_s = VERDICT_STYLE.get(verdict, verdict)
            cadj_s = f"{conf_adj:+.0%}" if conf_adj else "—"
            retry_s = f"{RED}{retries}{RESET}" if retries else "0"
            print(f"  Q{qid:<3} {title:<45} {verdict_s:<20} {cadj_s:<10} {retry_s}")

    print(f"\n{BOLD}{'═'*100}{RESET}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Trace inspector for Contract Analyzer")
    parser.add_argument("trace_id", nargs="?", default=None,
                        help="trace_id or prefix (e.g. first 8 chars). Omit to list recent traces.")
    parser.add_argument("--file", default="logs/app.jsonl", help="Path to log file")
    parser.add_argument("--list", "-l", action="store_true", help="List recent traces")
    args = parser.parse_args()

    log_path = Path(args.file)
    if not log_path.exists():
        print(f"{RED}Log file not found: {log_path}{RESET}")
        sys.exit(1)

    if args.trace_id is None or args.list:
        list_recent_traces(log_path)
        return

    events = load_trace(log_path, args.trace_id)
    if not events:
        print(f"{RED}No events found for trace prefix: {args.trace_id}{RESET}")
        print(f"{DIM}Run without arguments to list available traces.{RESET}")
        sys.exit(1)

    full_trace_id = events[0].get("trace_id", args.trace_id)
    render_trace(events, full_trace_id)


if __name__ == "__main__":
    main()
