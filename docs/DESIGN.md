# Design Document

This document explains the major design decisions behind the Contract Analyzer,
the trade-offs considered, and the rationale for every choice. It is intended
to be read alongside `ARCHITECTURE.md` (diagrams) and `MCP_CONNECTOR.md` (MCP
and external-connector design).

---

## 1. Design goals and constraints

The system is scoped to behave as a production prototype, not a notebook:

| Goal | Implication |
|------|-------------|
| Deterministic structured output | Pydantic validation at every boundary; tool-forced LLM output for the compliance agent |
| Grounded answers | Verbatim quote extraction with a deterministic fuzzy-match hallucination check |
| Observable in production | Structured JSON logging with trace/span IDs; SQLite metrics store; per-stage latency capture |
| Low cost / local-first | Local embeddings, in-process vector store, no external infra |
| Extensible | Clean agent boundaries, MCP server wrapper, FastAPI auto-OpenAPI |
| Reproducible demo | Single `setup.sh`, `.env.example`, no cloud dependencies beyond the LLM provider |

---

## 2. Pipeline stages and the decisions behind them

### 2.1 PDF parsing — `unstructured.io` (`hi_res`)

**Decision.** Use `unstructured[pdf]` with the `hi_res` strategy.

**Why.** Compliance evidence frequently lives inside tables (cipher suite lists,
password policy grids, authentication summary tables). `hi_res` uses a layout
model that returns `Title`, `NarrativeText`, `Table` (with `text_as_html`), and
coordinate metadata. That lets the chunker keep tables atomic and propagate
section hierarchy — critical for the Router Agent's section hints.

**Alternatives considered.**
- *PyMuPDF / pdfplumber* — faster, but collapse tables into line-order text. Bad
  for compliance because a cipher-suite table becomes an unsorted blob.
- *LlamaParse / AWS Textract* — better quality, but add a paid dependency and a
  network round-trip per document. Not justified for the assignment scope.
- *`unstructured fast` strategy* — falls back to pdfminer; loses table HTML.

**Trade-off.** `hi_res` is 3–8× slower than `fast` on born-digital PDFs. We
accept this because table fidelity drives compliance accuracy directly and
parsing runs once per contract (not per query).

### 2.2 Chunking — section-aware, atomic tables

**Decision.** Group consecutive elements under the nearest `Title`, never split
a `Table` across chunks, merge fragments below `MIN_CHUNK_WORDS=20` into their
predecessor, cap text chunks at `MAX_CHUNK_WORDS=400`.

**Why.** Fixed-size token windows (the LangChain default) do three bad things
on legal contracts:
1. Shred tables mid-row, losing the row's semantic unit.
2. Straddle section boundaries so a chunk contains the tail of `Section 6.2`
   and the head of `Section 6.3` — confusing for downstream agents that cite
   "Section X.Y".
3. Over-emit tiny orphan chunks for short list items.

Section-aware chunking preserves the structural signal the compliance agent
needs when it cites evidence.

**Trade-off.** Variable chunk sizes make embedding cost less predictable and
complicate similarity scoring across chunks of very different lengths.
Acceptable because retrieval is downstream-evaluated by the LLM, not returned
directly.

### 2.3 Table embedding — LLM-generated prose descriptions

**Decision.** For each `Table` element we ask Claude to write a 2–4 sentence
natural-language description of what the table encodes. The description is
what gets embedded; the original HTML is what gets returned to the
compliance agent as evidence. (`backend/ingestion/table_describer.py`,
wired in `chunker._build_table_texts`.)

**Why.** The embedding model (`all-MiniLM-L6-v2`) is a sentence encoder
trained on prose. A linearised table dump (`row1col1 row1col2 row2col1 ...`)
sits far from natural-language queries in vector space — the exact cell that
answers "password length requirements for admins" may not be retrieved because
the query wording does not appear in the cell content. The LLM prose
description bridges that gap without losing the HTML structure that the
compliance agent needs for verbatim quotation.

**Trade-off.** Adds one LLM call per table at ingestion time. For a typical
contract this is a handful of calls and a few cents. The retrieval quality
gain on table-heavy sections (which carry a lot of compliance evidence) is
substantial.

### 2.4 Embeddings — `sentence-transformers/all-MiniLM-L6-v2`

**Decision.** Local sentence-transformers model (384-dim, ~80MB).

