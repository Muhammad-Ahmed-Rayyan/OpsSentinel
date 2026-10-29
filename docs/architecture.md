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
        KB[("ChromaDB: past postmortems")]
        RB[("ChromaDB: runbooks")]
        INF["Infrastructure: services and hosts"]
    end

    subgraph Agents["LangGraph multi-agent workflow"]
        ING["Alert Ingestion Agent: normalize, filter noise, drop duplicates"]
        COR["Correlation Agent"]
        HYP["Root-Cause Hypothesis Agent"]
        NOT["Notification nodes"]
        GATE["Human Approval Gate"]
        EXE["Runbook Execution Agent"]
        VER["Verification Agent"]
        REV["Post-incident Review Gate"]
        REP["Reporting Agent"]
    end

    LLM["LLM: Groq or OpenRouter"]
    HUMAN(["On-call engineer"])
    OUT["Outbox folder and optional Slack webhook"]
    REPORTS["Postmortem reports"]
    DROP(["Suppressed: no incident opened"])

    MON --> ING
    ING -- "new incident" --> COR --> HYP
    ING -- "noise or duplicate" --> DROP
    TEL --> COR
    HYP <--> KB
    HYP <--> RB
    HYP <--> LLM
    HYP -- "high risk" --> NOT
    NOT -- "approval request" --> GATE
    HYP -- "low risk" --> EXE
    GATE <--> HUMAN
    GATE -- "approved option" --> EXE
    GATE -- "rejected" --> REP
    EXE -- "remediation actions" --> INF
    EXE -- "failed action" --> REP
    EXE --> VER
    INF -- "metrics" --> VER
    VER -- "recovered" --> REV
    VER -- "not recovered" --> REP
    REV <--> HUMAN
    REV --> REP
    NOT --> OUT
    REP --> REPORTS
    REP -- "confirmed or corrected fixes only" --> KB
```

Notification nodes also fire before the review gate and, when an incident ends escalated or failed, just before the report. Ingestion, correlation and hypothesis failures route to the Reporting Agent too, so every incident that opens ends with a report.

## 3. Agent communication flow

Agents never talk to each other directly. Each reads a shared, typed state and returns a partial update; LangGraph decides which node runs next.

```mermaid
sequenceDiagram
    autonumber
    participant G as LangGraph shared state
    participant I as Ingestion
    participant C as Correlation
    participant H as Hypothesis
    participant N as Notifier
    participant A as Approval Gate
    actor U as Human
    participant E as Execution
    participant V as Verification
    participant R as Review Gate
    participant P as Reporting

    G->>I: raw_alert
    I-->>G: alert, status ingested or suppressed
    G->>C: alert
    C-->>G: context with logs, metrics, deployments, signals
    G->>H: alert, context
    H-->>G: hypotheses, proposed_action, alternatives, risk_tier
    alt high risk
        G->>N: approval request
        N->>U: message sent once
        G->>A: proposed_action and alternatives
        A->>U: approval request, graph pauses at interrupt
        U-->>A: approve an option or reject, graph resumes
        A-->>G: approval and the chosen action
    end
    alt low risk or approved
        G->>E: proposed_action, approval
        E-->>G: execution_result
        G->>V: execution_result
        V-->>G: verification, status resolved or escalated
    end
    alt resolved
        G->>N: review request
        N->>U: message sent once
        G->>R: diagnosis and proof of the fix
        R->>U: confirm, correct or skip, graph pauses
        U-->>R: review, graph resumes
        R-->>G: review
    end
    alt escalated or failed
        G->>N: escalation message for the on-call engineer
    end
    G->>P: full state
    P-->>G: report, report_path, learned only if reviewed
```

## 4. Data flow

```mermaid
flowchart LR
    A1["alerts JSON"] -->|"raw alert"| P1["1 Ingest and filter"]
    P1 -->|"normalized alert"| P2["2 Correlate"]
    P1 -.->|"noise or duplicate"| X(["Suppressed"])
    T1["logs JSON"] -->|"WARN and ERROR logs"| P2
    T2["metrics JSON"] -->|"metric series"| P2
    T3["deployments JSON"] -->|"recent deployments"| P2
    P2 -->|"context and signals"| P3["3 Hypothesize"]
    D1[("ChromaDB postmortems")] -->|"similar past incidents"| P3
    D2[("ChromaDB runbooks")] -->|"procedures and cautions"| P3
    P3 <-->|"prompt and JSON answer"| L["LLM API"]
    P3 -->|"high risk: action and alternatives"| P4["4 Approve"]
    P3 -->|"low risk: action"| P5["5 Execute"]
    P4 <-->|"request and decision"| H(["Human"])
    P4 -->|"approved option"| P5
    P5 -->|"remediation call"| S[("Simulated infrastructure")]
    S -->|"current metrics"| P6["6 Verify"]
    P5 -->|"execution result"| P6
    P6 -->|"verified fix"| P7["7 Review"]
    P7 <-->|"diagnosis and decision"| H
    P7 -->|"review"| P8["8 Report"]
    P6 -->|"unverified"| P8
    P8 --> R[/"reports folder"/]
    P8 -->|"confirmed or corrected postmortem"| D1
    N[/"notifications folder and Slack webhook"/]
    P4 -.->|"approval request"| N
    P7 -.->|"review request"| N
    P8 -.->|"escalation, sent just before the report"| N
