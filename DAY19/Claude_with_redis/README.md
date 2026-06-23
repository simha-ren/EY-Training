# Claude Agent with FastAPI Backend and Redis Memory

This notebook demonstrates building a sophisticated tool-using agent using Claude, integrated with a FastAPI backend and a Redis memory layer. It covers several advanced enhancements for agentic systems.

## Architecture Overview

The system consists of the following key components:

*   **Claude Agent:** The core intelligence that interprets user requests, decides which tools to use, and generates responses.
*   **FastAPI Backend:** A simulated external API that exposes endpoints for `get_order` and `get_customer`. In a real-world scenario, this would be your production backend service.
*   **Redis Memory (`RedisMemory` class):** Stores both short-term conversation history and long-term user facts. Initially uses `fakeredis` for local development, later replaced with a real Redis instance.
*   **Tools:** Python functions (`get_order`, `remember_fact`, `recall_fact`, `forget_fact`, `get_customer`) that the Claude agent can invoke to interact with the external API and Redis memory.
*   **Dispatch Map:** A mapping between tool names (as defined in `TOOLS`) and their corresponding Python functions (`DISPATCH_V4`).

**Interaction Flow:**
1.  A user sends a message to the Claude Agent.
2.  The Agent, provided with `SYSTEM` instructions and `TOOLS` definitions, processes the message.
3.  If a tool is required, the Agent outputs a `tool_use` block.
4.  The system dispatches the `tool_use` request to the appropriate Python function via the `DISPATCH_V4` map.
5.  The tool function executes (e.g., calls the FastAPI backend or interacts with Redis).
6.  The tool's result is returned to the Agent as a `tool_result` block.
7.  The Agent processes the `tool_result` and generates a natural language response back to the user.

*A visual architecture diagram would show the Claude Agent making requests to a dispatcher, which routes to Python tool functions. These functions interact with the FastAPI backend (for `get_order`, `get_customer`) and the Redis memory (for `remember_fact`, `recall_fact`, `forget_fact`). The agent also uses Redis for conversation history.* 

## Implemented Features & Enhancements

This notebook progressively enhances the agent system with the following capabilities:

1.  **Conversation Compaction (Rolling Summary):**
    *   The `agent_turn_compacted` function intelligently summarizes older conversation turns using a cheaper language model when the history exceeds a defined limit. This helps to keep the context window bounded and manage token usage effectively. While there was a minor error during one of the summarization attempts (`Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': 'This model does not support assistant message prefill. The conversation must end with a user message.'}`), the core mechanism for history management was demonstrated.

2.  **TTL (Time-To-Live) & Forget Tool:**
    *   The `RedisMemory` class was refactored to store individual facts as separate Redis keys, allowing each fact to have its own `ttl_seconds`. A new `forget_fact` tool was added, enabling the agent to explicitly delete stored facts.
    *   **Demonstration:** Successfully stored a fact with a 3-second TTL, which subsequently expired and could not be recalled, confirming the TTL functionality. The `forget_fact` tool was also shown to work correctly by deleting a permanent fact.

3.  **Parallel Tool Lookups:**
    *   A new `get_customer` tool and corresponding `/customers/{customer_id}` FastAPI endpoint were added. The `agent_turn_parallel` function, with an updated system prompt, demonstrates Claude's ability to issue multiple `tool_use` calls concurrently within a single turn to fetch both order and customer details in parallel.
    *   **Demonstration:** The agent successfully executed `get_order` and `get_customer` in parallel for specific IDs, combining their results into a single comprehensive response.

4.  **Guarded Writes (PII Protection):**
    *   The `remember_fact` tool was enhanced (`tool_remember_fact_guarded`) to detect and reject Personally Identifiable Information (PII) like email addresses and credit card numbers using regex. The agent's system prompt (`SYSTEM_GUARDED`) was updated to instruct it to politely decline requests to store PII.
    *   **Demonstration:** Attempts to store an email address and a credit card number were successfully rejected by the tool, and the agent responded with polite explanations for the refusal, without storing the sensitive data.

