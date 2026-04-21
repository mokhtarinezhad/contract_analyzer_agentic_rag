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
from pathlib import Path

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
)

configure_logging()
init_db()

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")

# ─────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="Contract Analyzer",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# Sidebar navigation
# ─────────────────────────────────────────────

with st.sidebar:
    st.title("Contract Analyzer")
    st.caption("Senior Data Scientist Assessment | Manulife")
    st.divider()

    page = st.radio(
        "Navigate",
        ["Analyze Contract", "KPI Dashboard", "Chat"],
        index=0,
    )

    st.divider()
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

def page_analyze():
    st.header("Contract Compliance Analysis")
    st.caption(
        "Upload a PDF contract. The system will analyse it against 5 compliance "
        "requirements using an Agentic RAG pipeline."
    )

    # ── Upload ────────────────────────────────────────────────────────────
    uploaded = st.file_uploader(
        "Upload PDF Contract",
        type=["pdf"],
        help="Born-digital PDF recommended. Max 50 MB.",
    )

    if uploaded is None:
        st.info("Upload a PDF contract to begin analysis.")
        return

    col1, col2 = st.columns([1, 3])
    with col1:
        st.metric("File", uploaded.name)
        st.metric("Size", f"{uploaded.size / 1024:.1f} KB")
    with col2:
        analyze_btn = st.button("Analyze Contract", type="primary", use_container_width=True)

    if analyze_btn:
        # ── Submit job ────────────────────────────────────────────────────
        with st.spinner("Submitting analysis job..."):
            response = _call_api(
                "post",
                "/analyze",
                files={"file": (uploaded.name, uploaded.getvalue(), "application/pdf")},
            )

        if response is None:
            return

        job_id = response["job_id"]
        trace_id = response["trace_id"]
        contract_id = response.get("contract_id", "")

        st.success(f"Job started — ID: `{job_id}`")
        st.caption(f"Trace ID: `{trace_id}`")

        # Store in session for chat and result persistence
        st.session_state["contract_id"] = contract_id
        st.session_state["last_job_id"] = job_id
        st.session_state["last_trace_id"] = trace_id
        st.session_state["last_result"] = None  # clear previous result

        # ── Poll for results ──────────────────────────────────────────────
        progress_bar = st.progress(0, text="⏳ Submitting job...")
        status_area = st.empty()
        steps_done = st.empty()

        step_labels = {
            "pending":     "⏳ Queued — waiting to start...",
            "parsing_pdf": "📄 Step 1/5 — Parsing PDF (extracting text, tables, layout)...",
            "chunking":    "✂️  Step 2/5 — Chunking into section-aware passages...",
            "embedding":   "🔢 Step 3/5 — Embedding chunks with sentence-transformers...",
            "indexing":    "🗄️  Step 4/5 — Indexing vectors into ChromaDB...",
            "retrieving":  "🔍 Step 5/5 — Retrieving evidence per sub-criterion (hybrid search)...",
            "analyzing":   "🤖 Step 5/5 — Compliance Agent analysing all 5 questions in parallel...",
            "evaluating":  "🧐 Step 5/5 — Evaluator checking quotes and grading outputs...",
            "completed":   "✅ Analysis complete!",
        }

        step_order = ["pending", "parsing_pdf", "chunking", "embedding",
                      "indexing", "retrieving", "analyzing", "evaluating", "completed"]
        completed_steps = []

        for _ in range(720):  # 12-minute timeout at 1s intervals
            time.sleep(1)
            poll = _call_api("get", f"/results/{job_id}")
            if poll is None:
                break

            status = poll.get("status", "pending")
            pct = poll.get("progress_pct", 0)
            label = step_labels.get(status, status)

            # Track which steps we've seen so fast steps aren't lost
            if status not in completed_steps and status != "completed":
                completed_steps.append(status)

            progress_bar.progress(pct / 100, text=label)

            # Show breadcrumb of completed steps
            if len(completed_steps) > 1:
                done = " → ".join(
                    step_labels.get(s, s).split("—")[0].strip()
                    for s in completed_steps[:-1]
                )
                steps_done.caption(f"Done: {done}")

            if status == "completed":
                st.session_state["last_result"] = poll.get("result")
                progress_bar.progress(1.0, text="✅ Analysis complete!")
                break
            elif status == "failed":
                st.error(f"Analysis failed: {poll.get('error', 'Unknown error')}")
                return

        if st.session_state.get("last_result") is None:
            st.warning("Analysis timed out or result not available. Try polling manually.")
            return

    # ── Analysis history browser ──────────────────────────────────────────
    st.divider()
    st.subheader("Previous Analyses")
    history_df = get_analyses_df(limit=20)
    if history_df.empty:
        st.caption("No previous analyses yet.")
    else:
        for _, row in history_df.iterrows():
            ts = row.get("analysis_timestamp", "")[:16].replace("T", " ")
            label = f"📄 {row['filename']}  —  {ts}  —  conf: {row.get('avg_confidence', 0):.0%}"
            if st.button(label, key=f"hist_{row['trace_id']}"):
                raw = get_full_result(row["trace_id"])
                if raw:
                    st.session_state["last_result"] = json.loads(raw)
                    st.session_state["last_trace_id"] = row["trace_id"]
                    st.session_state["contract_id"] = row.get("contract_id", "")
                    st.rerun()
                else:
                    st.warning("Full result not stored for this analysis (run before history was enabled).")

    # ── Display results (persists across reruns) ──────────────────────────
    result_data = st.session_state.get("last_result")
    trace_id = st.session_state.get("last_trace_id", "")
    if result_data:
        _render_results(result_data, trace_id)