```

Every step also appends a timestamped entry to the audit log in the shared state; the Reporting Agent turns that log into the report timeline.

## 5. State diagram

The `status` field of the incident state. Two pauses are interrupts in the graph, not status values.

```mermaid
stateDiagram-v2
    [*] --> Ingested: alert normalized
    [*] --> Suppressed: noise or duplicate of an open incident
    [*] --> Failed: unsupported or malformed alert
    Ingested --> Correlated: context built
    Ingested --> Failed: all data sources down
    Correlated --> Hypothesized: LLM answer valid
    Correlated --> Escalated: LLM failed twice or API error
    Correlated --> Failed: missing alert or context
    Hypothesized --> ApprovalPending: high risk action
    Hypothesized --> Verifying: low risk action executed
    Hypothesized --> Escalated: low risk action failed
    ApprovalPending --> Executing: approved option
    ApprovalPending --> Rejected: rejected or unclear answer
    Executing --> Verifying: action executed
    Executing --> Escalated: action failed
    Verifying --> Resolved: metric recovered
    Verifying --> Escalated: not recovered or cannot verify
    Resolved --> ReviewPending: fix verified
    ReviewPending --> Closed: confirmed or corrected, outcome learned
    ReviewPending --> Closed: skipped or rejected, nothing learned
    Suppressed --> [*]: no incident and no report
    Rejected --> Closed: report written
    Escalated --> Closed: engineer notified and report written
    Failed --> Closed: engineer notified and report written
    Closed --> [*]

    note right of ApprovalPending : graph is paused by interrupt and status still reads hypothesized
    note right of ReviewPending : graph is paused by interrupt and status still reads resolved
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
        DD["Alert deduplicator: open incidents held in memory"]
    end
    subgraph AGT["Agents and policy"]
        AG["Ingestion, Correlation, Hypothesis, Approval Gate, Execution, Verification, Review Gate, Reporting"]
        NT["Notification nodes in front of each gate and the report"]
        POL["Action catalog: allowed actions, parameters, fixed risk tiers"]
    end
    subgraph TOOLS["Tool layer"]
        T1["telemetry: logs, metrics, deployments"]
        T2["monitoring: read metrics"]
        T3["remediation: execute actions"]
        T4["knowledge_base: postmortems"]
        T6["runbooks: procedures"]
        T5["llm: provider switch from env settings"]
        T7["notifier: outbox and webhook"]
    end
    subgraph DATA["Data stores"]
        D1[("JSON files: alerts, telemetry, postmortems, runbooks")]
        D2[("ChromaDB in chroma_db folder")]
        D3[("Simulated infrastructure state")]
        D4["reports folder: Markdown postmortems"]
        D5["notifications folder"]
    end
    subgraph EXT["External services"]
        X1["Groq API"]
        X2["OpenRouter API"]
        X3["Local ONNX embedding model"]
        X4["Slack-compatible webhook, optional"]
    end

    CLI --> LG
    LG --- CP
    LG --- DD
    LG --> AG
    AG <--> ST
    AG --> POL
    LG --> NT
    AG --> T1 & T2 & T3 & T4 & T6 & T5
    NT --> T7
    T1 --> D1
    T2 --> D3
    T3 --> D3
    T4 --> D2
    T6 --> D2
    T4 --> X3
    T6 --> X3
    T5 --> X1
    T5 --> X2
    T7 --> D5
    T7 --> X4
    AG --> D4
    D1 -. "seed" .-> D2
```

## 7. Human-in-the-loop workflow

```mermaid
flowchart TD
    A["Hypothesis Agent proposes a best action and up to two alternatives from the catalog"] --> B["Risk tier of every option is looked up in the catalog and never taken from the LLM"]
    B --> C{"Risk tier of the best action"}
    C -- "low" --> D["Execute automatically and record auto-approved in the audit log"]
    C -- "high" --> E["Notify the engineer once, then the graph pauses with an interrupt"]
    E --> F["Human sees alert, likely cause, confidence, options with risk tiers and the rationale"]
    F --> G{"Human decision"}
    G -- "approve option 1" --> H["Execute the proposed action"]
    G -- "approve option 2 or 3" --> H2["Execute the chosen alternative and record what it replaced"]
    G -- "reject or unclear answer" --> I["No change to infrastructure"]
    H --> J["Verification Agent checks the metric"]
    H2 --> J
    D --> J
    J --> K{"Recovered?"}
    K -- "yes" --> L["Notify the engineer, then pause for post-incident review"]
    K -- "no or cannot verify" --> M["Escalated: the engineer is notified and takes over"]
    L --> R{"Review decision"}
    R -- "confirmed or corrected" --> S["Postmortem written and the outcome is learned"]
    R -- "skipped, wrong or unclear" --> T["Postmortem written and nothing is learned"]
    I --> N["Rejected: postmortem written and nothing learned"]
    M --> O["Postmortem written and nothing learned"]
    S --> P["Similar future incidents retrieve this outcome as a hint"]
    H -.-> Q["Execution Agent also refuses high risk actions that lack a recorded approval"]
```