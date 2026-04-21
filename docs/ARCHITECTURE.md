# Architecture

Diagrams and data-flow for the Contract Analyzer. Read together with
`DESIGN.md` (rationale) and `MCP_CONNECTOR.md` (external integrations).

---

## 1. System overview

```mermaid
flowchart TB
    subgraph Clients
        UI[Streamlit UI]
        MCPClient[MCP Client<br/>Claude Desktop / Cursor]
        HTTPClient[HTTP Client<br/>ChatGPT / Copilot / Custom]
    end

    subgraph EdgeLayer["Edge / Interface Layer"]
        MCP[MCP Server<br/>backend/mcp/server.py]
        API[FastAPI<br/>backend/api/*]
    end

    subgraph Core["Analysis Core"]
        Ingest[Ingestion<br/>parse - chunk - embed - index]
        Agents[Agentic Pipeline<br/>LangGraph]
        Chat[Chat Endpoint<br/>semantic Q&A]
    end

    subgraph Storage
        Chroma[(ChromaDB<br/>per-contract<br/>collections)]
        SQLite[(SQLite<br/>analyses<br/>question_results<br/>agent_spans)]
        Logs[(JSONL Logs<br/>trace_id / span_id)]
    end

    UI --> API
    MCPClient --> MCP
    HTTPClient --> API
    MCP --> API

    API --> Ingest
    API --> Agents
    API --> Chat
    API --> SQLite

    Ingest --> Chroma
    Agents --> Chroma
    Chat --> Chroma
    Agents --> SQLite

    Ingest -.log.-> Logs
    Agents -.log.-> Logs
    API -.log.-> Logs
```

---

## 2. Request flow — PDF upload to JSON result

```mermaid
sequenceDiagram
    participant U as User
    participant UI as Streamlit
    participant API as FastAPI
    participant O as Orchestrator
    participant P as Parser
    participant C as Chunker
    participant E as Embedder
    participant V as ChromaDB
    participant R as Router Agent
    participant A as Compliance Agent
    participant EV as Evaluator Agent
    participant M as Metrics DB

    U->>UI: Upload PDF
    UI->>API: POST /analyze (multipart)
    API->>API: Generate job_id, trace_id, contract_id
    API-->>UI: 200 {job_id, trace_id}
    API->>O: background task: analyse_contract()
    UI->>API: GET /results/{job_id} (poll)

    O->>P: parse_pdf()
    P-->>O: List[ParsedElement]
    O->>C: chunk_elements()
    C-->>O: List[DocumentChunk]
    O->>E: embed_texts()
    E-->>O: embeddings
    O->>V: index_chunks(contract_id)

    par 5 questions in parallel
        O->>R: run_router_agent(Q1)
        R->>V: semantic_search x sub_criteria
        V-->>R: chunks
        R-->>O: RouterDecision
        O->>A: run_compliance_agent(Q1)
        A-->>O: ComplianceResult
        O->>EV: run_evaluator_agent(Q1)
        EV-->>O: {verdict, issues, confidence_adj}
        alt verdict == FAIL and retries_left
            O->>A: retry with critique
            A-->>O: revised ComplianceResult
        end
    and
        O->>R: ... Q2-Q5 ...
    end

    O->>M: record_analysis + record_question_result x 5
    O-->>API: ContractAnalysisResponse (5 validated results)
    UI->>API: GET /results/{job_id}
    API-->>UI: {status: completed, result: ...}
    UI-->>U: Render compliance cards + KPI dashboard
```

---

## 3. Per-question agent graph (LangGraph)

```mermaid
flowchart LR
    START([Start]) --> Router[Router Agent]
    Router -->|"chunks + sub-criterion<br/>query plan"| Compliance[Compliance Agent]
    Compliance -->|"ComplianceResult<br/>tool-forced JSON"| Evaluator[Evaluator Agent]
    Evaluator -->|"PASS / PASS_WITH_FLAGS"| END([End])
    Evaluator -->|"FAIL and retry_count < 2"| Compliance
    Evaluator -.->|"confidence adjustment<br/>state demotion"| END

    classDef agent fill:#2b6cb0,color:#fff,stroke:#1a4480,stroke-width:2px
    class Router,Compliance,Evaluator agent
```

Evaluator internals:

