# OpsSentinel Architecture

Seven views of the system. The diagrams match the code in `src/opssentinel/`.

## 1. Existing process workflow (human on-call)

Highlighted steps are the repetitive work the system takes over.

```mermaid
flowchart TD
    A["Monitoring tool fires an alert"] --> B["Page on-call engineer"]
    B --> C["Check dashboards and logs across several tools"]
    C --> D["Correlate with recent deployments and changes"]
    D --> E["Search past incidents and runbooks for similar cases"]
    E --> F["Form a root-cause hypothesis"]
    F --> G["Choose a remediation action"]
    G --> H{"Risky action?"}
    H -- "Yes" --> I["Ask a teammate or manager for sign-off"]
    H -- "No" --> J["Run the fix manually"]
    I --> J
    J --> K["Re-check metrics to see if it worked"]
    K --> L{"Recovered?"}
    L -- "No" --> C
    L -- "Yes" --> M["Write the postmortem by hand"]
    M --> N["Lessons stay in documents and in people's memory"]

    classDef repetitive fill:#fdebd0,stroke:#d98a1f,color:#000
    class C,D,E,G,J,K,M repetitive
```

## 2. Proposed multi-agent architecture

```mermaid
flowchart LR
    subgraph Sources["Monitoring and data sources"]
        MON["Alerts: Prometheus and Datadog formats"]
        TEL["Telemetry: logs, metrics, deployment history"]
        KB[("ChromaDB postmortem knowledge base")]
        INF["Infrastructure: services and hosts"]
    end

    subgraph Agents["LangGraph multi-agent workflow"]
        ING["Alert Ingestion Agent"]
        COR["Correlation Agent"]
        HYP["Root-Cause Hypothesis Agent"]
        GATE["Human Approval Gate"]
        EXE["Runbook Execution Agent"]
        VER["Verification Agent"]
        REP["Reporting Agent"]
    end

    LLM["LLM: Groq or OpenRouter"]
    HUMAN(["On-call engineer"])
    REPORTS["Postmortem reports"]

    MON --> ING --> COR --> HYP
    TEL --> COR
    HYP <--> KB
    HYP <--> LLM
    HYP -- "high risk" --> GATE
    HYP -- "low risk" --> EXE
    GATE <--> HUMAN
    GATE -- "approved" --> EXE
    GATE -- "rejected" --> REP
    EXE -- "remediation actions" --> INF
    EXE -- "failed action" --> REP
    EXE --> VER
    INF -- "metrics" --> VER
    VER --> REP
    REP --> REPORTS
    REP -- "verified fixes only" --> KB
```

Ingestion, correlation and hypothesis failures also route to the Reporting Agent, so every incident ends with a report.

## 3. Agent communication flow

Agents never talk to each other directly. Each reads a shared, typed state and returns a partial update; LangGraph decides which node runs next.

```mermaid
sequenceDiagram
    autonumber
    participant G as LangGraph shared state
    participant I as Ingestion
    participant C as Correlation
    participant H as Hypothesis
    participant A as Approval Gate
    actor U as Human
    participant E as Execution
    participant V as Verification
    participant R as Reporting

    G->>I: raw_alert
    I-->>G: alert, status ingested
    G->>C: alert
    C-->>G: context with logs, metrics, deployments, signals
    G->>H: alert, context
    H-->>G: hypotheses, proposed_action, risk_tier
    alt high risk
        G->>A: proposed_action
        A->>U: approval request, graph pauses at interrupt
        U-->>A: approved or rejected, graph resumes
        A-->>G: approval
    end
    alt low risk or approved
        G->>E: proposed_action, approval
        E-->>G: execution_result
        G->>V: execution_result
        V-->>G: verification, status resolved or escalated
    end
    G->>R: full state
    R-->>G: report, report_path
```

## 4. Data flow

```mermaid
flowchart LR
    A1["alerts JSON"] -->|"raw alert"| P1["1 Ingest"]
    P1 -->|"normalized alert"| P2["2 Correlate"]
    T1["logs JSON"] -->|"WARN and ERROR logs"| P2
    T2["metrics JSON"] -->|"metric series"| P2
    T3["deployments JSON"] -->|"recent deployments"| P2
    P2 -->|"context and signals"| P3["3 Hypothesize"]
    D1[("ChromaDB postmortems")] -->|"similar past incidents"| P3
    P3 <-->|"prompt and JSON answer"| L["LLM API"]
    P3 -->|"high risk: proposed action"| P4["4 Approve"]
    P3 -->|"low risk: proposed action"| P5["5 Execute"]
    P4 <-->|"request and decision"| H(["Human"])
    P4 -->|"approval"| P5
    P5 -->|"remediation call"| S[("Simulated infrastructure")]
    S -->|"current metrics"| P6["6 Verify"]
    P5 -->|"execution result"| P6
    P6 -->|"verification"| P7["7 Report"]
    P7 --> R[/"reports folder"/]
    P7 -->|"verified postmortem"| D1
```

