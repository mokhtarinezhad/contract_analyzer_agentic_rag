"""
Contract Analyzer — Streamlit Frontend

Pages (sidebar navigation):
  1. Analyze Contract   — Upload PDF, trigger analysis, show results
  2. KPI Dashboard      — Real-time + historical metrics
  3. Chat               — Free-form Q&A over uploaded contract (bonus)

Run with:
    streamlit run frontend/app.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# Add project root to path so backend imports resolve
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

from backend.observability.logger import configure_logging
from backend.observability.metrics_store import (
    get_analyses_df,
    get_compliance_distribution_df,
    get_confidence_trend_df,
    get_full_result,
    get_kpi_summary,
    get_latency_trend_df,
    get_question_results_df,
    init_db,
    list_law_references,
)

configure_logging()
init_db()

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")

# ─────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="Contract Analyzer | 247Labs",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        [data-testid="stSidebar"] { min-width: 320px; max-width: 320px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────
# Sidebar navigation
# ─────────────────────────────────────────────

with st.sidebar:
    st.image(str(Path(__file__).parent / "logo.jpeg"), use_container_width=True)
    st.markdown(
        """
        <div style="
            font-size: 1.45rem;
            font-weight: 900;
            letter-spacing: 0.5px;
            font-size: 1.7rem;
            color: #a855f7;
            text-shadow: 1px 1px 0px #6b21a8, 2px 2px 0px #581c87, 3px 3px 6px rgba(107,33,168,0.4);
            margin: 6px 0 2px 0;
            line-height: 1.2;
        ">Agentic RAG Demo</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div style="
            border-left: 3px solid #a855f7;
            padding: 6px 0 6px 10px;
            margin: 4px 0 0 0;
        ">
            <div style="font-size:0.65rem; color:#6b7280; letter-spacing:1.5px;
                        text-transform:uppercase; margin-bottom:2px;">
                Developed by
            </div>
            <div style="font-size:0.95rem; font-weight:700; color:#1e1b4b; line-height:1.2;">
                Farshid Mokhtarinezhad
            </div>
            <div style="font-size:0.72rem; color:#a855f7; font-weight:500; margin-top:1px;">
                Senior AI Engineer · 247Labs
            </div>
            <a href="mailto:farshid.mokhtarinezhad@247labs.com"
               style="display:inline-block; margin-top:5px; font-size:0.68rem;
                      color:#6b7280; text-decoration:none; letter-spacing:0.2px;">
                ✉ farshid.mokhtarinezhad@247labs.com
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    page = st.radio(
        "Navigate",
        ["Guide", "Law Library", "Analyze Contract", "KPI Dashboard", "Chat", "Process Monitor"],
        index=2,
    )

    st.divider()
    st.markdown(
        "<div style='font-size:0.65rem;color:#6b7280;letter-spacing:1.2px;"
        "text-transform:uppercase;margin-bottom:4px'>LLM Model</div>",
        unsafe_allow_html=True,
    )

    _MODEL_OPTIONS = {
        "claude-sonnet-4-6":         "Sonnet 4.6 — Balanced (default)",
        "claude-opus-4-7":           "Opus 4.7 — Most Capable",
        "claude-haiku-4-5-20251001": "Haiku 4.5 — Fastest",
        "gpt-4o":                    "GPT-4o — Most Capable",
        "gpt-4o-mini":               "GPT-4o Mini — Balanced",
        "gpt-4-turbo":               "GPT-4 Turbo — Advanced",
    }

    selected_model = st.selectbox(
        "model",
        options=list(_MODEL_OPTIONS.keys()),
        format_func=lambda k: _MODEL_OPTIONS[k],
        index=0,
        label_visibility="collapsed",
    )
    st.session_state["selected_model"] = selected_model

    provider = "Anthropic" if selected_model.startswith("claude") else "OpenAI"
    provider_color = "#a855f7" if provider == "Anthropic" else "#10b981"
    st.markdown(
        f"<div style='font-size:0.68rem;color:{provider_color};margin-top:2px'>"
        f"Provider: {provider}</div>",
        unsafe_allow_html=True,
    )

    st.divider()
    if st.session_state.get("job_running"):
        fname = st.session_state.get("job_filename", "")
        pct   = st.session_state.get("job_progress", {}).get("pct", 0)
        st.markdown(
            f"<div style='background:#1e3a1e;border-radius:6px;padding:8px 10px;margin-bottom:6px'>"
            f"<span style='color:#4ade80;font-size:0.75rem'>⏳ Analyzing…</span><br>"
            f"<span style='color:#e2e8f0;font-size:0.8rem'>{fname}</span><br>"
            f"<span style='color:#9ca3af;font-size:0.72rem'>{pct}% complete</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    if st.button("Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    st.caption(f"API: {API_BASE}")


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

STATE_COLORS = {
    "Fully Compliant": "#2ecc71",
    "Partially Compliant": "#f39c12",
    "Non-Compliant": "#e74c3c",
    "Unable to Determine": "#95a5a6",
}

STATE_EMOJI = {
    "Fully Compliant": "✅",
    "Partially Compliant": "⚠️",
    "Non-Compliant": "❌",
    "Unable to Determine": "❓",
}


def _state_badge(state: str) -> str:
    color = STATE_COLORS.get(state, "#95a5a6")
    emoji = STATE_EMOJI.get(state, "")
    return f"<span style='background:{color};color:white;padding:3px 10px;border-radius:12px;font-size:0.85em'>{emoji} {state}</span>"


def _confidence_bar(confidence: float) -> str:
    pct = int(confidence * 100)
    color = "#2ecc71" if pct >= 80 else "#f39c12" if pct >= 60 else "#e74c3c"
    return (
        f"<div style='background:#eee;border-radius:4px;width:120px;display:inline-block'>"
        f"<div style='background:{color};width:{pct}%;height:12px;border-radius:4px'></div>"
        f"</div> {pct}%"
    )


def _call_api(method: str, endpoint: str, **kwargs):
    """Wrapper for API calls with error handling."""
    url = f"{API_BASE}{endpoint}"
    try:
        resp = getattr(requests, method)(url, timeout=300, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.error(
            "Cannot connect to the API server. "
            "Start it with: `uvicorn backend.api.main:app --reload`"
        )
        return None
    except requests.exceptions.HTTPError as exc:
        st.error(f"API error: {exc.response.text}")
        return None


# ─────────────────────────────────────────────
# PAGE 1: Analyze Contract
# ─────────────────────────────────────────────

_STEP_LABELS = {
    "pending":      "⏳ Queued — waiting to start...",
    "parsing_pdf":  "📄 Step 1/6 — Parsing PDF (extracting text, tables, layout)...",
    "chunking":     "✂️  Step 2/6 — Chunking into section-aware passages...",
    "embedding":    "🔢 Step 3/6 — Embedding chunks with sentence-transformers...",
    "indexing":     "🗄️  Step 4/6 — Indexing contract vectors into ChromaDB...",
    "classifying":  "🔎 Step 5/6 — Classifying contract — selecting applicable ESA questions...",
    "retrieving":   "🔍 Step 6/6 — Retrieving evidence from contract + ESA act (dual-source)...",
    "analyzing":    "🤖 Step 6/6 — Compliance Agent analysing applicable ESA questions in parallel...",
    "evaluating":   "🧐 Step 6/6 — Evaluator checking quotes and grounding against ESA...",
    "completed":    "✅ Analysis complete!",
}


def page_analyze():
    st.header("Employment Contract — ESA Compliance Analysis")
    st.caption(
        "Upload an employment contract PDF. The system will automatically determine "
        "which Employment Standards Act of Ontario (ESA) requirements apply, then "
        "analyse each one using dual-source Agentic RAG (contract + ESA act text)."
    )

    job_running = st.session_state.get("job_running", False)

    # ── If a job is in progress, show progress and poll once, then rerun ──
    if job_running:
        job_id   = st.session_state["last_job_id"]
        filename = st.session_state.get("job_filename", "")
        progress = st.session_state.get("job_progress", {"pct": 0, "label": "⏳ Queued...", "steps": []})

        st.info(f"Analysis running: **{filename}**")
        st.progress(progress["pct"] / 100, text=progress["label"])

        steps_so_far = progress.get("steps", [])
        if len(steps_so_far) > 1:
            done = " → ".join(
                _STEP_LABELS.get(s, s).split("—")[0].strip()
                for s in steps_so_far[:-1]
            )
            st.caption(f"Done: {done}")

        # Poll once and reschedule via rerun
        poll = _call_api("get", f"/results/{job_id}")
        if poll is None:
            st.warning("Lost connection to API. Retrying...")
            time.sleep(2)
            st.rerun()
            return

        status = poll.get("status", "pending")
        pct    = poll.get("progress_pct", 0)
        label  = _STEP_LABELS.get(status, status)

        steps = steps_so_far.copy()
        if status not in steps and status != "completed":
            steps.append(status)

        st.session_state["job_progress"] = {"pct": pct, "label": label, "steps": steps}

        if status == "completed":
            st.session_state["last_result"]  = poll.get("result")
            st.session_state["job_running"]  = False
            st.session_state["job_progress"] = {}
            st.rerun()
            return
        elif status == "failed":
            st.error(f"Analysis failed: {poll.get('error', 'Unknown error')}")
            st.session_state["job_running"] = False
            st.session_state["job_progress"] = {}
            return
        else:
            time.sleep(1)
            st.rerun()
            return

    # ── Upload (only shown when no job is running) ────────────────────────
    uploaded = st.file_uploader(
        "Upload PDF Contract",
        type=["pdf"],
        help="Born-digital PDF recommended. Max 50 MB.",
    )

    # Law selector — only show ready laws
    laws = list_law_references(ready_only=True)
    law_options = {"default": "Default (built-in ESA)"}
    for law in laws:
        law_options[law["law_id"]] = law["display_name"]

    selected_law_id = st.selectbox(
        "Check contract against",
        options=list(law_options.keys()),
        format_func=lambda k: law_options[k],
        help="Select a law reference from the Law Library, or use the built-in ESA.",
    )

    if uploaded is not None:
        col1, col2 = st.columns([1, 3])
        with col1:
            st.metric("File", uploaded.name)
            st.metric("Size", f"{uploaded.size / 1024:.1f} KB")
        with col2:
            analyze_btn = st.button("Analyze Contract", type="primary", use_container_width=True)

        if analyze_btn:
            law_id_to_send = "" if selected_law_id == "default" else selected_law_id
            with st.spinner("Submitting analysis job..."):
                response = _call_api(
                    "post",
                    "/analyze",
                    files={"file": (uploaded.name, uploaded.getvalue(), "application/pdf")},
                    data={
                        "model": st.session_state.get("selected_model", "claude-sonnet-4-6"),
                        "law_id": law_id_to_send,
                    },
                )

            if response is not None:
                st.session_state["last_job_id"]   = response["job_id"]
                st.session_state["last_trace_id"] = response["trace_id"]
                st.session_state["contract_id"]   = response.get("contract_id", "")
                st.session_state["last_result"]   = None
                st.session_state["job_running"]   = True
                st.session_state["job_filename"]  = uploaded.name
                st.session_state["job_progress"]  = {"pct": 0, "label": "⏳ Queued...", "steps": []}
                st.rerun()

    # ── Analysis history browser (always visible) ─────────────────────────
    st.divider()
    st.subheader("Analysis History")
    history_df = get_analyses_df(limit=20)
    if history_df.empty:
        st.caption("No previous analyses yet.")
    else:
        for _, row in history_df.iterrows():
            ts = row.get("analysis_timestamp", "")[:16].replace("T", " ")
            is_active = st.session_state.get("last_trace_id") == row["trace_id"]
            label = f"{'▶ ' if is_active else '📄 '}{row['filename']}  —  {ts}  —  conf: {row.get('avg_confidence', 0):.0%}"
            if st.button(label, key=f"hist_{row['trace_id']}", type="primary" if is_active else "secondary"):
                raw = get_full_result(row["trace_id"])
                if raw:
                    st.session_state["last_result"] = json.loads(raw)
                    st.session_state["last_trace_id"] = row["trace_id"]
                    st.session_state["contract_id"] = row.get("contract_id", "")
                    st.rerun()
                else:
                    st.warning("Full result not stored for this analysis.")

    # ── Display results (always visible when loaded) ──────────────────────
    result_data = st.session_state.get("last_result")
    trace_id = st.session_state.get("last_trace_id", "")
    if result_data:
        _render_results(result_data, trace_id)


def _render_results(result_data: dict, trace_id: str):
    st.divider()
    st.subheader("ESA Compliance Analysis Results")

    results = result_data.get("results", [])
    meta = result_data.get("processing_metadata", {})

    # Summary cards
    c1, c2, c3, c4, c5 = st.columns(5)
    fully = sum(1 for r in results if r["compliance_state"] == "Fully Compliant")
    partial = sum(1 for r in results if r["compliance_state"] == "Partially Compliant")
    non = sum(1 for r in results if r["compliance_state"] == "Non-Compliant")
    avg_conf = sum(r["confidence"] for r in results) / max(len(results), 1)
    q_analyzed = meta.get("questions_analyzed", len(results))
    q_skipped = meta.get("questions_skipped", 0)

    c1.metric("Fully Compliant", fully)
    c2.metric("Partially Compliant", partial)
    c3.metric("Non-Compliant", non)
    c4.metric("Avg Confidence", f"{avg_conf:.0%}")
    c5.metric("Questions Analyzed", q_analyzed, help=f"{q_skipped} ESA questions skipped (not applicable to this contract)")

    st.divider()

    # Per-question expandable cards
    for result in results:
        state = result.get("compliance_state", "Unknown")
        emoji = STATE_EMOJI.get(state, "")
        conf = result.get("confidence", 0)
        title = result.get("question_title", "")
        qid = result.get("question_id", "")
        esa_parts = result.get("esa_parts", [])
        parts_str = f" | {', '.join(esa_parts)}" if esa_parts else ""

        with st.expander(
            f"{emoji} [{qid}]{parts_str}: {title} — {state} ({conf:.0%})",
            expanded=(state != "Fully Compliant"),
        ):
            col_a, col_b = st.columns([1, 2])

            with col_a:
                st.markdown(f"**State:** {_state_badge(state)}", unsafe_allow_html=True)
                st.markdown(f"**Confidence:** {_confidence_bar(conf)}", unsafe_allow_html=True)
                if result.get("retry_count", 0) > 0:
                    st.warning(f"Retried {result['retry_count']} time(s)")

                # ESA sections cited
                act_sections = result.get("act_sections_cited", [])
                if act_sections:
                    st.markdown(
                        "<div style='margin-top:6px'><span style='font-size:0.8rem;color:#6b7280'>ESA Sections:</span> "
                        + " ".join(
                            f"<code style='font-size:0.75rem;background:#1e1b4b;color:#a5b4fc;padding:1px 5px;border-radius:3px'>{s}</code>"
                            for s in act_sections
                        )
                        + "</div>",
                        unsafe_allow_html=True,
                    )

                # Evaluator badge
                ea = result.get("evaluator_assessment")
                if ea:
                    verdict = ea.get("verdict", "")
                    if verdict == "PASS":
                        st.success("Evaluator: PASS")
                    elif verdict == "PASS_WITH_FLAGS":
                        st.warning("Evaluator: PASS WITH FLAGS")
                    else:
                        st.error("Evaluator: FAIL (retried)")

                    if ea.get("hallucination_flags"):
                        st.error(f"Hallucination flags: {len(ea['hallucination_flags'])}")

            with col_b:
                st.markdown("**Rationale**")
                st.write(result.get("rationale", "No rationale provided."))

                # Gap summary
                gap = result.get("gap_summary", "")
                if gap and gap != "No gaps identified.":
                    st.markdown(
                        f"<div style='background:#2d1a1a;border-left:3px solid #e74c3c;"
                        f"padding:8px 12px;border-radius:4px;margin-top:8px'>"
                        f"<span style='font-size:0.75rem;color:#f87171;font-weight:600'>GAP vs ESA MINIMUM</span><br>"
                        f"<span style='font-size:0.85rem;color:#fca5a5'>{gap}</span></div>",
                        unsafe_allow_html=True,
                    )
                elif gap == "No gaps identified.":
                    st.markdown(
                        "<div style='background:#1a2d1a;border-left:3px solid #2ecc71;"
                        "padding:6px 12px;border-radius:4px;margin-top:8px'>"
                        "<span style='font-size:0.8rem;color:#4ade80'>No gaps vs ESA minimum</span></div>",
                        unsafe_allow_html=True,
                    )

            # Sub-criteria table
            sc_results = result.get("sub_criteria_results", [])
            if sc_results:
                st.markdown("**Sub-criteria Coverage**")
                sc_df = pd.DataFrame([
                    {
                        "ID": sc["criterion_id"],
                        "ESA Section": sc.get("esa_section", ""),
                        "Description": sc["description"][:65] + ("..." if len(sc["description"]) > 65 else ""),
                        "Met": "✅" if sc["found"] else "❌",
                        "Evidence": sc.get("evidence_summary", "")[:90],
                    }
                    for sc in sc_results
                ])
                st.dataframe(sc_df, use_container_width=True, hide_index=True)

            # Quotes — separated by source
            quotes = result.get("relevant_quotes", [])
            contract_quotes = [q for q in quotes if q.get("source", "contract") == "contract"]
            act_quotes = [q for q in quotes if q.get("source") == "act"]

            if contract_quotes:
                st.markdown("**Contract Quotes**")
                for q in contract_quotes:
                    st.markdown(
                        f"<div style='background:#1e1e2e;border-left:3px solid #3498db;"
                        f"padding:8px 12px;border-radius:4px;margin:4px 0'>"
                        f"<span style='font-size:0.75rem;color:#60a5fa'>CONTRACT</span><br>"
                        f"<em style='color:#e2e8f0'>\"{q['text']}\"</em><br>"
                        f"<span style='font-size:0.78rem;color:#94a3b8'>— {q.get('section_reference', '')}</span></div>",
                        unsafe_allow_html=True,
                    )

            if act_quotes:
                st.markdown("**ESA Act Quotes**")
                for q in act_quotes:
                    st.markdown(
                        f"<div style='background:#1e2e1e;border-left:3px solid #2ecc71;"
                        f"padding:8px 12px;border-radius:4px;margin:4px 0'>"
                        f"<span style='font-size:0.75rem;color:#4ade80'>ESA ACT</span><br>"
                        f"<em style='color:#e2e8f0'>\"{q['text']}\"</em><br>"
                        f"<span style='font-size:0.78rem;color:#94a3b8'>— {q.get('section_reference', '')}</span></div>",
                        unsafe_allow_html=True,
                    )

    # Processing metadata
    with st.expander("Processing Metadata / Observability"):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Time", f"{meta.get('total_duration_ms', 0)/1000:.1f}s")
        col2.metric("Input Tokens", f"{meta.get('total_input_tokens', 0):,}")
        col3.metric("Output Tokens", f"{meta.get('total_output_tokens', 0):,}")
        col4.metric("Est. Cost", f"${meta.get('estimated_cost_usd', 0):.4f}")

        st.caption(f"Model: `{meta.get('model_used', 'N/A')}` | Trace ID: `{trace_id}`")

        timings = {
            "PDF Parse": meta.get("pdf_parse_duration_ms", 0),
            "Embedding": meta.get("embedding_duration_ms", 0),
            "Retrieval/Index": meta.get("retrieval_duration_ms", 0),
            "LLM (all agents)": meta.get("llm_duration_ms", 0),
            "Evaluation": meta.get("evaluation_duration_ms", 0),
        }
        fig = px.bar(
            x=list(timings.keys()),
            y=[v / 1000 for v in timings.values()],
            labels={"x": "Stage", "y": "Seconds"},
            title="Pipeline Stage Timings",
            color_discrete_sequence=["#3498db"],
        )
        st.plotly_chart(fig, use_container_width=True)

    # JSON download
    st.download_button(
        "Download JSON Results",
        data=json.dumps(result_data, indent=2, default=str),
        file_name=f"compliance_analysis_{trace_id[:8]}.json",
        mime="application/json",
    )


# ─────────────────────────────────────────────
# PAGE 2: KPI Dashboard
# ─────────────────────────────────────────────

def page_dashboard():
    st.header("KPI Dashboard")
    st.caption("Real-time and historical performance monitoring for the Contract Analyzer system.")

    kpi = get_kpi_summary()

    # ── Summary KPI cards ─────────────────────────────────────────────────
    st.subheader("System Overview")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Analyses", kpi.get("total_analyses", 0))
    c2.metric(
        "Avg Latency",
        f"{kpi.get('avg_latency_ms', 0)/1000:.1f}s",
        help="End-to-end wall time per analysis. Target: < 30s p95",
    )
    c3.metric(
        "Avg Confidence",
        f"{kpi.get('avg_confidence', 0):.1f}%",
        help="Average confidence across all compliance questions. Alert if < 65%",
    )
    c4.metric(
        "Avg Cost / Analysis",
        f"${kpi.get('avg_cost_usd', 0):.4f}",
        help="LLM API cost per contract. Target: < $0.10",
    )
    c5.metric(
        "Hallucination Rate",
        f"{kpi.get('hallucination_rate', 0):.1f}%",
        help="% of questions where evaluator flagged unverified quotes. Alert if > 5%",
    )

    col_a, col_b = st.columns(2)
    with col_a:
        st.metric(
            "Evaluator Retry Rate",
            f"{kpi.get('avg_retry_rate', 0):.1f}%",
            help="% of questions requiring at least one retry. Alert if > 20%",
        )
    with col_b:
        st.metric(
            "Total LLM Tokens",
            f"{kpi.get('total_input_tokens', 0) + kpi.get('total_output_tokens', 0):,}",
        )

    st.divider()

    # ── Historical trends ─────────────────────────────────────────────────
    st.subheader("Historical Trends (Last 30 Days)")

    days = st.slider("Trend window (days)", 7, 90, 30)

    tab1, tab2, tab3 = st.tabs(["Latency Trend", "Confidence Trend", "Compliance Distribution"])

    with tab1:
        latency_df = get_latency_trend_df(days=days)
        if latency_df.empty:
            st.info("No data yet — run some analyses first.")
        else:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=latency_df["date"], y=latency_df["avg_latency_ms"] / 1000,
                name="Avg", mode="lines+markers", line=dict(color="#3498db"),
            ))
            fig.add_trace(go.Scatter(
                x=latency_df["date"], y=latency_df["max_latency_ms"] / 1000,
                name="Max", mode="lines", line=dict(color="#e74c3c", dash="dot"),
            ))
            fig.add_hline(y=30, line_dash="dash", line_color="orange",
                          annotation_text="30s SLO", annotation_position="bottom right")
            fig.update_layout(
                title="Analysis Latency Over Time",
                yaxis_title="Seconds",
                xaxis_title="Date",
                legend=dict(orientation="h"),
            )
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        conf_df = get_confidence_trend_df(days=days)
        if conf_df.empty:
            st.info("No data yet.")
        else:
            fig = px.line(
                conf_df,
                x="date",
                y="avg_confidence",
                color="question_title",
                title="Average Confidence per Question Over Time",
                labels={"avg_confidence": "Confidence", "date": "Date", "question_title": "Question"},
                range_y=[0, 1],
            )
            fig.add_hline(y=0.65, line_dash="dash", line_color="orange",
                          annotation_text="65% alert threshold")
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        dist_df = get_compliance_distribution_df()
        if dist_df.empty:
            st.info("No data yet.")
        else:
            fig = px.bar(
                dist_df,
                x="question_title",
                y="count",
                color="compliance_state",
                color_discrete_map={
                    "Fully Compliant": "#2ecc71",
                    "Partially Compliant": "#f39c12",
                    "Non-Compliant": "#e74c3c",
                    "Unable to Determine": "#95a5a6",
                },
                title="Compliance State Distribution by Question",
                labels={"question_title": "Question", "count": "Count"},
                barmode="stack",
            )
            fig.update_xaxes(tickangle=20)
            st.plotly_chart(fig, use_container_width=True)

    # ── Recent analyses table ─────────────────────────────────────────────
    st.subheader("Recent Analyses")
    analyses_df = get_analyses_df(limit=20)
    if analyses_df.empty:
        st.info("No analyses completed yet.")
    else:
        display_cols = [
            "trace_id", "filename", "analysis_timestamp",
            "total_duration_ms", "avg_confidence",
            "estimated_cost_usd", "retry_count", "model_used",
        ]
        display_cols = [c for c in display_cols if c in analyses_df.columns]
        st.dataframe(
            analyses_df[display_cols].rename(columns={
                "total_duration_ms": "latency_ms",
                "avg_confidence": "avg_confidence",
                "estimated_cost_usd": "cost_usd",
            }),
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("KPI Rationale & Thresholds"):
        st.markdown("""
| KPI | Target / Threshold | Alert Action | Why It Matters |
|-----|--------------------|--------------|----------------|
| End-to-end latency p95 | < 30s | Investigate span timings | User experience; LLM degradation signal |
| Avg Confidence | > 65% | Review retrieval recall | Low confidence = weak evidence or ambiguous contract |
| Hallucination Rate | < 5% | Audit flagged quotes; adjust grounding prompt | Direct compliance accuracy risk |
| Evaluator Retry Rate | < 20% | Review compliance/evaluator prompt alignment | High retry = agent quality degrading |
| Cost per analysis | < $0.10 | Optimise chunk sizes, reduce top-k | Budget control |
| Total tokens | Track weekly | No hard threshold | Model drift detection |
        """)


# ─────────────────────────────────────────────
# PAGE 3: Chat (Bonus)
# ─────────────────────────────────────────────

def page_chat():
    st.header("Contract Chat")
    st.caption(
        "Ask free-form questions about the uploaded contract. "
        "Requires an analysis to have been completed first (the vector store must be populated)."
    )

    contract_id = st.session_state.get("contract_id")

    if not contract_id:
        st.warning(
            "No contract loaded. Go to **Analyze Contract**, upload a PDF, and wait for analysis to complete."
        )
        manual_id = st.text_input("Or enter a Contract ID manually:")
        if manual_id:
            st.session_state["contract_id"] = manual_id
            contract_id = manual_id
        if not contract_id:
            return

    st.info(f"Contract ID: `{contract_id}`")

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    # Display existing messages
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                with st.expander("Sources"):
                    for src in msg["sources"]:
                        st.markdown(f"> *\"{src['text']}\"* — {src['section_reference']}")

    # Input
    user_input = st.chat_input("Ask about the contract...")
    if not user_input:
        return

    # Display user message
    with st.chat_message("user"):
        st.markdown(user_input)

    st.session_state["chat_history"].append({"role": "user", "content": user_input})

    # Call API
    with st.chat_message("assistant"):
        with st.spinner("Searching contract..."):
            history_for_api = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state["chat_history"][:-1]
            ]
            payload = {
                "contract_id": contract_id,
                "message": user_input,
                "history": history_for_api,
            }
            result = _call_api("post", "/chat", json=payload)

        if result:
            reply = result.get("reply", "No response.")
            sources = result.get("sources", [])
            st.markdown(reply)
            if sources:
                with st.expander("Sources"):
                    for src in sources:
                        st.markdown(
                            f"> *\"{src['text']}\"*  \n"
                            f"> — {src.get('section_reference', 'Unknown')}"
                        )
            st.session_state["chat_history"].append({
                "role": "assistant",
                "content": reply,
                "sources": sources,
            })
        else:
            st.error("Failed to get response from API.")

    if st.button("Clear Chat"):
        st.session_state["chat_history"] = []
        st.rerun()