```mermaid
flowchart TB
    In[ComplianceResult +<br/>retrieved chunks] --> L1[Layer 1<br/>Deterministic Grounding<br/>SequenceMatcher vs source chunks<br/>threshold 0.80]
    In --> L2[Layer 2<br/>LLM Critic<br/>completeness / consistency /<br/>calibration / groundedness]
    L1 --> Merge[Merge<br/>hallucination flags<br/>into LLM assessment]
    L2 --> Merge
    Merge --> L3{Layer 3<br/>Decision}
    L3 -->|FAIL + retries_left| Retry[Retry Compliance Agent<br/>with critique as feedback]
    L3 -->|PASS_WITH_FLAGS| Adjust[Adjust confidence<br/>Demote state if conf < 0.5]
    L3 -->|PASS| Out[Final ComplianceResult]
    Adjust --> Out
```

---

## 4. Data flow — PDF elements to chunks to vectors

```mermaid
flowchart LR
    PDF[(PDF)] --> Unstructured[unstructured hi_res]
    Unstructured --> Elements["ParsedElement[]<br/>Title / Narrative /<br/>Table / ListItem"]
    Elements --> Chunker[Section-aware chunker]
    Chunker -->|"text chunks<br/>capped at 400 words"| TextCh[Text Chunk<br/>doc = text<br/>embed = text]
    Chunker -->|"Table elements<br/>atomic"| TableCh[Table Chunk]
    TableCh --> Describer[LLM table describer]
    Describer -->|"2-4 sentence prose"| TableCh2[Table Chunk<br/>doc = HTML<br/>embed = prose]
    TextCh --> Embedder[sentence-transformers<br/>all-MiniLM-L6-v2<br/>normalised]
    TableCh2 --> Embedder
    Embedder --> Chroma[(ChromaDB<br/>contract-xxx collection<br/>cosine space)]
```

Why the split between `document` and `embedding_text` on table chunks:
- The **document** returned to the compliance agent must preserve structure —
  HTML keeps rows and columns intact so the agent can quote a specific cell.
- The **embedding text** drives retrieval — prose aligns with how analysts
  phrase queries, so the vector lives near natural-language queries.

---

## 5. Observability architecture

```mermaid
flowchart LR
    subgraph Runtime
        Stage[Pipeline stage]
    end

    Stage -->|"logger.info(event, trace_id, span_id, ...)"| structlog
    structlog --> Console[stdout<br/>human-readable during dev]
    structlog --> JSONL[(logs/app.jsonl<br/>production sink)]

    Stage -->|"record_analysis /<br/>record_question_result /<br/>record_agent_span"| SQLite[(metrics.db)]

    SQLite --> Dashboard[Streamlit<br/>KPI Dashboard]
    SQLite --> Queries[Ad-hoc SQL<br/>for debugging]
    JSONL --> Grep["grep + jq<br/>'grep trace_id | jq'"]
    JSONL --> SIEM[Any SIEM / log pipeline<br/>future: OTLP export]
```

Every log event and every metric row carries the same `trace_id`, so a single
request is reconstructable across both sinks.

---

## 6. Deployment topology (production extension)

```mermaid
flowchart TB
    LB[Load Balancer] --> API1[FastAPI replica 1]
    LB --> API2[FastAPI replica 2]
    LB --> APIn[FastAPI replica N]

    API1 --> Jobs[(Job Store<br/>Redis or Postgres)]
    API2 --> Jobs
    APIn --> Jobs

    API1 --> Vec[(Vector Store<br/>Qdrant or pgvector)]
    API2 --> Vec
    APIn --> Vec

    API1 --> Metrics[(Metrics Store<br/>Postgres)]
    API2 --> Metrics
    APIn --> Metrics

    API1 -.log.-> OTLP[OpenTelemetry Collector]
    API2 -.log.-> OTLP
    APIn -.log.-> OTLP
    OTLP --> Obs[Grafana / Datadog /<br/>Honeycomb]

    MCPGW[MCP Gateway] --> LB
    ExternalBots[ChatGPT / Claude /<br/>Copilot Connectors] --> LB
```

The in-process components migrated in this topology:
- `_jobs` dict → shared job store (Redis / Postgres)
- ChromaDB → Qdrant / pgvector (multi-replica safe)
- SQLite metrics → Postgres (aggregates across replicas)
- File-based JSONL → OTLP → unified observability stack

No application code changes beyond the I/O shims — the agent graph and
compliance logic are unchanged.