def _render_results(result_data: dict, trace_id: str):
    st.divider()
    st.subheader("Compliance Analysis Results")

    results = result_data.get("results", [])
    meta = result_data.get("processing_metadata", {})

    # Summary cards
    c1, c2, c3, c4 = st.columns(4)
    fully = sum(1 for r in results if r["compliance_state"] == "Fully Compliant")
    partial = sum(1 for r in results if r["compliance_state"] == "Partially Compliant")
    non = sum(1 for r in results if r["compliance_state"] == "Non-Compliant")
    avg_conf = sum(r["confidence"] for r in results) / max(len(results), 1)

    c1.metric("Fully Compliant", fully, delta=None)
    c2.metric("Partially Compliant", partial)
    c3.metric("Non-Compliant", non)
    c4.metric("Avg Confidence", f"{avg_conf:.0%}")

    st.divider()

    # Per-question expandable cards
    for result in results:
        state = result.get("compliance_state", "Unknown")
        emoji = STATE_EMOJI.get(state, "")
        conf = result.get("confidence", 0)
        title = result.get("question_title", "")

        with st.expander(f"{emoji} Q{result.get('question_id', '?')}: {title} — {state} ({conf:.0%})", expanded=(state != "Fully Compliant")):
            col_a, col_b = st.columns([1, 2])

            with col_a:
                st.markdown(f"**State:** {_state_badge(state)}", unsafe_allow_html=True)
                st.markdown(f"**Confidence:** {_confidence_bar(conf)}", unsafe_allow_html=True)
                if result.get("retry_count", 0) > 0:
                    st.warning(f"Retried {result['retry_count']} time(s)")

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

            # Sub-criteria table
            sc_results = result.get("sub_criteria_results", [])
            if sc_results:
                st.markdown("**Sub-criteria Coverage**")
                sc_df = pd.DataFrame([
                    {
                        "ID": sc["criterion_id"],
                        "Description": sc["description"][:70] + "...",
                        "Found": "✅" if sc["found"] else "❌",
                        "Evidence": sc.get("evidence_summary", "")[:100],
                    }
                    for sc in sc_results
                ])
                st.dataframe(sc_df, use_container_width=True, hide_index=True)

            # Relevant quotes
            quotes = result.get("relevant_quotes", [])
            if quotes:
                st.markdown("**Relevant Contract Quotes**")
                for q in quotes:
                    st.markdown(
                        f"> *\"{q['text']}\"*  \n"
                        f"> — {q.get('section_reference', 'Unknown section')}"
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

    # ── KPI rationale expander (for interview) ────────────────────────────
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
# Router
# ─────────────────────────────────────────────

if page == "Analyze Contract":
    page_analyze()
elif page == "KPI Dashboard":
    page_dashboard()
elif page == "Chat":
    page_chat()