# ─────────────────────────────────────────────
# PAGE 4: Process Monitor
# ─────────────────────────────────────────────

_EST = ZoneInfo("America/New_York")


def _to_est(ts: str) -> str:
    """Convert an ISO UTC timestamp string to EST/EDT (America/New_York)."""
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_EST).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return ts[:19].replace("T", " ")


# Stage → (label, css-color, emoji)  — mirrors tools/log_live.py STAGE_MAP
_STAGE_MAP = {
    "api_startup_complete":       ("STARTUP",    "#22d3ee", "🚀"),
    "metrics_db_initialized":     ("STARTUP",    "#6b7280", "💾"),
    "analysis_job_created":       ("JOB",        "#60a5fa", "📋"),
    "analysis_pipeline_start":    ("PIPELINE",   "#60a5fa", "▶"),
    "pdf_parse_start":            ("PARSE",      "#fbbf24", "📄"),
    "pdf_parse_complete":         ("PARSE",      "#fbbf24", "📄"),
    "chunking_complete":          ("CHUNK",      "#fbbf24", "✂"),
    "embedding_model_loading":    ("EMBED",      "#e879f9", "🔢"),
    "embedding_model_ready":      ("EMBED",      "#e879f9", "🔢"),
    "embedding_complete":         ("EMBED",      "#e879f9", "🔢"),
    "chromadb_client_ready":      ("INDEX",      "#e879f9", "🗄"),
    "chunks_indexed":             ("INDEX",      "#e879f9", "🗄"),
    "router_llm_call_start":      ("ROUTER",     "#22d3ee", "🔀"),
    "router_llm_call_complete":   ("ROUTER",     "#22d3ee", "🔀"),
    "router_query_plan":          ("ROUTER",     "#22d3ee", "🔀"),
    "compliance_agent_llm_call":  ("COMPLIANCE", "#4ade80", "🤖"),
    "compliance_agent_complete":  ("COMPLIANCE", "#4ade80", "🤖"),
    "evaluator_complete":         ("EVALUATOR",  "#fbbf24", "🧐"),
    "analysis_pipeline_complete": ("DONE",       "#4ade80", "✅"),
    "analysis_job_failed":        ("ERROR",      "#f87171", "❌"),
    "analysis_job_error":         ("ERROR",      "#f87171", "❌"),
}