Every step also appends a timestamped entry to the audit log in the shared state; the Reporting Agent turns that log into the report timeline.

## 5. State diagram

The `status` field of the incident state. The approval pause is an interrupt in the graph, not a status value.

```mermaid
stateDiagram-v2
    [*] --> Ingested: alert normalized
    [*] --> Failed: unsupported or malformed alert
    Ingested --> Correlated: context built
    Ingested --> Failed: all data sources down
    Correlated --> Hypothesized: LLM answer valid
    Correlated --> Escalated: LLM failed twice or API error
    Correlated --> Failed: missing alert or context
    Hypothesized --> ApprovalPending: high risk action
    Hypothesized --> Verifying: low risk action executed
    Hypothesized --> Escalated: low risk action failed
    ApprovalPending --> Executing: approved
    ApprovalPending --> Rejected: rejected or unclear answer
    Executing --> Verifying: action executed
    Executing --> Escalated: action failed
    Verifying --> Resolved: metric recovered
    Verifying --> Escalated: not recovered or cannot verify
    Resolved --> [*]: report written and outcome learned
    Rejected --> [*]: report written
    Escalated --> [*]: report written
    Failed --> [*]: report written

    note right of ApprovalPending : graph is paused by interrupt and status still reads hypothesized
```

## 6. System architecture

```mermaid
flowchart TB
    subgraph UI["Interface"]
        CLI["CLI runner: main.py"]
    end
    subgraph ORCH["Orchestration"]
        LG["LangGraph StateGraph with conditional routing"]
        CP["MemorySaver checkpointer for interrupt and resume"]
        ST["Shared IncidentState and audit log"]
    end
    subgraph AGT["Agents and policy"]
        AG["Ingestion, Correlation, Hypothesis, Approval Gate, Execution, Verification, Reporting"]
        POL["Action catalog: allowed actions, parameters, fixed risk tiers"]
    end
    subgraph TOOLS["Tool layer"]
        T1["telemetry: logs, metrics, deployments"]
        T2["monitoring: read metrics"]
        T3["remediation: execute actions"]
        T4["knowledge_base: search and add postmortems"]
        T5["llm: provider switch from env settings"]
    end
    subgraph DATA["Data stores"]
        D1[("JSON files: alerts, telemetry, postmortems")]
        D2[("ChromaDB in chroma_db folder")]
        D3[("Simulated infrastructure state")]
        D4["reports folder: Markdown postmortems"]
    end
    subgraph EXT["External services"]
        X1["Groq API"]
        X2["OpenRouter API"]
        X3["Local ONNX embedding model"]
    end

    CLI --> LG
    LG --- CP
    LG --> AG
    AG <--> ST
    AG --> POL
    AG --> T1 & T2 & T3 & T4 & T5
    T1 --> D1
    T2 --> D3
    T3 --> D3
    T4 --> D2
    T4 --> X3
    T5 --> X1
    T5 --> X2
    AG --> D4
    D1 -. "seed" .-> D2
```

## 7. Human-in-the-loop workflow

```mermaid
flowchart TD
    A["Hypothesis Agent proposes an action from the catalog"] --> B["Risk tier is looked up in the catalog and never taken from the LLM"]
    B --> C{"Risk tier"}
    C -- "low" --> D["Execute automatically and record auto-approved in the audit log"]
    C -- "high" --> E["Graph pauses with interrupt"]
    E --> F["Human sees alert, likely cause, confidence, action, parameters and rationale"]
    F --> G{"Human decision"}
    G -- "approved" --> H["Execute and record reviewer and comment"]
    G -- "rejected or unclear answer" --> I["No change to infrastructure"]
    H --> J["Verification Agent checks the metric"]
    D --> J
    J --> K{"Recovered?"}
    K -- "yes" --> L["Resolved: postmortem written and outcome learned"]
    K -- "no or cannot verify" --> M["Escalated: a human takes over"]
    I --> N["Rejected: postmortem written and nothing learned"]
    M --> O["Postmortem written and nothing learned"]
    L --> P["Similar future incidents retrieve this outcome as a hint"]
    H -.-> Q["Execution Agent also refuses high risk actions that lack a recorded approval"]
```