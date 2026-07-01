## Capstone Project: Small Support Agent Architecture

This project implements a **Small Support Agent** designed to handle customer inquiries using a combination of AI models, specialized tools, and robust infrastructure components. The agent demonstrates key concepts like short-term memory, long-term knowledge retrieval, tool orchestration, and observability.


### High-Level Flow:

1.  **User Input**: A customer's query is received by the Support Agent.
2.  **Short-Term Memory**: The agent stores the conversation history in Redis to maintain context.
3.  **Agent Orchestration (Live vs. Mock)**:
    *   **Live Mode**: The query, along with conversation history and a list of available tools (with their schemas), is sent to Anthropic Claude. Claude decides which tool(s) to use or to respond directly.
    *   **Offline Mock Mode**: A predefined, deterministic sequence of tool calls is executed, simulating the agent's behavior for testing and demonstration.
4.  **Tool Execution**: Based on Claude's (or the mock agent's) decision, the `Tool Dispatcher` executes the chosen tool(s).
    *   **Long-Term Recall**: The `recall_policy` tool queries the `Simple Vector Store` for relevant policy documents.
    *   **Operational Tools**: Tools like `lookup_order`, `create_ticket`, `request_refund`, and `approve_refund` interact with a simulated SQLite database.
    *   **Asynchronous Tool**: The `send_followup_email` tool places email tasks onto a Redis stream (queue), which are then processed by an `Email Worker`.
5.  **Robustness & Observability**: All tool calls are traced and recorded by the `Trace Recorder` for auditing and debugging. Retries are implemented for transient tool failures. Token usage is tracked in live mode.
6.  **Response**: The agent formulates a response based on tool outputs and policy information, which is then stored in short-term memory and returned to the user.

## Detailed Component Breakdown

### 1. Short-Term Memory (Redis / `fakeredis`)

*   **Purpose**: Stores the ongoing conversation history between the user and the agent, providing context for subsequent interactions.
*   **Implementation**: The `ShortTermMemory` class uses `fakeredis.FakeStrictRedis` to simulate a Redis instance. This allows for in-memory, fast key-value storage without requiring a running Redis server.
*   **Mechanism**: Each turn (user input or agent response) is stored as a JSON object in a Redis list, keyed by `session_id`. The memory is bounded (`ltrim`) to keep recent interactions.

### 2. Long-Term Recall (Simple Vector Store)

*   **Purpose**: Enables the agent to retrieve relevant policy documents based on a query, acting as its knowledge base.
*   **Implementation**: The `SimpleVectorStore` class contains predefined policy documents. It's a simplified
vector store, where documents and queries are converted into word-count vectors. Similarity is calculated using cosine similarity.
*   **Key Tool**: `recall_policy` uses this component to find and return policy matches.

### 3. Tools

The agent uses a variety of tools, defined with JSON schemas, to perform specific actions:

*   **`recall_policy(query: str)`**: Searches the `SimpleVectorStore` for policy documents related to the query.
*   **`lookup_order(order_id: str)`**: Queries a simulated SQLite database to fetch details about a specific order.
*   **`create_ticket(order_id: str, category: str, summary: str, priority: str)`**: Creates a new support ticket in the SQLite database.
*   **`request_refund(order_id: str, amount: float, reason: str)`**: Initiates a refund. Refunds above `$100` (defined by `APPROVAL_THRESHOLD`) automatically trigger a `needs_approval` status, requiring human intervention.
*   **`approve_refund(approval_id: str, approved: bool)`**: Simulates a human-in-the-loop gate for refund approvals, updating the status in the SQLite database.
*   **`send_followup_email(to: str, subject: str, body: str)`**: This is the **asynchronous queue-backed tool**. It places an email job onto a Redis Stream (`EMAIL_STREAM`) and returns a `job_id` immediately. The actual email sending is processed by a separate worker (`run_email_worker`).
*   **`check_email_job(job_id: str)`**: Checks the status of an asynchronous email job in Redis.

### 4. Agent Orchestration (`make_agent` function)

*   **Live Mode**: When `live` is `True` (meaning an Anthropic API key is provided), the agent interacts with Anthropic Claude. Claude receives the conversation history and tool definitions, then decides which tool to call or what to respond. The `run_tool` wrapper executes Claude's chosen tool, and the result is fed back to Claude.
*   **Offline Mock Mode**: When `live` is `False`, the agent executes a hardcoded sequence of tool calls, demonstrating the desired orchestration flow deterministically without needing an LLM call. This is crucial for testing and showcasing the agent's capabilities predictably.

### 5. Robustness & Observability

*   **Tracing**: The `TraceRecorder` class logs every tool call (`tool`, `args`, `ms`, `ok`, `attempts`). This provides a detailed audit trail of the agent's actions, invaluable for debugging and understanding agent behavior.
*   **Retries**: The `run_tool` wrapper implements retry logic (up to 2 retries) for transient errors, especially demonstrated with the `send_followup_email` tool which is configured to fail once initially.
*   **Token Reporting**: In live mode, token usage (input, output, cache read) from Anthropic Claude is tracked, which is essential for cost analysis and understanding the effectiveness of prompt caching.

### 6. Data Stores

*   **SQLite Database (`create_database`)**: Acts as a mock for various operational systems, storing `orders`, `tickets`, `refunds`, and `approvals` data in memory.
*   **Redis (`create_redis`)**: Uses `fakeredis` for short-term memory and for implementing the asynchronous email queue via Redis Streams.


### Conclusion:

The execution output successfully validates all the core requirements of the Capstone project:

*   **Short-term Memory**: The conversation (`user` and `assistant` turns) is stored and shown in "Short-term memory" section.
*   **Long-term Recall**: The `recall_policy` tool was used, and a policy was identified.
*   **Tools**: All seven tools were defined and actively used (`lookup_order`, `recall_policy`, `create_ticket`, `request_refund`, `approve_refund`, `send_followup_email`, `check_email_job`), including the asynchronous email tool.
*   **Agent Orchestration**: The agent correctly routed and chained tools, including the `request_refund` leading to `approve_refund` (human-approval gate).
*   **Robustness & Observability**: The `Trace spans` clearly show the sequence of tool calls, their success/failure, and the `send_followup_email` tool demonstrated retry functionality (`attempts=2`). Token usage is also reported.