_NOISY_LOGGERS = {
    "matplotlib", "httpx", "huggingface_hub", "sentence_transformers",
    "unstructured", "unstructured_inference", "pikepdf._core",
}
_NOISY_EVENTS = {"http_request_start", "http_request_end"}

_VERDICT_COLOR = {
    "PASS":            "#4ade80",
    "PASS_WITH_FLAGS": "#fbbf24",
    "FAIL":            "#f87171",
}
_STATE_COLOR = {
    "Fully Compliant":      "#4ade80",
    "Partially Compliant":  "#fbbf24",
    "Non-Compliant":        "#f87171",
    "Unable to Determine":  "#9ca3af",
}


def _fmt_extras_html(entry: dict) -> str:
    skip = {"event", "logger", "level", "timestamp", "trace_id", "span_id", "request_id"}
    priority = [
        "question_id", "question_title", "duration_ms", "total_chunks",
        "total_elements", "num_chunks", "confidence", "verdict",
        "compliance_state", "retry_count", "hallucination_flags",
        "error", "filename", "model", "total_input_tokens",
        "total_output_tokens", "estimated_cost_usd",
    ]
    parts = []
    shown: set[str] = set()
    for key in priority:
        if key in entry and key not in skip:
            val = entry[key]
            if key == "duration_ms":
                val = f"{val/1000:.2f}s"
            elif key == "estimated_cost_usd":
                val = f"${val:.4f}"
            elif key == "confidence":
                val = f"{val:.0%}"
            parts.append(
                f"<span style='color:#6b7280'>{key}</span>"
                f"<span style='color:#e2e8f0'>=</span>"
                f"<span style='color:#22d3ee'>{val}</span>"
            )
            shown.add(key)
    for key, val in entry.items():
        if key not in skip and key not in shown and not isinstance(val, (dict, list)):
            parts.append(
                f"<span style='color:#6b7280'>{key}={val}</span>"
            )
    return "&nbsp;&nbsp;".join(parts)


