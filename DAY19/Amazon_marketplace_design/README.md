# Amazon Marketplace MCP Architecture: Design Case Study

A comprehensive technical guide to designing an agentic architecture for Amazon sellers using the Model Context Protocol (MCP). This repository documents architecture decisions, trust boundaries, and implementation patterns for multi-server MCP orchestration.

**📅 June 2026 | Protocol Landscape v1.0**

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Design Decision Framework](#design-decision-framework)
4. [Trust & Security Model](#trust--security-model)
5. [Data Flow Architecture](#data-flow-architecture)
6. [Human-in-the-Loop Pattern](#human-in-the-loop-pattern)
7. [Authorization Model](#authorization-model)
8. [Implementation Roadmap](#implementation-roadmap)
9. [Design Axes Resolution](#design-axes-resolution)
10. [Key Considerations](#key-considerations)

---

## Executive Summary

### The Challenge

Amazon sellers operating at scale need unified AI-driven operations across:
- **Pricing & inventory management**
- **FBA operations & restocks**
- **Advertising campaigns**
- **Order & return handling**
- **Buyer communication**
- **Profitability reconciliation**

These functions span disparate Amazon systems, creating a complex integration puzzle.

### The Solution

A **multi-server MCP-centric topology** with two trust boundaries:
- **Amazon-hosted**: Ads MCP Server (official, narrow scope)
- **Seller-controlled**: SP-API MCP Server (self-hosted or compliant vendor)

One orchestrating agent manages both, with human approval gates for financial decisions.

---

## System Architecture

### Reference Topology

```mermaid
graph TB
    Agent["🤖 Orchestrating Agent<br/>(One Seller, One Brain)"]
    
    subgraph Seller["🟢 Seller-Controlled Boundary"]
        SP_API["SP-API MCP Server<br/>Orders • Inventory • Listings"]
        Cost["Cost/COGS Data<br/>Private Margin Inputs"]
    end
    
    subgraph Amazon["🟠 Amazon-Hosted Boundary"]
        Ads["Amazon Ads MCP Server<br/>Campaigns • Reporting • AMC"]
        AdsAPI["Ads API + Amazon Marketing Cloud"]
    end
    
    Agent -->|Auth with credentials| Ads
    Agent -->|Self-host or compliant vendor| SP_API
    Ads --> AdsAPI
    SP_API --> Cost
    
    style Agent fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style Seller fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    style Amazon fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style Ads fill:#fff9c4,stroke:#fbc02d
    style SP_API fill:#c8e6c9,stroke:#388e3c
    style Cost fill:#c8e6c9,stroke:#388e3c
```

**Key Insight**: Two trust boundaries, not one. The division reflects data ownership and regulatory constraints, not just technical preference.

---

## Design Decision Framework

### The Decision Tree

```mermaid
graph TD
    Start["🎯 Build Amazon AI Agent<br/>for End-to-End Operations"]
    
    Start --> Q1["Q1: Where does your data live?"]
    
    Q1 -->|Ads only| NoSP["❌ Can't use Ads server alone<br/>Missing orders, inventory, financials"]
    Q1 -->|Orders + Inventory + Ads| Multi["✅ Multi-server design required"]
    
    NoSP --> End1["Reconsider scope"]
    
    Multi --> Q2["Q2: Who hosts the SP-API server?"]
    Q2 -->|Self-host| SelfHost["✅ Full data control<br/>Higher operational burden"]
    Q2 -->|Third-party vendor| Vendor["✅ Easier ops<br/>⚠️ PII flows through vendor"]
    
    SelfHost --> Q3["Q3: What can the agent<br/>write to autonomously?"]
    Vendor --> Q3
    
    Q3 -->|Reads only| ReadOnly["🟢 Lowest risk<br/>Prove out functionality first"]
    Q3 -->|Reads + reversible writes| Mixed["🟡 Medium risk<br/>Draft messages, draft campaigns"]
    Q3 -->|Reads + all writes| HighRisk["🔴 High risk<br/>Requires strong guardrails"]
    
    ReadOnly --> Q4["Q4: How do you gate spending?"]
    Mixed --> Q4
    HighRisk --> Q4
    
    Q4 -->|Human approval for all spends| SafeSpend["✅ Compliant with AI Agent Policy<br/>Protects margin and brand"]
    Q4 -->|Agent decides spending| UnsafeSpend["❌ Violates March 2026 Policy<br/>Price wars, budget overruns likely"]
    
    SafeSpend --> Final["🎬 Proceed to implementation"]
    UnsafeSpend --> Revise["🔄 Revise strategy"]
    
    style Start fill:#bbdefb,stroke:#1565c0,stroke-width:2px
    style Multi fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
    style SelfHost fill:#c8e6c9,stroke:#2e7d32
    style ReadOnly fill:#c8e6c9,stroke:#2e7d32
    style SafeSpend fill:#c8e6c9,stroke:#2e7d32
    style Final fill:#a5d6a7,stroke:#1b5e20,stroke-width:2px
    style NoSP fill:#ffcdd2,stroke:#c62828
    style UnsafeSpend fill:#ffcdd2,stroke:#c62828
    style Revise fill:#ffe0b2,stroke:#e65100
```

---

## Trust & Security Model

### Trust Boundary Resolution

```mermaid
graph LR
    subgraph TrustModel["🔐 Trust Boundary Matrix"]
        direction LR
        
        subgraph Ads["Amazon-Hosted (Ads)"]
            A1["📊 Campaigns"]
            A2["📈 Reporting"]
            A3["🎯 Amazon Marketing Cloud"]
        end
        
        subgraph SP["Seller-Controlled (SP-API)"]
            S1["📦 Orders + Buyer PII"]
            S2["📊 Inventory"]
            S3["💰 Settlements"]
            S4["📋 Listings"]
        end
        
        subgraph Private["Seller Private"]
            P1["💵 Cost / COGS"]
            P2["📝 Margin Targets"]
        end
    end
    
    Decision["🎯 Decision Rule"]
    Decision -->|Amazon-sensitive data<br/>Fast to stand up| AdsChoice["Use Official<br/>Ads MCP Server"]
    Decision -->|Buyer PII + Financials<br/>High compliance bar| SPChoice["Self-host SP-API or<br/>compliant vendor only"]
    Decision -->|Your secrets<br/>Never to API| PrivChoice["Manage locally<br/>Pass to agent only at read"]
    
    style Ads fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style SP fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    style Private fill:#f3e5f5,stroke:#6a1b9a,stroke-width:2px
    style AdsChoice fill:#fff9c4,stroke:#fbc02d
    style SPChoice fill:#c8e6c9,stroke:#388e3c
    style PrivChoice fill:#e1bee7,stroke:#6a1b9a
```

### Data Protection Strategy

| Data Type | Location | Authority | Risk Level |
|-----------|----------|-----------|-----------|
| **Campaigns, Spend, Reporting** | Amazon-hosted Ads MCP | Amazon | Low (Amazon-controlled) |
| **Orders, Buyer Names/Addresses** | Self-hosted SP-API or compliant vendor | Seller | **Critical** (PII) |
| **Inventory, Settlements** | Self-hosted SP-API or compliant vendor | Seller | High (Financial) |
| **COGS, Cost Data** | Seller private (never API) | Seller | Critical (Competitive) |

---

## Data Flow Architecture

### Read-Only Path (Autonomous)

```mermaid
graph LR
    Agent["🤖 Agent"]
    
    Agent -->|1. Request reports| AdsServer["Ads MCP Server"]
    Agent -->|1. Query orders| SPServer["SP-API MCP Server"]
    Agent -->|1. Fetch COGS| Internal["Internal Cost System"]
    
    AdsServer -->|2. Return campaigns,<br/>spend, ACOS| Agent
    SPServer -->|2. Return orders,<br/>inventory, margins| Agent
    Internal -->|2. Return cost data| Agent
    
    Agent -->|3. Analyze &<br/>Reconcile| Analytics["Profit-Per-SKU<br/>View"]
    
    Analytics -->|4. Output reports| Output["📊 Dashboard<br/>No human gate needed"]
    
    style Agent fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style AdsServer fill:#fff9c4,stroke:#fbc02d,stroke-width:2px
    style SPServer fill:#c8e6c9,stroke:#388e3c,stroke-width:2px
    style Output fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
```

### Write Path (Gated)

```mermaid
graph TD
    Agent["🤖 Agent Decides<br/>Action Needed"]
    
    subgraph WriteTypes["Categorized by Risk"]
        DraftMsg["📝 Draft Message<br/>Reversible"]
        DraftCamp["🎬 Draft Campaign<br/>Reversible"]
        PriceChange["💰 Price Change<br/>HIGH DANGER"]
        NewCampaign["🚀 New Campaign<br/>Spends Money"]
        BudgetIncrease["💵 Budget Increase<br/>Spends Money"]
    end
    
    Agent --> DraftMsg
    Agent --> DraftCamp
    Agent --> PriceChange
    Agent --> NewCampaign
    Agent --> BudgetIncrease
    
    DraftMsg -->|Log & Execute<br/>Autonomous| Log1["📋 Audit Trail"]
    DraftCamp -->|Log & Execute<br/>Autonomous| Log1
    
    PriceChange -->|Constrained Tool:<br/>Floor & Ceiling Only| Constrain["🔒 Guard Rails<br/>Prevent margin wars"]
    Constrain -->|Log & Execute<br/>Autonomous| Log1
    
    NewCampaign -->|Create Proposal| Proposal["📋 Proposal to Human"]
    BudgetIncrease -->|Create Proposal| Proposal
    
    Proposal -->|Human Approval| Human["✅ Review & Approve"]
    Proposal -->|Human Reject| Reject["❌ Rejected"]
    
    Human -->|Approved| Execute["Execute Write"]
    Reject -->|Discard| Log2["Log rejection"]
    
    Execute --> Log3["📊 Log execution<br/>+ timestamp"]
    Log3 --> MCP["Write via MCP<br/>to AWS/SP-API"]
    
    Log1 --> Trail["🔍 Complete Audit Trail"]
    Log2 --> Trail
    
    style Agent fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style DraftMsg fill:#c8e6c9,stroke:#2e7d32
    style DraftCamp fill:#c8e6c9,stroke:#2e7d32
    style PriceChange fill:#ffe0b2,stroke:#e65100,stroke-width:2px
    style Constrain fill:#fff9c4,stroke:#fbc02d
    style Proposal fill:#ffccbc,stroke:#d84315
    style Human fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
    style Execute fill:#a5d6a7,stroke:#1b5e20,stroke-width:2px
    style Trail fill:#a5d6a7,stroke:#1b5e20,stroke-width:2px
```

---

## Human-in-the-Loop Pattern

### Decision Gate by Operation Type

```mermaid
graph TD
    Op["📋 Operation<br/>Initiated"]
    
    Op --> Classify{"Is this a<br/>write?"}
    
    Classify -->|No| Read["🟢 READ<br/>Analytics, Reports,<br/>Queries"]
    Classify -->|Yes| IsSpend{"Does it touch<br/>money?"}
    
    Read -->|Autonomous| ReadEx["Execute immediately<br/>with logging"]
    
    IsSpend -->|No| Reversible{"Is it<br/>reversible?"}
    IsSpend -->|Yes| Spend["🔴 SPENDING DECISION<br/>Budget, campaign, price change"]
    
    Reversible -->|Yes| RevEx["🟡 REVERSIBLE WRITE<br/>Draft message, draft campaign"]
    Reversible -->|No| Spend
    
    ReadEx --> Log1["Log execution"]
    RevEx -->|Execute immediately| Log2["Log execution"]
    
    Spend --> SpecialCheck{"Is it the<br/>repricer?"}
    SpecialCheck -->|Yes| Reprice["🔒 REPRICER TOOL<br/>Floor & Ceiling only<br/>Constrained writes"]
    SpecialCheck -->|No| Gate["🚪 HUMAN GATE<br/>Create proposal<br/>Wait for approval"]
    
    Reprice -->|Execute if<br/>within bounds| Log3["Log execution<br/>+ constraints checked"]
    Gate -->|If Approved| Exec["Execute"]
    Gate -->|If Rejected| Reject["Discard"]
    
    Exec --> Log4["Log approval<br/>+ execution"]
    Reject --> Log5["Log rejection"]
    
    Log1 --> Complete["✅ Complete"]
    Log2 --> Complete
    Log3 --> Complete
    Log4 --> Complete
    Log5 --> Complete
    
    style Op fill:#bbdefb,stroke:#1565c0,stroke-width:2px
    style Read fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
    style Reversible fill:#fff9c4,stroke:#fbc02d,stroke-width:2px
    style Spend fill:#ffccbc,stroke:#d84315,stroke-width:2px
    style Gate fill:#ffccbc,stroke:#d84315,stroke-width:2px
    style Reprice fill:#ffe0b2,stroke:#e65100,stroke-width:2px
    style Exec fill:#a5d6a7,stroke:#1b5e20,stroke-width:2px
    style Complete fill:#a5d6a7,stroke:#1b5e20,stroke-width:2px
```

### Risk Levels by Operation

```
┌─────────────────────────────────────────────────────────────┐
│                    HUMAN-IN-LOOP FRAMEWORK                   │
├─────────────────────┬──────────────┬──────────┬─────────────┤
│ Operation Type      │ Risk Level   │ Autonomy │ Gating      │
├─────────────────────┼──────────────┼──────────┼─────────────┤
│ Read analytics      │ 🟢 NONE      │ Full     │ None        │
│ Report generation   │ 🟢 NONE      │ Full     │ None        │
│ Draft message       │ 🟡 REVERSIBLE│ Full     │ Audit log   │
│ Draft campaign      │ 🟡 REVERSIBLE│ Full     │ Audit log   │
│ Reprice            │ 🔴 CRITICAL  │ Partial  │ Constraints │
│ New campaign       │ 🔴 SPENDING   │ Propose  │ Human vote  │
│ Budget increase    │ 🔴 SPENDING   │ Propose  │ Human vote  │
│ Price change (free)│ 🔴 SPENDING   │ Propose  │ Human vote  │
│ Refund (Buy Box)   │ 🔴 BUY BOX    │ Propose  │ Human vote  │
└─────────────────────┴──────────────┴──────────┴─────────────┘
```

---

## Authorization Model

### Least-Privilege SP-API Roles

```mermaid
graph LR
    Agent["🤖 Agent"]
    Manager["Manager Credentials<br/>(for each client)"]
    
    R1["sellingpartner:orders:read"]
    R2["sellingpartner:inventory:read"]
    R3["sellingpartner:listings:write"]
    R4["sellingpartner:reports:read"]
    R5["sellingpartner:returns:read"]
    
    Orders["📦 Orders<br/>(Read Only)"]
    Inventory["📊 Inventory<br/>(Read Only)"]
    Listings["📋 Listings<br/>(Limited Write)"]
    Reports["📈 Reports<br/>(Read Only)"]
    Returns["↩️ Returns<br/>(Read Only)"]
    
    RDT1{"Needs<br/>Buyer PII?"}
    RDT2{"Needs<br/>Buyer PII?"}
    
    RDT_Token["🔐 Restricted Data Token<br/>(Specific tool only)"]
    StandardToken["Standard Token"]
    
    FinalAuth["✅ Authorized Tool Calls<br/>(e.g., Generate Shipping Label)"]
    
    Agent -->|Assume role via<br/>STS token| Manager
    
    Manager --> R1
    Manager --> R2
    Manager --> R3
    Manager --> R4
    Manager --> R5
    
    R1 --> Orders
    R2 --> Inventory
    R3 --> Listings
    R4 --> Reports
    R5 --> Returns
    
    Orders --> RDT1
    Listings --> RDT2
    
    RDT1 -->|Yes| RDT_Token
    RDT1 -->|No| StandardToken
    
    RDT2 -->|Yes for Shipping| RDT_Token
    RDT2 -->|No| StandardToken
    
    RDT_Token --> FinalAuth
    StandardToken --> FinalAuth
    
    style Agent fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style Manager fill:#fff9c4,stroke:#fbc02d,stroke-width:2px
    style R1 fill:#e8f5e9,stroke:#388e3c
    style R2 fill:#e8f5e9,stroke:#388e3c
    style R3 fill:#e8f5e9,stroke:#388e3c
    style R4 fill:#e8f5e9,stroke:#388e3c
    style R5 fill:#e8f5e9,stroke:#388e3c
    style RDT_Token fill:#ffccbc,stroke:#d84315,stroke-width:2px
    style StandardToken fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
    style FinalAuth fill:#a5d6a7,stroke:#1b5e20,stroke-width:2px
```

### Per-Client Isolation (Agency Model)

```mermaid
graph TB
    App["🏢 Single Approved<br/>Application"]
    
    App --> Manager["Manager Account<br/>(Application-level)"]
    
    Manager --> Client1["Client A Account"]
    Manager --> Client2["Client B Account"]
    Manager --> Client3["Client C Account"]
    
    Client1 --> Creds1["🔑 Client A<br/>Credentials<br/>(Isolated)"]
    Client2 --> Creds2["🔑 Client B<br/>Credentials<br/>(Isolated)"]
    Client3 --> Creds3["🔑 Client C<br/>Credentials<br/>(Isolated)"]
    
    Creds1 --> Agent1["Agent A<br/>(Sandboxed)"]
    Creds2 --> Agent2["Agent B<br/>(Sandboxed)"]
    Creds3 --> Agent3["Agent C<br/>(Sandboxed)"]
    
    Agent1 -->|Can only access<br/>Client A data| Data1["📦 A's Orders<br/>📊 A's Inventory"]
    Agent2 -->|Can only access<br/>Client B data| Data2["📦 B's Orders<br/>📊 B's Inventory"]
    Agent3 -->|Can only access<br/>Client C data| Data3["📦 C's Orders<br/>📊 C's Inventory"]
    
    Breach["❌ If one credential<br/>is compromised..."]
    Breach -->|Blast radius| Impact["Only that client's<br/>data is at risk,<br/>not entire book"]
    
    style App fill:#bbdefb,stroke:#1565c0,stroke-width:2px
    style Manager fill:#fff9c4,stroke:#fbc02d,stroke-width:2px
    style Creds1 fill:#ffccbc,stroke:#d84315
    style Creds2 fill:#ffccbc,stroke:#d84315
    style Creds3 fill:#ffccbc,stroke:#d84315
    style Agent1 fill:#c8e6c9,stroke:#2e7d32
    style Agent2 fill:#c8e6c9,stroke:#2e7d32
    style Agent3 fill:#c8e6c9,stroke:#2e7d32
    style Impact fill:#a5d6a7,stroke:#1b5e20,stroke-width:2px
```

---

## Transport & Protocol Details

### JSON-RPC 2.0 Pattern

```mermaid
sequenceDiagram
    participant Agent
    participant Server as MCP Server<br/>JSON-RPC/HTTPS
    participant AWS as Amazon API<br/>SP-API / Ads
    
    Agent->>Server: 1. POST /mcp<br/>{"jsonrpc":"2.0",<br/>"method":"list_tools",<br/>"id":1}
    
    Server->>Server: 2. Verify request signature
    
    Server->>AWS: 3. Query available endpoints<br/>(if dynamic)
    AWS-->>Server: 4. Endpoint list
    
    Server-->>Agent: 5. Return tools list<br/>{"result":[...]}
    
    Agent->>Server: 6. POST /mcp<br/>{"jsonrpc":"2.0",<br/>"method":"call_tool",<br/>"params":{...}}
    
    Server->>AWS: 7. Execute with credentials
    AWS-->>Server: 8. Result (data or job ID)
    
    alt Async Report Job
        Server-->>Agent: 9. {"status":"pending",<br/>"job_id":"xyz"}<br/>Set-Cookie: stream_token
        
        Note over Agent,Server: Long-running job
        
        Agent->>Server: 10. GET /mcp/job/xyz<br/>Accept: text/event-stream
        
        Server-->>Agent: 11. Event stream<br/>data: {"progress":50}
        Server-->>Agent: 12. data: {"status":"complete"}
    else Immediate Result
        Server-->>Agent: 9. {"result":data}
    end
```

### Quota Management Pattern

```mermaid
graph LR
    Agent["🤖 Agent"]
    
    Agent -->|Burst pattern:<br/>requests grouped| Server["MCP Server<br/>Quota Manager"]
    
    Server -->|Check quota<br/>balance| Quota["Quota State<br/>Per endpoint"]
    
    Quota -->|Quota available| Execute["✅ Execute request"]
    Quota -->|Quota exhausted| Wait["⏳ Wait + Restore<br/>Exponential backoff"]
    
    Execute -->|Track usage| Update["Update quota"]
    Wait -->|Restore signal| Update
    
    Update -->|Clean answer<br/>to agent| Return["Return result<br/>(not error)"]
    
    style Server fill:#fff9c4,stroke:#fbc02d,stroke-width:2px
    style Quota fill:#e8f5e9,stroke:#388e3c
    style Execute fill:#c8e6c9,stroke:#2e7d32
    style Wait fill:#ffe0b2,stroke:#e65100
    style Return fill:#a5d6a7,stroke:#1b5e20,stroke-width:2px
```

### Event Subscription Pattern (vs. Polling)

```mermaid
graph LR
    subgraph Polling["❌ Polling (Inefficient)"]
        P1["Agent loops<br/>every 5 min"]
        P2["Hammers API<br/>90% empty results"]
        P3["Rate limits<br/>hit quickly"]
        P4["Missed events<br/>between polls"]
        
        P1 --> P2 --> P3 --> P4
    end
    
    subgraph Events["✅ Event Subscriptions (Efficient)"]
        E1["Agent subscribes<br/>to events:<br/>Buy Box lost<br/>Low stock<br/>Ad cost spike"]
        E2["Server wakes agent<br/>only on trigger"]
        E3["No wasted<br/>API calls"]
        E4["Sub-second<br/>latency"]
        
        E1 --> E2 --> E3 --> E4
    end
    
    style Polling fill:#ffcdd2,stroke:#c62828,stroke-width:2px
    style Events fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
```

---

## Implementation Roadmap

### Staged Rollout Plan

```mermaid
gantt
    title Amazon MCP Agent: Phased Implementation (8-12 weeks)
    dateFormat YYYY-MM-DD
    
    section Phase 1: Foundation
    Infra setup & MCP servers          :p1a, 2026-07-01, 7d
    Connect Ads server (read-only)     :p1b, 2026-07-01, 7d
    Connect SP-API server (read-only)  :p1c, 2026-07-05, 7d
    Build basic agent skeleton         :p1d, 2026-07-08, 5d
    
    section Phase 2: Read-Only Proof
    Reporting & reconciliation tools   :p2a, 2026-07-15, 10d
    Profit-per-SKU view                :p2b, 2026-07-18, 8d
    Dashboard & alerting               :p2c, 2026-07-25, 7d
    User testing & iteration           :p2d, 2026-07-28, 5d
    
    section Phase 3: Reversible Writes
    Buyer message drafting             :p3a, 2026-08-05, 7d
    Campaign draft tool                :p3b, 2026-08-08, 7d
    Audit logging framework            :p3c, 2026-08-10, 5d
    QA & confidence building           :p3d, 2026-08-15, 5d
    
    section Phase 4: Gated Spending
    Repricer (constrained tool)        :p4a, 2026-08-20, 10d
    Human approval workflow            :p4b, 2026-08-22, 8d
    Kill switch & emergency stops      :p4c, 2026-08-28, 3d
    Integration testing                :p4d, 2026-08-30, 5d
    
    section Phase 5: Go-Live
    Production deployment              :p5a, 2026-09-10, 3d
    Operator training & runbooks       :p5b, 2026-09-08, 5d
    Live monitoring & response         :p5c, 2026-09-10, 30d
```

### Risk-Gated Milestones

```mermaid
graph TD
    Start["🚀 Day 0: Project Kickoff"]
    
    Start --> M1["✅ Milestone 1: Read-Only Proof<br/>Week 1-2"]
    M1 --> Gate1{"Ready to<br/>enable writes?"}
    Gate1 -->|No| Debug1["🔧 Debug & iterate"]
    Debug1 --> M1
    Gate1 -->|Yes| M2["✅ Milestone 2: Reversible Writes<br/>Week 3-4"]
    
    M2 --> Gate2{"Audit trail<br/>solid?"}
    Gate2 -->|No| Debug2["🔧 Strengthen logging"]
    Debug2 --> M2
    Gate2 -->|Yes| M3["✅ Milestone 3: Gated Spending<br/>Week 5-6"]
    
    M3 --> Gate3{"Constraints &<br/>guardrails tested?"}
    Gate3 -->|No| Debug3["🔧 Harden controls"]
    Debug3 --> M3
    Gate3 -->|Yes| M4["✅ Milestone 4: Production Ready<br/>Week 7-8"]
    
    M4 --> Gate4{"Launch approval<br/>from leadership?"}
    Gate4 -->|No| Review["📋 Review findings"]
    Review --> M4
    Gate4 -->|Yes| GoLive["🎬 Go Live"]
    
    style Start fill:#bbdefb,stroke:#1565c0,stroke-width:2px
    style M1 fill:#c8e6c9,stroke:#2e7d32
    style M2 fill:#c8e6c9,stroke:#2e7d32
    style M3 fill:#c8e6c9,stroke:#2e7d32
    style M4 fill:#c8e6c9,stroke:#2e7d32
    style GoLive fill:#a5d6a7,stroke:#1b5e20,stroke-width:2px
    style Gate1 fill:#fff9c4,stroke:#fbc02d
    style Gate2 fill:#fff9c4,stroke:#fbc02d
    style Gate3 fill:#fff9c4,stroke:#fbc02d
    style Gate4 fill:#fff9c4,stroke:#fbc02d
```

---

## Design Axes Resolution

### Summary Table

| Design Axis | Resolution | Rationale |
|---|---|---|
| **Topology** | MCP-centric, multi-server | One orchestrating agent; agencies fan out with per-client credential isolation |
| **Trust Boundary** | Ads → Amazon-hosted<br/>SP-API → Self-hosted or compliant vendor | Ads data stays in Amazon's boundary; buyer PII must not flow through third party |
| **Authorization** | Least-privilege SP-API roles<br/>RDT only for PII tools<br/>Per-client isolation | Minimize blast radius of credential compromise |
| **Human-in-Loop** | Reads autonomous<br/>Reversible writes auto-with-logging<br/>Money/Buy Box/pricing → human gate | Complies with March 2026 AI Agent Policy; protects margin and brand |
| **Transport & State** | JSON-RPC 2.0 over HTTPS<br/>Async report jobs<br/>Quota-aware throttling<br/>Event subscriptions > polling | Matches Amazon's native patterns; avoid rate limits and wasted API calls |
| **Discovery** | Static, pinned servers<br/>No dynamic registry | Security control; prevents prompt injection and look-alike tool attacks |
| **Profitability** | Join Amazon fee/return/ad data with seller's private COGS | Amazon cannot know your cost; real net margin requires data fusion |

---

## Key Considerations

### Security & Compliance

```mermaid
graph LR
    subgraph Threats["🔴 Known Threats"]
        T1["Prompt injection<br/>via review text"]
        T2["Untrusted input:<br/>buyer messages"]
        T3["Look-alike tools<br/>silently replacing trusted ones"]
        T4["Tool combinations<br/>exfiltrating data"]
        T5["Credential compromise<br/>accessing wrong client"]
    end
    
    subgraph Mitigations["🟢 Mitigations"]
        M1["Taint untrusted input;<br/>never trigger privileged tools"]
        M2["Audit all tool calls<br/>with attribution"]
        M3["Pin known servers;<br/>no dynamic discovery"]
        M4["Least-privilege roles;<br/>RDT only when needed"]
        M5["Per-client credential<br/>isolation"]
    end
    
    T1 --> M1
    T2 --> M1
    T3 --> M3
    T4 --> M4
    T5 --> M5
    
    style Threats fill:#ffcdd2,stroke:#c62828,stroke-width:2px
    style Mitigations fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
```

### Operational Runbooks

**If price war detected:**
- Repricer is constrained; cannot exceed ceiling
- Audit log shows who approved last price change
- Kill switch: disable pricing tool instantly
- Escalate to operator; human reviews competitor pricing

**If Buy Box lost:**
- Event subscription wakes agent
- Agent generates report: inventory, reviews, price vs. competitors
- Proposal sent to human (no autonomous action)
- Human reviews; approves inventory restock or price adjustment

**If rate limit hit:**
- Quota manager detects exhaustion
- Agent backs off exponentially; no error to user
- Server handles fan-out across multiple manager accounts (if agency)
- Operator gets alert; no SLA violation if quota increases available

**If credential compromised:**
- Blast radius limited to one client (agency) or one account (seller)
- Audit log shows what was accessed and when
- Revoke credential; rotate immediately
- Other clients unaffected

### Monitoring & Observability

```mermaid
graph TB
    Agent["🤖 Agent"]
    
    Agent -->|Every tool call| Logger["📋 Audit Logger"]
    
    Logger -->|Log entry:<br/>timestamp,<br/>tool name,<br/>input,<br/>output,<br/>user/approval| Storage["Audit Trail<br/>(Immutable)"]
    
    Logger -->|Metrics:<br/>tool latency,<br/>error rate,<br/>quota usage| Metrics["📊 Prometheus<br/>Metrics"]
    
    Metrics -->|Expose to| Dashboard["Grafana Dashboard<br/>Real-time monitoring"]
    
    Logger -->|High-severity events:<br/>spending approvals,<br/>errors,<br/>quota exhaustion| Alerts["🚨 Alert Manager"]
    
    Alerts -->|Trigger on| Rules["Alert Rules:<br/>SLA violations,<br/>anomalies"]
    
    Rules -->|Escalate to| Team["👥 Operations Team"]
    
    style Agent fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style Storage fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
    style Dashboard fill:#fff9c4,stroke:#fbc02d,stroke-width:2px
    style Alerts fill:#ffccbc,stroke:#d84315,stroke-width:2px
    style Team fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
```

---

## Conclusion: From Design to Operations

This case study resolves the Amazon marketplace integration problem through a **multi-server MCP topology with clear trust boundaries, staged rollout, and human-in-the-loop gates on all financial decisions**.


### Key Takeaways

| Takeaway | Implementation |
|----------|---|
| **Trust boundaries exist for a reason** | Never route buyer PII through third-party MCP servers; self-host or pick a compliant vendor |
| **Human gates scale** | Design for humans to approve proposals, not monitor fine-grained decisions; gates should be exceptions, not the norm |
| **Audit trails are not optional** | Log every tool call with attribution; if something goes wrong, you need the history |
| **Constraints beat permissions** | Don't ask if the repricer *should* move price; build a tool that *cannot* move it outside safe bounds |
| **Events beat polling** | Subscribe to Amazon events (Buy Box lost, low stock, cost spike) rather than hammering endpoints |
| **Staged rollout wins** | Move from read-only → reversible writes → gated spending; each gate is a confidence checkpoint |

---