**Why.** Free, fast, no API dependency, deterministic. Good enough for
in-document retrieval where we only need to rank chunks of a single contract
against a few well-phrased sub-criterion queries.

**Alternatives considered.**
- *OpenAI text-embedding-3-small / Voyage voyage-2* — better on legal text,
  but adds a second paid API and introduces a failure mode (network, rate
  limit, cost). Worth it for multi-contract corpora; overkill here.
- *BAAI/bge-small-en-v1.5 or nomic-embed-text-v1.5* — stronger open-source
  options. A drop-in upgrade (swap the string in `config.py`) if the
  production workload demands it. Left as a documented future improvement.

**Trade-off.** MiniLM underperforms larger encoders on domain-specific legal
phrasing. Partly compensated by (a) the Router Agent rewriting queries into
retrieval-friendly language, and (b) section hinting that re-ranks by
structural signal.

### 2.5 Vector store — ChromaDB (in-process, persistent)

**Decision.** One collection per contract, keyed by `contract_id`, stored on
disk at `./data/chroma_db`.

**Why.** Zero-infra, in-process, cosine similarity, metadata filtering, safe
to reset. One-collection-per-contract isolates every analysis so chat /
follow-up retrieval cannot leak across contracts.

**Alternatives considered.**
- *Qdrant / Weaviate* — richer filtering and scale, but require running a
  server. Not justified for single-document retrieval.
- *FAISS* — faster nearest-neighbour, but no metadata filtering, no
  persistence story out of the box.
- *pgvector* — attractive for a deployment that already runs Postgres; not the
  case here.

**Trade-off.** Per-contract collections accumulate on disk. We ship a
`DELETE /contracts/{id}` endpoint for cleanup; production should add a TTL
or cleanup-after-chat-expires job.

### 2.6 Retrieval — hybrid semantic + section targeting

**Decision.** For each sub-criterion query, run a broad semantic search
(`top_k * 2`), then run additional targeted searches restricted to the sections
the Router Agent predicts, then merge with priority on section-targeted hits.
(`backend/rag/retriever.py::retrieve_for_query`.)

**Why.** Pure semantic search misses evidence that is structurally predictable
but semantically distant — e.g. a cell in "Exhibit G3A — Password Requirements"
that says "admin 14+ chars" ranks poorly on the query "password length
requirements" alone. The Router supplies a list of likely section titles, we
re-run retrieval filtered to those, and merge. This is the "router does more
than routing" pattern.

**Trade-off.** Two-pass retrieval doubles vector-store calls. Cost is
negligible because ChromaDB is in-process and embeddings are cached.

### 2.7 Agent orchestration — LangGraph

**Decision.** LangGraph `StateGraph` with three nodes per question (router,
compliance, evaluator), a conditional edge from evaluator back to compliance
for retries, and asyncio-driven fan-out of all 5 questions.
(`backend/agents/orchestrator.py`.)

**Why.**
- *Typed state.* `QuestionState` is a `TypedDict`; state flow is explicit and
  inspectable.
- *Visualisable.* `graph.get_graph().draw_mermaid_png()` renders the topology
  for demos and documentation.
- *Conditional edges.* The retry loop is a first-class graph feature, not an
  ad-hoc while-loop.
- *Interrupts and replays.* LangGraph supports checkpointing, which is a
  natural extension path for human-in-the-loop review (future work).

**Alternatives considered.**
- *LangChain Runnable / LCEL* — simpler for linear pipelines, but the retry
  edge is awkward without extra plumbing.
- *CrewAI / AutoGen* — higher-level, more opinionated; would have imposed
  their own messaging and role semantics that don't match the deterministic
  compliance workflow.
- *Hand-rolled orchestration* — would have worked, but LangGraph's typed
  state and conditional-edge pattern is exactly the shape of this problem,
  and it gives a defensible answer to "which framework and why".

**Trade-off.** LangGraph `.invoke` is synchronous; we run it inside
`loop.run_in_executor(...)` to enable asyncio fan-out across the 5 questions.
Clean enough; an async-native alternative would avoid the thread pool.

### 2.8 Router Agent — decompose + plan + retrieve

**Decision.** The Router is an LLM that, given a compliance question and its
declared sub-criteria, emits a JSON array of `{sub_id, query, likely_sections}`.
A deterministic fallback produces a keyword-based plan if the JSON does not
parse.