def _render_entry_html(entry: dict, trace_filter: str | None, verbose: bool) -> str | None:
    logger_name = entry.get("logger", "")
    event       = entry.get("event", "")
    level       = entry.get("level", "info").lower()
    ts          = _to_est(entry.get("timestamp", ""))
    trace_id    = entry.get("trace_id", "")
    short_tid   = trace_id[:8] if trace_id else "--------"

    if trace_filter and trace_id and not trace_id.startswith(trace_filter):
        return None
    if not verbose:
        if any(logger_name.startswith(n) for n in _NOISY_LOGGERS):
            return None
        if event in _NOISY_EVENTS:
            return None

    stage, color, emoji = _STAGE_MAP.get(event, ("SYS", "#6b7280", "·"))

    if level in ("error", "critical"):
        color = "#f87171"
    elif level == "warning":
        color = "#fbbf24"

    extras = _fmt_extras_html(entry)
    return (
        f"<div style='margin:1px 0; line-height:1.6'>"
        f"<span style='color:#4b5563'>{ts}</span>&nbsp;"
        f"<span style='color:#374151'>[{short_tid}]</span>&nbsp;"
        f"<span style='color:{color};font-weight:600;min-width:90px;display:inline-block'>{stage}</span>&nbsp;"
        f"<span style='color:{color}'>{emoji}&nbsp;{event}</span>&nbsp;&nbsp;"
        f"{extras}"
        f"</div>"
    )


