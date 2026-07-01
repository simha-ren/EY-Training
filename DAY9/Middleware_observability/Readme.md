
# 🔬 Demo 1 — FastAPI Middleware & Observability

**Scenario:** This project simulates the development of a FastAPI application for a global payments modernization initiative at EY, focusing on implementing key backend engineering best practices related to observability and resilience.

## 🚀 Learning Objectives

-   Attach HTTP middleware to a FastAPI app for various functionalities.
-   Utilize `structlog` for structured JSON logging with correlation IDs.
-   Expose a `/metrics` endpoint for Prometheus scraping.
-   Implement exponential-backoff retry mechanisms with `tenacity`.
-   Integrate a circuit breaker pattern using `pybreaker` to prevent cascade failures.
-   Implement a sliding-window rate limiter.
-   Ensure correlation ID propagation across outbound `httpx` calls.

## 🗺️ Road Map & Implemented Features

This project systematically builds out a robust FastAPI service, covering:

### Part 1 → Install Dependencies
Key libraries like `fastapi`, `uvicorn`, `structlog`, `tenacity`, `pybreaker`, `prometheus-client`, `prometheus-fastapi-instrumentator`, `httpx`, `pyngrok`, and `nest_asyncio` are installed and configured for a Colab environment.

### Part 2 → Structured Logging Middleware
-   `structlog` configured for structured JSON logging.
-   HTTP middleware implemented to handle `X-Correlation-Id` (generate if missing) and log request start/end.
-   Ensured `structlog` compatibility with Colab's execution model.

### Part 3 → Prometheus Metrics Middleware
-   Custom Prometheus `Histogram` (`PAYMENT_AMOUNT`) and `Counter` (`ERROR_COUNT`) metrics defined.
-   `prometheus-fastapi-instrumentator` used for automatic HTTP route instrumentation.
-   Metrics are registered once to prevent re-registration errors in Colab.

### Part 4 → Retry Logic with Tenacity
-   `tenacity` integrated for retrying flaky downstream calls (simulated `flaky_fraud_check`) with exponential backoff.

### Part 5 → Circuit Breaker with PyBreaker
-   `pybreaker` implemented with a custom `LoggingListener` to prevent cascading failures to a consistently failing fraud service.

### Part 6 → Run the Full App (ngrok tunnel)
-   FastAPI application runs on a dynamic port using `uvicorn` in a background thread.
-   `ngrok` tunnel provides a public URL for external access.
-   Robustness added for Colab re-execution (dynamic port assignment, ngrok session management, `nest_asyncio` compatibility).

### Extension A — Rate-Limiting Middleware (Implemented)
-   A sliding-window rate limiter is implemented to limit requests per client IP.
-   Returns `429 Too Many Requests` with a `Retry-After` header when the limit is exceeded.
-   A Prometheus `Counter` (`RATE_LIMIT_HITS`) tracks rate limit violations.

### Extension B — Correlation ID Propagation (Implemented)
-   `contextvars.ContextVar` stores the correlation ID per request.
-   Custom `HttpxCorrelationIdAuth` automatically injects `X-Correlation-Id` into outbound `httpx` requests.
-   Mock downstream services are used to verify propagation.

## 🧰 Dependencies

-   `fastapi`
-   `uvicorn[standard]`
-   `structlog`
-   `tenacity`
-   `pybreaker`
-   `prometheus-client`
-   `prometheus-fastapi-instrumentator`
-   `httpx`
-   `pyngrok`
-   `nest-asyncio`

## ⚙️ Configuration

-   **NGROK_TOKEN**: Retrieve your ngrok authentication token from [dashboard.ngrok.com](https://dashboard.ngrok.com) and store it in Colab secrets as `NGROK_TOKEN`.
-   **GRAFANA_CLOUD_REMOTE_WRITE_URL**, **GRAFANA_CLOUD_USERNAME**, **GRAFANA_CLOUD_API_KEY**: (For Extension C) These credentials should be stored in Colab secrets to enable Prometheus remote write to Grafana Cloud.

## 📝 Unresolved / Future Work

### Extension C — Prometheus + Grafana Dashboard (Advanced)
-   The core challenge is the lack of a readily available Python library for serializing Prometheus metrics into the specific remote write protobuf format. Manual protobuf definition or a specialized client library is required.
-   Once serialization is possible, metrics will be pushed to Grafana Cloud, allowing for dashboard creation (request rate, latency, error rate, circuit breaker state).

### Extension D — Structured Log Aggregation (Advanced)
-   Future work involves setting up a log aggregation solution (e.g., Elastic Cloud or local file-based) and configuring `structlog` to output newline-delimited JSON logs to a file.
-   This will enable advanced querying of logs, such as identifying requests with high latency for specific correlation IDs.