**Why decompose.** The 5 compliance questions bundle 4–7 sub-criteria each.
A single retrieval query for "Password Management" returns a grab-bag of
chunks; per-sub-criterion queries produce more targeted evidence and let the
compliance agent give each sub-criterion its own `found / evidence_summary`.

**Why LLM-generated queries vs deterministic.** Sub-criterion descriptions
are written in policy language ("prohibition on default and known-compromised
passwords"). Contract language typically phrases the same thing differently
("shall not permit default credentials"). The LLM rewrites each sub-criterion
into a retrieval-friendly query that matches contract phrasing better.

**Trade-off.** One LLM call per question just for planning. Offset by parallel
execution; total wall-clock is bounded by the slowest question.

### 2.9 Compliance Agent — tool-forced structured output

**Decision.** `bind_tools([submit_compliance_result], tool_choice="tool")`.
Claude is forced to call the tool, which means its output is schema-validated
by Anthropic's API before it ever reaches our Pydantic layer.

**Why.** Legal-risk systems cannot accept free-text JSON that sometimes
parses. Tool-forced output eliminates an entire class of failure modes (missing
fields, mis-typed enums, trailing commas). The Pydantic validator is then a
second net, not the first line of defence.

**Trade-off.** Tool forcing is slightly more expensive in tokens than prompting
"return JSON". Worth it.

### 2.10 Evaluator Agent — three-layer critic

**Decision.** Three independent layers:
1. **Deterministic.** Fuzzy-match each cited quote against the retrieved source
   chunks (`SequenceMatcher`, substring fast-path, 0.80 threshold). Quotes that
   do not match are flagged as potential hallucinations.
2. **LLM critic.** A second Claude call reviews completeness, consistency,
   confidence calibration, and groundedness. Emits verdict + issues + a
   confidence adjustment in [-0.3, 0.3].
3. **Decision.** If verdict is `FAIL` and `retry_count < MAX_RETRIES`, send
   the critique back to the Compliance Agent as feedback and re-run. If
   hallucinations were found, penalise confidence by 0.10 per flag and demote
   `Fully Compliant` → `Partially Compliant` if confidence drops below 0.5.

**Why three layers.** Each layer catches a different failure mode.
- Deterministic layer catches fabricated quotes (hardest-to-detect hallucination).
- LLM critic catches reasoning errors the deterministic layer cannot see
  (right quote, wrong conclusion).
- Decision layer converts "we think this is wrong" into a concrete action
  (retry vs demote vs pass-with-flags).

**Trade-off.** Every question now costs 2–3 LLM calls instead of 1. Justified
because the alternative is silently shipping wrong compliance determinations,
which is strictly worse than a slower analysis.

### 2.11 Retry strategy

**Decision.** Up to `MAX_RETRY_COUNT=2` retries per question. On retry, the
compliance agent receives its previous answer plus the evaluator's critique
as a multi-turn conversation.

**Why conversational retry.** Sending only the critique without the previous
answer forces the agent to re-derive state. Sending the previous answer as
an `AIMessage` gives the model context to correct specific issues rather than
regenerate from scratch.

**Trade-off.** Retry cost is ~1.5× the first call. Capped at 2 retries to
bound the worst case.

### 2.12 Structured output validation — Pydantic v2

**Decision.** Every agent output and API response is a Pydantic model. A
`@model_validator` on `ComplianceResult` enforces that `Fully Compliant`
implies `confidence >= 0.5`.

**Why.** Validation at the boundary, not in the caller. A downstream consumer
of the JSON can trust the contract.

**Trade-off.** The validator can raise on genuinely malformed LLM output. The
evaluator demotes state in that scenario before it reaches the validator, so
this is a defence-in-depth check rather than the primary correction mechanism.

---

## 3. Observability

### 3.1 Structured logging — `structlog` JSON

**Decision.** One JSON line per event, written to `logs/app.jsonl` and stdout.
Every event carries `trace_id` (analysis-wide) and `span_id` (per-operation).
The root trace_id propagates through parsing, chunking, embedding, all 5
agent loops, and metrics persistence.

**Why.** Structured logs let the panel grep a single `trace_id` and
reconstruct the full pipeline for any analysis:

    grep '"trace_id":"<id>"' logs/app.jsonl | jq .

Free-text logs do not support that workflow.

### 3.2 Metrics store — SQLite

**Decision.** Three tables — `analyses`, `question_results`, `agent_spans` —
written directly by the orchestrator, read back as pandas DataFrames for
Streamlit charting.

**Why SQLite.**
- Zero infrastructure. Ships with Python.
- Queryable. The same store powers ad-hoc KPI queries during demos and live presentations.
- Persistent across restarts, unlike an in-memory metric registry.
- Good fit for the take-home scope (dozens to hundreds of analyses).

**Alternatives considered.**
- *Prometheus + Grafana* — the "correct" production answer. Excessive for a
  take-home demo; documented as a future migration in the architecture doc.
- *OpenTelemetry / Langfuse* — richer trace model (explicit spans, attributes,
  OTLP export). Planned extension; the current structlog + SQLite approach
  exposes the same information and can be replayed into OTel later without
  changing application code.

**Trade-off.** SQLite writes from a multi-threaded executor require a
`threading.Lock`. Simple; the fan-out is already rate-limited by the LLM calls.

### 3.3 KPI selection

KPIs are chosen to cover the four axes a production GenAI compliance system
has to answer for:

| Axis | KPI | Why this KPI |
|------|-----|--------------|
| User experience | End-to-end latency p95 | Direct UX signal; degrades first when any stage regresses |
| Quality | Avg confidence | Proxy for retrieval/reasoning quality; drops on weak evidence or model drift |
| Safety | Hallucination rate | Fraction of questions with unverified quotes; direct compliance-accuracy risk |
| Self-assessment | Evaluator retry rate | Fraction of questions that needed re-analysis; high value = agent quality eroding |
| Cost | Cost per analysis | Budget control; changes immediately visible after any model/prompt change |

Thresholds and actions are published in the UI's "KPI Rationale" panel so the
panel can challenge and discuss each one live.

---

## 4. Security, cost, and operational considerations

### 4.1 Secrets

`ANTHROPIC_API_KEY` is loaded from `.env`, which is gitignored. `.env.example`
documents the required variables without any real value.

### 4.2 Cost control

Every LLM call logs `input_tokens` and `output_tokens`. The orchestrator
converts them to USD using the model's published rate and persists the
per-analysis cost. Cost is displayed per-analysis in the UI and aggregated in
the KPI dashboard so regressions are visible the first time they happen.

A known limitation: the per-token rate table currently covers the default
model. When switching models, update the rate lookup alongside the model
name to keep cost tracking accurate.

### 4.3 Data isolation

Each contract gets its own ChromaDB collection. There is no cross-contract
retrieval path. Deleting a contract's collection deletes all of its vectors
but leaves the metrics in SQLite (intentionally — metrics are anonymised
operational signal).

### 4.4 Known limitations (honest list)

- **In-memory job store.** `_jobs` in `api/routes.py` is a Python dict. On API
  restart, running jobs are lost. Production should persist to SQLite or
  Redis. Single-replica demo deployments are unaffected.
- **Collection accumulation.** ChromaDB collections are not garbage collected.
  Production should add a TTL sweeper.
- **Large-document guardrails.** No hard cap on PDF size or element count.
  A 500-page contract will be processed without warning.
- **Retrieval ceiling.** MiniLM-L6-v2 is the weakest modern encoder. Upgrading
  to `bge-small-en-v1.5` or a Voyage embedding would measurably improve
  recall on legal phrasing.
- **Evaluator LLM response** is parsed from free-text JSON with a fallback
  rather than tool-forced. Applying the compliance agent's tool-forced
  pattern would eliminate the parse-failure branch.

---

## 5. Extensibility

The system is organised for three concrete extensions:

1. **New compliance questions.** Add a `ComplianceQuestion` in
   `backend/compliance/questions.py` with sub-criteria and section hints. No
   code changes elsewhere.
2. **New LLM provider.** Replace `langchain_anthropic.ChatAnthropic` in the
   three agent modules. The rest of the pipeline is provider-agnostic.
3. **New interface.** The MCP server (`backend/mcp/server.py`) already exposes
   the analyser as tool endpoints; a REST connector re-uses the same FastAPI
   backend and can be published as an OpenAPI spec. See `MCP_CONNECTOR.md`
   for the full design.