def _read_log_entries(log_path: Path, last_n: int = 300) -> list[dict]:
    entries = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines[-last_n:]:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    except OSError:
        pass
    return entries


def _list_recent_traces(entries: list[dict]) -> list[dict]:
    traces: dict[str, dict] = {}
    for e in entries:
        tid = e.get("trace_id")
        if not tid:
            continue
        if tid not in traces:
            traces[tid] = {"trace_id": tid, "started": e.get("timestamp", ""), "filename": "", "events": 0}
        traces[tid]["events"] += 1
        if e.get("filename"):
            traces[tid]["filename"] = e["filename"]
    return sorted(traces.values(), key=lambda x: x["started"], reverse=True)


def _render_trace_html(entries: list[dict]) -> str:
    lines = []
    stage_for_event: dict[str, str] = {}
    _TRACE_STAGES = [
        ("📋  JOB CREATED",      ["analysis_job_created"]),
        ("📄  PDF PARSING",       ["pdf_parse_start", "pdf_parse_complete"]),
        ("✂   CHUNKING",          ["chunking_complete"]),
        ("🔢  EMBEDDING",         ["embedding_model_loading", "embedding_model_ready", "embedding_complete"]),
        ("🗄   INDEXING",          ["chromadb_client_ready", "chunks_indexed"]),
        ("🔀  ROUTER AGENT",      ["router_llm_call_start", "router_llm_call_complete", "router_query_plan"]),
        ("🤖  COMPLIANCE AGENT",  ["compliance_agent_llm_call", "compliance_agent_complete", "compliance_agent_start"]),
        ("🧐  EVALUATOR",         ["evaluator_complete", "evaluator_start", "evaluator_llm_call"]),
        ("✅  PIPELINE COMPLETE", ["analysis_pipeline_complete"]),
        ("❌  ERRORS",            ["analysis_job_failed", "analysis_job_error"]),
    ]
    for stage_label, stage_events in _TRACE_STAGES:
        for ev in stage_events:
            stage_for_event[ev] = stage_label

    current_stage = None
    for entry in entries:
        ev    = entry.get("event", "")
        ts    = _to_est(entry.get("timestamp", ""))
        level = entry.get("level", "info").lower()

        stage = stage_for_event.get(ev)
        if stage and stage != current_stage:
            current_stage = stage
            lines.append(
                f"<div style='margin:10px 0 4px 0; color:#60a5fa; font-weight:700; "
                f"border-bottom:1px solid #1e3a5f; padding-bottom:2px'>── {stage}</div>"
            )

        _, color, emoji = _STAGE_MAP.get(ev, ("SYS", "#6b7280", "·"))
        if level in ("error", "critical"):
            color = "#f87171"
        elif level == "warning":
            color = "#fbbf24"

        extras = _fmt_extras_html(entry)

        # Special rich rendering for key events
        detail = ""
        if ev == "analysis_pipeline_complete":
            dur  = entry.get("total_duration_ms", 0) / 1000
            cost = entry.get("estimated_cost_usd", 0)
            tin  = entry.get("total_input_tokens", 0)
            tout = entry.get("total_output_tokens", 0)
            detail = (
                f"<div style='margin-left:16px;color:#9ca3af;font-size:0.85em'>"
                f"duration: <b style='color:#e2e8f0'>{dur:.1f}s</b> &nbsp;"
                f"cost: <b style='color:#e2e8f0'>${cost:.4f}</b> &nbsp;"
                f"tokens: <b style='color:#e2e8f0'>{tin:,} in / {tout:,} out</b>"
                f"</div>"
            )
        elif ev == "evaluator_complete":
            verdict   = entry.get("verdict", "")
            conf_adj  = entry.get("confidence_adjustment")
            hall_raw  = entry.get("hallucination_flags", [])
            hall_n    = hall_raw if isinstance(hall_raw, int) else len(hall_raw)
            vcol      = _VERDICT_COLOR.get(verdict, "#e2e8f0")
            detail_parts = [f"verdict: <b style='color:{vcol}'>{verdict}</b>"]
            if conf_adj is not None:
                detail_parts.append(f"conf_adj: <b style='color:#e2e8f0'>{conf_adj:+.0%}</b>")
            if hall_n:
                detail_parts.append(f"<span style='color:#f87171'>hallucination_flags: {hall_n}</span>")
            detail = f"<div style='margin-left:16px;color:#9ca3af;font-size:0.85em'>{'  '.join(detail_parts)}</div>"
        elif ev == "compliance_agent_complete":
            state = entry.get("compliance_state", "")
            conf  = entry.get("confidence", 0)
            scol  = _STATE_COLOR.get(state, "#e2e8f0")
            detail = (
                f"<div style='margin-left:16px;color:#9ca3af;font-size:0.85em'>"
                f"state: <b style='color:{scol}'>{state}</b> &nbsp;"
                f"confidence: <b style='color:#e2e8f0'>{conf:.0%}</b>"
                f"</div>"
            )

        lines.append(
            f"<div style='margin:1px 0;line-height:1.7'>"
            f"<span style='color:#4b5563'>{ts}</span>&nbsp;"
            f"<span style='color:{color}'>{emoji}&nbsp;<b>{ev}</b></span>&nbsp;&nbsp;"
            f"{extras}"
            f"</div>"
            f"{detail}"
        )

    # Compliance summary table
    comp_events = [e for e in entries if e.get("event") == "evaluator_complete"]
    if comp_events:
        lines.append(
            "<div style='margin:16px 0 4px 0;color:#60a5fa;font-weight:700;"
            "border-bottom:1px solid #1e3a5f;padding-bottom:2px'>── COMPLIANCE SUMMARY</div>"
        )
        lines.append(
            "<table style='width:100%;border-collapse:collapse;font-size:0.82em;margin-top:6px'>"
            "<tr style='color:#6b7280'><th style='text-align:left;padding:2px 8px'>Q</th>"
            "<th style='text-align:left;padding:2px 8px'>Question</th>"
            "<th style='text-align:left;padding:2px 8px'>Verdict</th>"
            "<th style='text-align:left;padding:2px 8px'>Conf Adj</th>"
            "<th style='text-align:left;padding:2px 8px'>Retries</th></tr>"
        )
        for e in sorted(comp_events, key=lambda x: x.get("question_id", 0)):
            qid     = e.get("question_id", "?")
            title   = (e.get("question_title") or "")[:45]
            verdict = e.get("verdict", "")
            cadj    = e.get("confidence_adjustment", 0) or 0
            retries = e.get("retry_count", 0)
            vcol    = _VERDICT_COLOR.get(verdict, "#e2e8f0")
            rcol    = "#f87171" if retries else "#e2e8f0"
            cadj_s  = f"{cadj:+.0%}" if cadj else "—"
            lines.append(
                f"<tr style='border-top:1px solid #1e293b'>"
                f"<td style='padding:3px 8px;color:#9ca3af'>Q{qid}</td>"
                f"<td style='padding:3px 8px;color:#e2e8f0'>{title}</td>"
                f"<td style='padding:3px 8px;color:{vcol};font-weight:700'>{verdict}</td>"
                f"<td style='padding:3px 8px;color:#9ca3af'>{cadj_s}</td>"
                f"<td style='padding:3px 8px;color:{rcol}'>{retries}</td>"
                f"</tr>"
            )
        lines.append("</table>")

    return "\n".join(lines)


