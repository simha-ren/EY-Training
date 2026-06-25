#AI PROPOSAL GENERATOR AGENT PLATFORM


> Stack: Streamlit frontend · Azure backend (Azure OpenAI, AI Search, Cosmos DB, Document Intelligence). Orchestration with **Semantic Kernel / LangChain**-style agents (any of Semantic Kernel, LangGraph, or AutoGen works — the roles below are framework-agnostic).

---

## 1. Agents Used

ProposalForge runs **five cooperating agents**. One operates at ingestion time; four operate at request time under an orchestrator.

| Agent | Type | Responsibility | Key tools | Runs on |
|-------|------|----------------|-----------|---------|
| **Orchestrator Agent** | Planner / router | Plans the run, routes between agents, holds conversation memory, drives the clarification loop | Agent framework, state store | Azure Functions (Durable) / Container Apps |
| **Reasoning Agent** | Analyst | Interprets the RFP, extracts metadata filters, maps requirements → proposal sections, **detects gaps** | Azure OpenAI (GPT-4o) | Azure OpenAI |
| **Retrieval Agent** | Tool-calling | Hybrid retrieval + metadata filtering + semantic re-ranking | Azure AI Search, Cosmos DB (vectors) | Azure AI Search / Cosmos DB |
| **Action / Generation Agent** | Tool-calling | Composes grounded sections with citations; calls the format builders | `pptx_builder`, `docx_builder`, `pdf_builder` | Azure OpenAI + Functions |
| **Document Normalizer** | Ingestion agent | At upload: extracts layout, chunks, auto-tags metadata, embeds & indexes | Azure AI Document Intelligence, Azure OpenAI embeddings | Azure Functions |

### 1.1 What each agent does

- **Orchestrator Agent** — the control loop. Receives the user request, decides which agent to invoke next, keeps short-term memory of the conversation, and — crucially — decides whether to **pause and ask the user** (clarification loop) or proceed to generation.
- **Reasoning Agent** — reads the uploaded RFP, produces a structured requirement checklist, extracts filters (sector, content-type, skills, years), maps each requirement to a proposal section, and flags any **mandatory field with no grounded source** (the gap-detection signal).
- **Retrieval Agent** — for each section query it runs **hybrid retrieval** (keyword + vector) against Azure AI Search and Cosmos DB, applies permission-trimming and metadata filters, then **semantically re-ranks** the candidates.
- **Action / Generation Agent** — drafts each section grounded in the retrieved context with **inline citations**, assembles a structured key–value map of the proposal, and renders the user-chosen format (PPTX / Word / PDF).
- **Document Normalizer** — the ingestion-time agent that turns any uploaded file into searchable, embedded, metadata-tagged knowledge with source links preserved.

### 1.2 Interaction flow

```
User ──▶ Orchestrator
            │  (plan)
            ▼
        Reasoning Agent ──▶ extract filters, map requirements, detect gaps
            │
            ├── gap found ──▶ Orchestrator ──▶ ask User ──▶ (answer captured) ──▶ loop back
            │
            ▼ (no gap)
        Retrieval Agent ◀──▶ Knowledge Layer (AI Search + Cosmos DB)
            │
            ▼
        Action / Generation Agent ──▶ grounded draft + citations ──▶ PPTX/DOCX/PDF ──▶ User
```

---

## 2. RAGAS Evaluation

RAGAS is an open-source framework for evaluating RAG and agentic pipelines. It scores the **retriever** and the **generator** separately, so you can tell a retrieval problem from a generation problem — essential in a regulated BFSI setting where an unsupported claim is a real risk.

### 2.1 Why we need it

- A high faithfulness score with low context recall is a classic trap: the generator answers coherently from *partial* context while silently missing a requirement. Measuring only generation hides this — so we measure **both stages**.
- RAGAS turns "the proposal looks good" into **numbers we can gate releases on** and tie directly to the project KPIs (citation coverage, requirement coverage).

### 2.2 Metrics mapped to ProposalForge

| RAGAS metric | Stage | What it catches | Target |
|--------------|-------|-----------------|--------|
| **Faithfulness** | Generation | Claims in the draft not supported by retrieved context (hallucination) | ≥ 0.95 |
| **Response Relevancy** | Generation | Answer drifts from the actual requirement | ≥ 0.85 |
| **Context Precision** | Retrieval | Irrelevant chunks diluting the context / wrong ranking | ≥ 0.80 |
| **Context Recall** | Retrieval | Required information missing from retrieved context | ≥ 0.90 |
| **Context Entities Recall** | Retrieval | Key entities (client, product, dates) not retrieved | ≥ 0.85 |
| **Noise Sensitivity** | End-to-end | Quality degrading when irrelevant chunks slip in | ≤ 0.20 (lower = better) |
| **Factual Correctness** | Generation | Draft vs. ground-truth answer (when labelled) | ≥ 0.85 |
| **Semantic Similarity** | Generation | Draft vs. reference proposal section | ≥ 0.85 |

