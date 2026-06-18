# LangGraph Multi-Agent Research System

A scalable **multi-agent AI research workflow** built with **LangGraph** that autonomously transforms a user objective into actionable tasks, executes research workflows, validates results, and improves responses through an iterative feedback loop.

The architecture follows:

**Plan → Execute → Verify → Refine**

---

# Architecture Overview

The system consists of three specialized agents:

| Agent | Responsibility |
|---|---|
| 🧠 Planner Agent | Converts user goals into structured actionable tasks |
| ⚙️ Executor Agent | Executes tasks, performs research, and generates results |
| ✅ Verifier Agent | Evaluates output quality and decides whether refinement is required |

All agents communicate through a shared `AgentState`.

---

# System Architecture Diagram

```mermaid
flowchart TD

    USER["👤 User Goal"]

    STATE["📦 Shared AgentState<br/><br/>
    goal<br/>
    tasks<br/>
    results<br/>
    critique<br/>
    approved<br/>
    iterations"]

    PLANNER["🧠 Planner Agent<br/><br/>
    Goal Understanding<br/>
    Task Decomposition"]

    TASKS["📋 Generated Tasks"]

    EXECUTOR["⚙️ Executor Agent<br/><br/>
    Task Execution<br/>
    Result Generation"]

    TOOLS["🔎 Research Tools<br/><br/>
    Web Search<br/>
    External APIs"]

    LLM["🤖 LLM Engine<br/><br/>
    Reasoning & Synthesis"]

    RESULTS["📄 Generated Results"]

    VERIFIER["✅ Verifier Agent<br/><br/>
    Quality Evaluation<br/>
    Validation"]

    DECISION{"🎯 Approved?"}

    FINAL["🚀 Final Response"]

    FEEDBACK["🔄 Critique Feedback"]


    USER --> STATE

    STATE --> PLANNER

    PLANNER --> TASKS

    TASKS --> EXECUTOR

    EXECUTOR --> TOOLS

    TOOLS --> LLM

    LLM --> RESULTS

    RESULTS --> VERIFIER

    VERIFIER --> DECISION

    DECISION -->|Yes| FINAL

    DECISION -->|No| FEEDBACK

    FEEDBACK --> EXECUTOR