def _terminal_wrap(content_html: str, height: int = 520) -> str:
    return (
        f"<div style='"
        f"background:#0d1117;padding:16px;border-radius:8px;"
        f"font-family:\"Fira Code\",\"Cascadia Code\",monospace;font-size:0.76rem;"
        f"height:{height}px;overflow-y:auto;border:1px solid #21262d;"
        f"color:#e2e8f0;line-height:1.5'>"
        f"{content_html}"
        f"</div>"
    )


def page_monitor():
    st.header("Process Monitor")
    st.caption("Live pipeline logs and per-trace inspection.")

    log_path = Path(os.getenv("LOG_FILE_PATH", "logs/app.jsonl"))

    tab1, tab2 = st.tabs(["Live Feed", "Trace Inspector"])

    # ── Tab 1: Live Feed ──────────────────────────────────────────────────
    with tab1:
        current_trace = st.session_state.get("last_trace_id", "")

        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            auto_refresh = st.toggle("Auto-refresh", value=False)
        with col2:
            interval = st.selectbox("Every", [2, 5, 10, 30], index=1, format_func=lambda x: f"{x}s")
        with col3:
            verbose = st.toggle("Verbose", value=False)

        if not current_trace:
            st.info("No active analysis in this session. Go to **Analyze Contract**, upload a PDF, and the live logs will appear here.")
        elif not log_path.exists():
            st.warning(f"Log file not found at `{log_path}`. Start the API server first.")
        else:
            entries = _read_log_entries(log_path, last_n=5000)
            # Show only entries for the current session's trace
            trace_entries = [e for e in entries if e.get("trace_id", "").startswith(current_trace)]
            rendered = [_render_entry_html(e, current_trace, verbose) for e in trace_entries]
            rendered = [r for r in rendered if r]

            short_tid = current_trace[:12]
            st.caption(f"Trace: `{short_tid}...`  —  {len(rendered)} events  (EST)")

            if not rendered:
                content = "<span style='color:#4b5563'>Waiting for log events for this trace…</span>"
            else:
                content = "\n".join(rendered)

            st.markdown(_terminal_wrap(content), unsafe_allow_html=True)

        if auto_refresh and current_trace:
            time.sleep(interval)
            st.rerun()

    # ── Tab 2: Trace Inspector ────────────────────────────────────────────
    with tab2:
        if not log_path.exists():
            st.warning(f"Log file not found at `{log_path}`.")
        else:
            all_entries = _read_log_entries(log_path, last_n=5000)
            recent_traces = _list_recent_traces(all_entries)

            if not recent_traces:
                st.info("No traces found yet. Run an analysis first.")
            else:
                st.markdown("**Recent traces** — click one to inspect:")

                selected_trace = st.session_state.get("monitor_selected_trace")

                cols = st.columns([3, 2, 1, 1])
                cols[0].markdown("<span style='color:gray;font-size:0.8em'>Trace ID</span>", unsafe_allow_html=True)
                cols[1].markdown("<span style='color:gray;font-size:0.8em'>File</span>", unsafe_allow_html=True)
                cols[2].markdown("<span style='color:gray;font-size:0.8em'>Started</span>", unsafe_allow_html=True)
                cols[3].markdown("<span style='color:gray;font-size:0.8em'>Events</span>", unsafe_allow_html=True)

                for trace in recent_traces[:15]:
                    tid   = trace["trace_id"]
                    ts    = _to_est(trace["started"])[:16]
                    fn    = (trace["filename"] or "(unknown)")[:30]
                    n_ev  = trace["events"]
                    is_sel = selected_trace == tid

                    c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
                    with c1:
                        btn_label = f"{'▶ ' if is_sel else ''}{tid[:20]}..."
                        if st.button(btn_label, key=f"trace_{tid}",
                                     type="primary" if is_sel else "secondary",
                                     use_container_width=True):
                            st.session_state["monitor_selected_trace"] = tid
                            st.rerun()
                    c2.markdown(f"<span style='font-size:0.85em'>{fn}</span>", unsafe_allow_html=True)
                    c3.markdown(f"<span style='font-size:0.85em;color:gray'>{ts}</span>", unsafe_allow_html=True)
                    c4.markdown(f"<span style='font-size:0.85em;color:gray'>{n_ev}</span>", unsafe_allow_html=True)

                if selected_trace:
                    trace_entries = [e for e in all_entries if e.get("trace_id", "").startswith(selected_trace)]
                    trace_entries = sorted(trace_entries, key=lambda e: e.get("timestamp", ""))

                    st.divider()
                    st.markdown(f"**Trace:** `{selected_trace}`  — {len(trace_entries)} events")

                    if trace_entries:
                        content = _render_trace_html(trace_entries)
                        st.markdown(_terminal_wrap(content, height=600), unsafe_allow_html=True)
                    else:
                        st.warning("No events found for this trace.")


