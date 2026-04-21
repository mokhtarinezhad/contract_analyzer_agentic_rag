# Contract Analyzer · 247Labs

> **Proprietary Software** — © 2025 [247Labs Inc.](https://247labs.com)
> Developed by **Farshid Mokhtarinezhad**, Senior AI Engineer.
> Commercial use is permitted solely by 247Labs Inc. and its authorised representatives.
> See [NOTICE.md](./NOTICE.md) for full terms.

A production-grade contract compliance analysis demo built for **247Labs Inc.**,
demonstrating an end-to-end Agentic RAG pipeline — extract, retrieve, analyse, and
verify compliance against security requirements with grounded, hallucination-checked
structured output.

## Quick Start

```bash
# 1. Clone / navigate to project root
cd contract_analyzer

# 2. One-command setup (creates venv, installs deps, downloads embedding model)
bash setup.sh

# 3. Add your Anthropic API key
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env

# 4. Start API server (terminal 1)
source .venv/bin/activate
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload

# 5. Start Streamlit UI (terminal 2)
source .venv/bin/activate
streamlit run frontend/app.py

# 6. Open http://localhost:8501
```

## Architecture

```
PDF Upload (Streamlit)
       │
       ▼
FastAPI /analyze
       │
       ▼
┌──────────────────────────────────────────────┐
│  Ingestion Pipeline                           │
│  parse_pdf (unstructured.io)                  │
│  chunk_elements (section-aware)               │
│  embed_texts (sentence-transformers)          │
│  index_chunks (ChromaDB)                      │
└──────────────────────────────────────────────┘
       │
       ▼ (5 questions in parallel via asyncio)
┌──────────────────────────────────────────────┐
│  LangGraph Agent Loop (per question)          │
│                                               │
│  ROUTER → decompose question → hybrid         │
│           retrieval (semantic + section hint) │
│      │                                        │
│      ▼                                        │
│  COMPLIANCE → analyse chunks → structured     │
│              JSON output                      │
│      │                                        │
│      ▼                                        │
│  EVALUATOR → Layer 1: fuzzy hallucination     │
│              check (deterministic)            │
│            → Layer 2: LLM critic              │
│            → Layer 3: retry decision          │
│      │                                        │
│      ├─ PASS ────────────────────────► END    │
│      └─ FAIL (retry_count < 2) ──► COMPLIANCE│
└──────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│  Output                                       │
│  Pydantic-validated ContractAnalysisResponse  │
│  SQLite metrics persistence                   │
│  Structured JSON logs (trace_id / span_id)    │
└──────────────────────────────────────────────┘
```

## Compliance Questions Analysed

| # | Requirement |
|---|-------------|
| 1 | Password Management |
| 2 | IT Asset Management |
| 3 | Security Training & Background Checks |
| 4 | Data in Transit Encryption |
| 5 | Network Authentication & Authorization Protocols |

## Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| LLM | Claude (Anthropic) | Best structured output; native JSON mode |
| PDF Parsing | unstructured.io | Best table extraction; handles mixed layouts |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Local, free, no extra API |
| Vector Store | ChromaDB | Zero-infra, in-process, persistent |
| Agent Orchestration | LangGraph | Typed state, conditional retry edges, visualisable |
| Backend | FastAPI | Async, auto-OpenAPI spec, Pydantic native |
| Frontend | Streamlit | Python-native, production-appropriate for internal tools |
| Logging | structlog (JSON) | Structured, trace/span IDs, parseable |
| Metrics | SQLite | Zero-infra, directly queryable by Streamlit |
| MCP Server | mcp SDK | Exposes analysis as an MCP tool (compatible with any MCP client) |

## Project Structure

```
.
├── backend/
│   ├── compliance/
│   │   ├── questions.py        # 5 compliance question definitions + sub-criteria
│   │   └── schemas.py          # Pydantic output models
│   ├── ingestion/
│   │   ├── pdf_parser.py       # unstructured.io PDF parsing
│   │   ├── chunker.py          # Section-aware chunking
│   │   └── embedder.py         # sentence-transformers wrapper
│   ├── rag/
│   │   ├── vector_store.py     # ChromaDB wrapper
│   │   └── retriever.py        # Hybrid semantic + section retrieval
│   ├── agents/
│   │   ├── router_agent.py     # Decomposes questions, plans retrieval
│   │   ├── compliance_agent.py # Generates compliance determination
│   │   ├── evaluator_agent.py  # 3-layer critic + hallucination check
│   │   └── orchestrator.py     # LangGraph pipeline + async parallelism
│   ├── observability/
│   │   ├── logger.py           # structlog JSON logger
│   │   └── metrics_store.py    # SQLite metrics persistence
│   ├── api/
│   │   ├── main.py             # FastAPI app
│   │   └── routes.py           # Endpoints
│   └── mcp/
│       └── server.py           # MCP tool server
├── frontend/
│   └── app.py                  # Streamlit UI (3 pages)
├── docs/
├── data/                       # ChromaDB + SQLite (auto-created)
├── logs/                       # JSONL log output (auto-created)
├── requirements.txt
├── .env.example
├── setup.sh
└── README.md
```

## KPI Dashboard Metrics

| KPI | Target | Alert Threshold | Action |
|-----|--------|-----------------|--------|
| End-to-end latency p95 | < 30s | > 45s | Check span timings |
| Avg confidence | > 65% | < 50% | Review retrieval recall |
| Hallucination rate | < 5% | > 10% | Audit flagged quotes |
| Retry rate | < 20% | > 30% | Review agent prompts |
| Cost per analysis | < $0.10 | > $0.20 | Reduce top-k or chunk size |

## MCP Server

Start the MCP server:
```bash
python -m backend.mcp.server
```

Add to Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "contract-analyzer": {
      "command": "python",
      "args": ["-m", "backend.mcp.server"],
      "cwd": "/path/to/contract_analyzer",
      "env": {"ANTHROPIC_API_KEY": "sk-ant-..."}
    }
  }
}
```

## Observability

All logs are JSON-formatted in `logs/app.jsonl`. Follow a request:
```bash
grep '"trace_id":"<your-trace-id>"' logs/app.jsonl | jq .
```

Example log events:
- `pdf_parse_start/complete` — parsing timing
- `chunking_complete` — chunk count and word stats
- `router_llm_call_start/complete` — token usage
- `router_query_plan` — which sections targeted per sub-criterion
- `compliance_agent_llm_call` — retry context
- `evaluator_complete` — verdict, hallucination flags, confidence adjustment
- `analysis_pipeline_complete` — full summary with cost

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Required |
| `LLM_MODEL` | `claude-sonnet-4-6` | Claude model |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model |
| `CHROMA_PERSIST_DIR` | `./data/chroma_db` | Vector store persistence |
| `METRICS_DB_PATH` | `./data/metrics.db` | SQLite metrics |
| `LOG_FILE_PATH` | `./logs/app.jsonl` | JSON log output |
| `MAX_RETRY_COUNT` | `2` | Evaluator retry limit |
| `HALLUCINATION_MATCH_THRESHOLD` | `0.80` | Fuzzy match threshold |