**Agentic metrics** (for the multi-agent layer, evaluated on multi-turn traces):

| RAGAS metric | What it measures |
|--------------|------------------|
| **Tool Call Accuracy** | Did the Retrieval / Action agents call the right tools with the right arguments? |
| **Agent Goal Accuracy** | Did the run achieve the user's goal (a complete, on-spec proposal)? |
| **Topic Adherence** | Did the copilot stay within the RFP/BFSI scope and not wander? |

### 2.3 Evaluation dataset

Build a small **golden set** of (RFP question → ideal answer) pairs from real + synthetic banking RFPs. Each sample:

| Field | Meaning |
|-------|---------|
| `user_input` | the section/requirement question |
| `retrieved_contexts` | chunks the Retrieval Agent returned |
| `response` | the section the copilot drafted |
| `reference` | the ground-truth / gold answer (for recall & correctness) |





### 2.7 How agents + RAGAS connect

- **Faithfulness** validates the **Action / Generation Agent** — it is the automated counterpart of the citation-coverage KPI and complements the runtime groundedness check.
- **Context Recall / Precision / Entities Recall** validate the **Retrieval Agent** and the Document Normalizer's chunking & tagging choices.
- **Tool Call Accuracy / Agent Goal Accuracy / Topic Adherence** validate the **Orchestrator** and the overall multi-agent run.
- The **Gap Detection** signal (Reasoning Agent) and RAGAS are complementary: gap detection prevents ungrounded generation *at runtime*; RAGAS measures grounding *quality* offline and online.

---

## 3. Success Metrics & KPIs

How we know it works. Two layers run together: **product KPIs** (business outcome) and **quality metrics** (the RAGAS scores from §2).

### 3.1 Product KPIs

| Metric | Target | How measured |
|--------|--------|--------------|
| Proposal turnaround time | **−70%** vs. baseline (first draft < 1 hr) | Timestamp from upload to first draft |
| First-draft acceptance | **≥ 60%** | % of sections kept with only minor edits |
| Citation coverage | **≥ 95%** | % of factual claims with a valid source |
| Requirement coverage | **≥ 98%** | % of mandatory RFP requirements addressed |
| Retrieval quality | precision@5 + groundedness | Offline eval set + LLM-graded groundedness |
| Latency | **P95 < 3s** retrieval | Application Insights traces |
| Asset reuse rate | ↑ over baseline | % of content sourced from existing assets |

### 3.2 Quality metrics (link to RAGAS)

The KPIs above are backed by the continuously-measured RAGAS scores, so a business goal always has an automated signal behind it:

| KPI | Backed by RAGAS metric (§2.2) |
|-----|-------------------------------|
| Citation coverage | **Faithfulness** ≥ 0.95 |
| Requirement coverage | **Context Recall** ≥ 0.90 + **Context Entities Recall** ≥ 0.85 |
| Retrieval quality | **Context Precision** ≥ 0.80, **Noise Sensitivity** ≤ 0.20 |
| First-draft acceptance | **Response Relevancy** ≥ 0.85, **Factual Correctness** ≥ 0.85 |
| Agent reliability | **Tool Call Accuracy**, **Agent Goal Accuracy**, **Topic Adherence** |

### 3.3 Secondary signals

Groundedness score · P95 retrieval latency · reduction in duplicated effort · number of clarification questions per proposal (a falling trend signals a maturing knowledge base).

---

## 4. Market Research & Competitive Landscape

### 4.1 Market size

The proposal / RFP-response software market is estimated at roughly **USD 2.9–3.3 billion in 2025–26** and is projected to grow at an **~11–12% CAGR** toward **USD 7–9 billion by the mid-2030s**, with **government and BFSI** among the leading, most compliance-heavy verticals. **Generative and agentic AI is the dominant disruption theme.**

### 4.2 Competitive landscape

| Segment | Representative players | Positioning |
|---------|------------------------|-------------|
| **Legacy leaders** | Loopio · Responsive (RFPIO) · Qvidian (Upland) | Strong content libraries, workflow & governance; AI layered on; human-in-the-loop drafting |
| **AI-native challengers** | AutoRFP.ai · Arphie · AutogenAI · Inventive AI | Agentic requirement extraction & first-draft generation; fast onboarding; lighter governance / data control |
| **Adjacent / security** | Conveyor · Whistic · SafeBase | Security-questionnaire-led; trust-center profiles |

### 4.3 Where ProposalForge fits

- A **clarification loop** that asks the user back instead of guessing — reducing hallucination in a regulated domain.
- **BFSI-grounded** answers with inline citations and a full audit trail.
- **Format-flexible** output (PPTX / Word / PDF) from one grounded model.
- Built on the organisation's **own Azure tenant** for data residency, security and cost control — a build-side alternative to SaaS lock-in.

> **Sources:** Future Market Insights and Fortune Business Insights (2025–26 market sizing); Loopio and Responsive 2026 industry reports. Figures are paraphrased and ranges vary by analyst.

---