# ─────────────────────────────────────────────
# PAGE 0: Guide
# ─────────────────────────────────────────────

def page_guide():
    # ── Hero ──────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 60%, #2e1065 100%);
            border-radius: 16px; padding: 48px 40px 40px 40px; margin-bottom: 32px;
            border: 1px solid #312e81;
        ">
            <div style="font-size:0.75rem;color:#a855f7;letter-spacing:3px;
                        text-transform:uppercase;margin-bottom:10px;">
                247Labs · AI Engineering
            </div>
            <div style="font-size:2.4rem;font-weight:900;color:#f1f5f9;line-height:1.15;
                        margin-bottom:14px;">
                Contract Compliance Analyzer
            </div>
            <div style="font-size:1.05rem;color:#94a3b8;max-width:680px;line-height:1.7;">
                An intelligent, fully automated pipeline that reads a PDF contract and
                determines — in minutes — whether it meets your organisation's security
                and compliance requirements. Every finding is grounded in verbatim
                contract language with hallucination detection built in.
            </div>
            <div style="margin-top:24px;display:flex;gap:12px;flex-wrap:wrap;">
                <span style="background:#1e3a5f;color:#38bdf8;padding:6px 14px;
                             border-radius:20px;font-size:0.78rem;font-weight:600;">
                    ⚡ 2–5 min per contract
                </span>
                <span style="background:#1e3a1e;color:#4ade80;padding:6px 14px;
                             border-radius:20px;font-size:0.78rem;font-weight:600;">
                    ✅ Hallucination-checked
                </span>
                <span style="background:#2e1065;color:#a855f7;padding:6px 14px;
                             border-radius:20px;font-size:0.78rem;font-weight:600;">
                    🤖 Agentic RAG Pipeline
                </span>
                <span style="background:#1c1917;color:#fb923c;padding:6px 14px;
                             border-radius:20px;font-size:0.78rem;font-weight:600;">
                    💰 ~$0.05–$0.15 per analysis
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── How it works ──────────────────────────────────────────────────────
    st.markdown("### How It Works")
    steps = [
        ("📄", "Upload",    "Drop in any PDF contract — vendor agreements, MSAs, SOWs, NDAs."),
        ("🔍", "Parse",     "The system extracts text, tables, and section structure using deep-learning layout analysis."),
        ("🔢", "Embed",     "Content is split into semantically meaningful chunks and indexed locally with vector embeddings."),
        ("🔀", "Retrieve",  "For each compliance criterion, a Router Agent plans targeted queries and fetches the most relevant evidence."),
        ("🤖", "Analyse",   "A Compliance Agent evaluates every sub-criterion against the retrieved evidence and extracts verbatim quotes."),
        ("🧐", "Verify",    "An Evaluator Agent cross-checks every quote for accuracy, flags hallucinations, and retries weak determinations."),
        ("📊", "Report",    "Results are returned as structured, auditable output with confidence scores, sub-criterion breakdowns, and cost tracking."),
    ]
    cols = st.columns(len(steps))
    for col, (icon, title, desc) in zip(cols, steps):
        col.markdown(
            f"""
            <div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;
                        padding:16px 12px;text-align:center;height:180px;">
                <div style="font-size:1.8rem">{icon}</div>
                <div style="font-size:0.78rem;font-weight:700;color:#e2e8f0;
                            margin:6px 0 4px 0">{title}</div>
                <div style="font-size:0.7rem;color:#64748b;line-height:1.5">{desc}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Manual vs Automated ───────────────────────────────────────────────
    st.markdown("### Manual Review vs. This System")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            """
            <div style="background:#1c0a0a;border:1px solid #7f1d1d;border-radius:12px;padding:24px;">
                <div style="font-size:1rem;font-weight:700;color:#f87171;margin-bottom:16px;">
                    ❌ Manual Contract Review
                </div>
                <ul style="color:#fca5a5;font-size:0.85rem;line-height:2;list-style:none;padding:0;margin:0">
                    <li>⏱ 3–8 hours per contract</li>
                    <li>💸 $150–$500 in legal / compliance time</li>
                    <li>🧠 Inconsistent — depends on reviewer expertise</li>
                    <li>📋 No audit trail or confidence scoring</li>
                    <li>🔁 Non-scalable — bottleneck at volume</li>
                    <li>⚠️ Risk of missed clauses in long documents</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            """
            <div style="background:#031a0f;border:1px solid #14532d;border-radius:12px;padding:24px;">
                <div style="font-size:1rem;font-weight:700;color:#4ade80;margin-bottom:16px;">
                    ✅ Contract Analyzer
                </div>
                <ul style="color:#86efac;font-size:0.85rem;line-height:2;list-style:none;padding:0;margin:0">
                    <li>⚡ 2–5 minutes per contract</li>
                    <li>💰 $0.05–$0.15 in compute cost</li>
                    <li>🎯 Deterministic, criteria-driven analysis</li>
                    <li>📑 Full audit trail with verbatim quotes</li>
                    <li>🚀 Scales to hundreds of contracts per day</li>
                    <li>🛡 3-layer hallucination detection built in</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Compliance domains ────────────────────────────────────────────────
    st.markdown("### Compliance Domains Analysed")
    domains = [
        ("🔐", "Password Management",
         "Checks 7 sub-criteria: password length, default prohibition, secure storage, brute-force protection, sharing ban, credential vaulting, and rotation policy."),
        ("🖥", "IT Asset Management",
         "Verifies asset inventory completeness, required fields, quarterly reconciliation, configuration baselines, and drift remediation procedures."),
        ("🎓", "Security Training & Background Checks",
         "Confirms on-hire and annual security training, background screening requirements, and policy attestation obligations."),
        ("🔒", "Data in Transit Encryption",
         "Validates TLS 1.2+ enforcement, TLS 1.3 preference, admin pathway encryption, subprocessor transfer controls, and certificate management."),
        ("🌐", "Network Authentication & Authorization",
         "Reviews authentication mechanisms, MFA requirements, secure admin pathways, session logging, and RBAC implementation."),
    ]
    for icon, title, desc in domains:
        st.markdown(
            f"""
            <div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;
                        padding:16px 20px;margin-bottom:10px;display:flex;align-items:flex-start;gap:14px;">
                <div style="font-size:1.5rem;margin-top:2px">{icon}</div>
                <div>
                    <div style="font-size:0.9rem;font-weight:700;color:#e2e8f0">{title}</div>
                    <div style="font-size:0.8rem;color:#64748b;margin-top:4px;line-height:1.6">{desc}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Who it helps ──────────────────────────────────────────────────────
    st.markdown("### Who Benefits")
    industries = [
        ("🏦", "Financial Services",
         "Review vendor and cloud provider contracts for data security compliance before onboarding."),
        ("🏥", "Healthcare",
         "Verify that BAAs and service agreements meet HIPAA-aligned security obligations."),
        ("⚖️", "Legal & Procurement",
         "Accelerate contract review cycles and flag gaps before negotiations close."),
        ("🏛", "Government & Public Sector",
         "Ensure vendor contracts align with security frameworks like FedRAMP, NIST, or ISO 27001."),
        ("🏗", "Enterprise IT / CISO Office",
         "Continuously monitor a portfolio of active vendor contracts for compliance drift."),
    ]
    cols = st.columns(len(industries))
    for col, (icon, title, desc) in zip(cols, industries):
        col.markdown(
            f"""
            <div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;
                        padding:16px 12px;height:170px;">
                <div style="font-size:1.5rem">{icon}</div>
                <div style="font-size:0.8rem;font-weight:700;color:#e2e8f0;margin:6px 0 6px 0">{title}</div>
                <div style="font-size:0.72rem;color:#64748b;line-height:1.5">{desc}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Adaptability ──────────────────────────────────────────────────────
    st.markdown("### Adapt It to Any Use Case")
    st.markdown(
        """
        <div style="background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:28px 32px;">
            <div style="color:#94a3b8;font-size:0.88rem;line-height:1.9">
                The compliance questions are defined in a single file
                (<code style="color:#a855f7;background:#1e1035;padding:1px 5px;border-radius:3px">
                backend/compliance/questions.py</code>)
                as plain Python objects — no prompt engineering required to add new criteria.
                <br><br>
                <b style="color:#e2e8f0">Examples of other frameworks this system can be re-pointed at:</b>
            </div>
            <div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:18px;">
        """,
        unsafe_allow_html=True,
    )
    frameworks = ["SOC 2 Type II", "ISO 27001", "HIPAA", "GDPR", "NIST CSF", "PCI-DSS",
                  "FedRAMP", "CIS Controls", "CCPA", "Custom SLA Terms"]
    badges = "".join(
        f"<span style='background:#1e1b4b;color:#a78bfa;padding:5px 12px;"
        f"border-radius:16px;font-size:0.78rem;font-weight:600'>{f}</span>"
        for f in frameworks
    )
    st.markdown(
        f"<div style='display:flex;flex-wrap:wrap;gap:10px;padding:0 32px 28px 32px'>{badges}</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Footer contact ────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="background:#0f172a;border:1px solid #312e81;border-radius:12px;
                    padding:28px 32px;text-align:center;">
            <div style="font-size:0.75rem;color:#6b7280;letter-spacing:2px;
                        text-transform:uppercase;margin-bottom:8px;">Built by</div>
            <div style="font-size:1.1rem;font-weight:700;color:#e2e8f0">Farshid Mokhtarinezhad</div>
            <div style="font-size:0.82rem;color:#a855f7;margin:4px 0 12px 0">
                Senior AI Engineer · 247Labs
            </div>
            <a href="mailto:farshid.mokhtarinezhad@247labs.com"
               style="color:#64748b;font-size:0.8rem;text-decoration:none;">
                ✉ farshid.mokhtarinezhad@247labs.com
            </a>
            <div style="margin-top:16px;font-size:0.72rem;color:#374151;">
                © 2025 247Labs Inc. — All commercial use rights reserved.
                See NOTICE.md for full terms.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# PAGE: Law Library
# ─────────────────────────────────────────────

def page_law_library():
    st.header("Law Library")
    st.caption(
        "Upload any law or regulation as a PDF and give it a custom name. "
        "Once indexed, it appears in the Analyze Contract page as a check target. "
        "Uploaded laws are permanent — they persist across sessions."
    )

    st.subheader("Upload New Law")
    with st.form("upload_law_form", clear_on_submit=True):
        law_file = st.file_uploader("Law PDF", type=["pdf"], help="Official act / regulation PDF")
        col_id, col_name = st.columns(2)
        with col_id:
            law_id_input = st.text_input(
                "Law ID (no spaces)",
                placeholder="e.g. ontario-law-2026",
                help="Unique identifier. Only letters, numbers, hyphens.",
            )
        with col_name:
            display_name_input = st.text_input(
                "Display Name",
                placeholder="e.g. Ontario ESA 2026",
                help="Human-readable label shown in the law selector.",
            )
        submitted = st.form_submit_button("Upload & Index", type="primary")

    if submitted:
        if law_file is None:
            st.error("Please select a PDF file.")
        elif not law_id_input.strip():
            st.error("Law ID is required.")
        elif not display_name_input.strip():
            st.error("Display Name is required.")
        else:
            with st.spinner(f"Uploading and indexing '{display_name_input}'…"):
                resp = _call_api(
                    "post",
                    "/laws",
                    files={"file": (law_file.name, law_file.getvalue(), "application/pdf")},
                    data={"law_id": law_id_input.strip(), "display_name": display_name_input.strip()},
                )
            if resp:
                st.success(
                    f"Law **{resp['display_name']}** accepted for indexing. "
                    f"Refresh in a moment to see it as 'ready'."
                )

    st.divider()
    st.subheader("Indexed Laws")

    all_laws_raw = _call_api("get", "/laws") or []

    if not all_laws_raw:
        st.info("No laws indexed yet. Upload your first law PDF above.")
    else:
        for law in all_laws_raw:
            status = law.get("status", "unknown")
            status_color = {"ready": "#2ecc71", "indexing": "#f39c12", "failed": "#e74c3c"}.get(status, "#95a5a6")
            status_label = {"ready": "✅ Ready", "indexing": "⏳ Indexing…", "failed": "❌ Failed"}.get(status, status)

            with st.expander(
                f"**{law['display_name']}**  —  `{law['law_id']}`  —  "
                f"<span style='color:{status_color}'>{status_label}</span>",
                expanded=False,
            ):
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"**File:** {law.get('filename', '—')}")
                c2.markdown(f"**Chunks:** {law.get('chunk_count', 0)}")
                c3.markdown(f"**Uploaded:** {str(law.get('uploaded_at', ''))[:16].replace('T', ' ')}")
                c1.markdown(f"**Collection:** `{law.get('collection_name', '—')}`")
                c2.markdown(
                    f"<span style='color:{status_color};font-weight:600'>{status_label}</span>",
                    unsafe_allow_html=True,
                )
                if status == "ready":
                    if st.button("Delete", key=f"del_law_{law['law_id']}", type="secondary"):
                        result = _call_api("delete", f"/laws/{law['law_id']}")
                        if result:
                            st.success(f"Law '{law['law_id']}' deleted.")
                            st.rerun()

    if st.button("Refresh", key="refresh_laws"):
        st.rerun()


# ─────────────────────────────────────────────
# Router
# ─────────────────────────────────────────────

if page == "Guide":
    page_guide()
elif page == "Law Library":
    page_law_library()
elif page == "Analyze Contract":
    page_analyze()
elif page == "KPI Dashboard":
    page_dashboard()
elif page == "Chat":
    page_chat()
elif page == "Process Monitor":
    page_monitor()
