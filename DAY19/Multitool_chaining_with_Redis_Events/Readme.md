# Project README: Multi-tool Agent with Redis Event Queue

This project demonstrates a sophisticated ordering agent built in Google Colab, showcasing various advanced patterns for agent design, tool integration, and asynchronous processing.

## Architecture Diagram (Conceptual)

*(An architecture diagram would visually represent the following components and their interactions:)*

1.  **User Input**: The user interacts with the agent through natural language.
2.  **Anthropic Agent**: The core of the system, powered by the Anthropic Claude model. It interprets user requests and orchestrates tool calls.
    *   **Prompt Caching**: The agent leverages caching for system prompts and tool definitions to optimize token usage.
3.  **Tools (Python Functions)**: A set of Python functions exposed to the agent.
    *   **Synchronous Tools**: `check_inventory`, `create_order`, `verify_order`, `approve_order`.
        *   These interact with an **SQLite Database** (for `inventory` and `orders` tables).
        *   `create_order` includes a **Human-in-the-Loop Gate** for high-value orders, marking them `needs_approval`.
    *   **Asynchronous Tools**: `send_confirmation`, `check_job`, `inspect_dlq`.
        *   These interact with a **Redis Stream (fakeredis)** acting as an **Email Job Queue**.
4.  **Background Worker Thread**: A separate Python thread that continuously processes jobs from the Redis Stream.
    *   It uses a **Consumer Group** for reliable message delivery.
    *   Includes **Dead-Letter Queue (DLQ)** and **Retry Mechanism** for email jobs with invalid addresses.
5.  **Trace Spans**: `run_tool` is wrapped to record execution details (tool name, arguments, duration, success/failure) for every tool call, providing a detailed per-turn trace table.

```mermaid
graph TD
    A[User Input] --> B(Anthropic Agent)
    B --> C{Tools Orchestration}
    C --> |Synchronous| D[SQLite DB]
    C --> |Asynchronous| E[Redis Stream / Email Queue]
    D --> |check_inventory, create_order, verify_order, approve_order| F[Tool Functions]
    E --> |send_confirmation, check_job, inspect_dlq| F
    F --> B
    E --> G[Background Worker Thread]
    G --> H[Email Provider (Mock)]
    G --> I[Dead-Letter Queue (DLQ)]
    subgraph Human-in-the-Loop
        F -- Needs Approval --> J[Approval Gate]
        J -- approve_order --> F
    end
    subgraph Observability
        F -- Trace Spans --> K[Trace Table]
        B --> K
    end
    style D fill:#f9f,stroke:#333,stroke-width:2px
    style E fill:#ccf,stroke:#333,stroke-width:2px
    style G fill:#ffc,stroke:#333,stroke-width:2px
    style J fill:#fcc,stroke:#333,stroke-width:2px
    style K fill:#cfc,stroke:#333,stroke-width:2px
```

## Agent Capabilities

*   **Order Management**: Checks inventory, creates orders, and sends confirmations.
*   **Asynchronous Email**: Uses a Redis Stream to decouple email sending from the agent's main loop.
*   **Resilience**: Implements a retry mechanism and a Dead-Letter Queue for failed email jobs.
*   **Verification**: Ensures order details are correct using a `verify_order` tool.
*   **Human Oversight**: High-value orders require explicit approval via an `approve_order` tool.
*   **Observability**: Provides detailed trace spans for every tool call.
*   **Efficiency**: Utilizes prompt caching for system prompts and tool blocks to reduce token usage.

## Example Outputs

*(Below would be snippets from running the agent, demonstrating its capabilities, tool traces, and caching results.)*

### Successful Order Flow

```text
--- Running agent with tracing ---

  → check_inventory({'sku': 'MON-4'})
  → create_order({'sku': 'MON-4', 'qty': 1})
  → send_confirmation({'to': 'asha@x.com', 'order_id': <order_id>})
  → verify_order({'order_id': <order_id>})

--- Tool Call Trace ---
Tool            | Args                                       |     MS |   OK
----------------+--------------------------------------------+--------+-----
check_inventory | {'sku': 'MON-4'}                           |   0.41 |    ✅
create_order    | {'sku': 'MON-4', 'qty': 1}                 |   0.75 |    ✅
send_confirmation| {'to': 'asha@x.com', 'order_id': <order_id>}|   0.20 |    ✅
verify_order    | {'order_id': <order_id>}                   |   0.30 |    ✅
---------------------
Everything checks out! Here's a full summary:
...
```

### High-Value Order Requiring Approval

```text
Order for MON-4 with total $820.0 needs approval.

--- Tool Call Trace ---
Tool            | Args                                       |     MS |   OK
----------------+--------------------------------------------+--------+-----
check_inventory | {'sku': 'MON-4'}                           |   0.41 |    ✅
create_order    | {'sku': 'MON-4', 'qty': 2}                 |   0.75 |    ✅
---------------------
I have created an order for 2 4K Monitors (SKU: MON-4) totaling $820.00.
However, this order requires approval before it can be fulfilled. The order ID is <order_id>.
...
```

### DLQ Inspection

```text
Inspecting DLQ:
  DLQ Message: {'job_id': 'b6927c4a', 'to': 'invalid-email', 'subject': 'Invalid Email Test', 'body': 'This email should go to DLQ', 'retries': '2'}
```

### Prompt Caching Savings

*(Results from the prompt caching test would be displayed here after the kernel restart and re-execution.)*

```text
--- Testing Prompt Caching ---

--- Agent Turn 1 ---
... (Agent output) ...
Turn 1 LLM Calls Summary:
  Total input tokens: <X>
  Cache read input tokens: 0

--- Agent Turn 2 (Identical Request) ---
... (Agent output) ...
Turn 2 LLM Calls Summary:
  Total input tokens: <Y>
  Cache read input tokens: <Z>

--- Caching Savings Report ---
Tokens saved in Turn 2 due to caching: <Z>
This represents a saving of approximately <Percentage>% of the total input tokens for Turn 2's LLM calls.
```