5.  **Token Accounting:**
    *   The `agent_turn_with_tokens` function was introduced to track and print the cumulative input and output tokens used by the Claude model for each step of an agent's turn. This provides transparency and control over token usage.
    *   **Demonstration:** Logged token usage for various interactions, including simple questions, tool-based recalls, and PII rejection scenarios, showing cumulative input and output token counts.

6.  **Real Redis Integration:**
    *   The `fakeredis` library was replaced with `redis.Redis.from_url`, connecting the `RedisMemory` instance to a live Upstash Redis database. This demonstrates seamless transition from mock to production-ready infrastructure without altering the `RedisMemory` class logic.
    *   **Demonstration:** A successful connection to the real Redis instance was established, and a test fact was set, recalled, and deleted, confirming the functionality of the live Redis setup.

## Key Demonstrations and Outputs

*   **Basic Order Lookup:** The agent successfully retrieves order details using the `get_order` tool.
    ```
    USER: What is the status of order A1002?
    AGENT: → tool: get_order({'order_id': 'A1002'})
    Here are the details for order **A1002**:
    - **Item:** USB-C Hub
    - **Quantity:** 2
    - **Status:** Processing
    - **Total:** $58.00
    ```

*   **Remembering and Recalling Facts:** The agent can store and retrieve user preferences.
    ```
    USER: Please remember that my shipping preference is express.
    AGENT: → tool: remember_fact({'key': 'shipping_pref', 'value': 'express'})
    Got it! I've saved your shipping preference as **express**.

    USER: What did I say my shipping preference was?
    AGENT: → tool: recall_fact({'key': 'shipping_pref'})
    Your shipping preference is set to **express**.
    ```

*   **Parallel Tool Use:** The agent concurrently uses `get_order` and `get_customer`.
    ```
    USER: What is the status of order A1001 and who is the customer C100?
    AGENT: → tool: get_order({'order_id': 'A1001'})
    → tool: get_customer({'customer_id': 'C100'})
    Here's the information you requested:
    **Order A1001:** ...
    **Customer C100:** ...
    ```

*   **PII Rejection:** The agent politely refuses to store sensitive information.
    ```
    USER: Please remember my email is asha.example@gmail.com.
    AGENT: I'm sorry, but I'm unable to store your email address. Saving sensitive personal information like email addresses could pose a privacy risk, so I'm not able to store it.
    ```

*   **Token Usage Tracking:** Each turn's token consumption is logged.
    ```
    USER: Hello, what is your name?
    → Step 1: Tokens this step - Input: 1093, Output: 96. Cumulative - Input: 1093, Output: 96
    AGENT: Hi there! I'm your **Order Support Assistant**.
    ```

*   **Real Redis Connection:** Verified successful connection and basic operations on a live Redis instance.
    ```
    Successfully connected to real Redis!
    RedisMemory 'mem' re-instantiated with the new Redis client.
    Stored 'redis_connection_test' fact in new Redis instance.
    Recalling 'redis_connection_test': success_real_redis
    ```

## How to Run This Notebook

1.  **Install Dependencies:** Run the first code cell (`!pip install -q ...`) to install `anthropic`, `fastapi`, `httpx`, and `fakeredis`.
2.  **Set API Key:** Provide your `ANTHROPIC_API_KEY` in Colab secrets (recommended) or directly in the `os.environ` variable in the designated cell.
3.  **FastAPI Deployment (Optional for Stretch Goal):** If attempting the 'Real FastAPI' stretch goal, deploy your FastAPI application to a public URL (e.g., Google Cloud Run, Heroku) and update the `FASTAPI_BASE_URL` variable accordingly. For local tunneling, use tools like `ngrok`.
4.  **Redis Setup (Optional for Stretch Goal):** For real Redis integration, create an Upstash Redis database (or similar provider) and obtain its connection URL. Update the `REDIS_URL` in the `qjhRgosi_PI_` cell with your Redis connection string.
5.  **Execute Cells:** Run all cells sequentially. The notebook is designed to build the system incrementally and demonstrate each feature.
