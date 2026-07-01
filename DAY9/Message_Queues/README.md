# MESSAGE_QUEUES

## Description
This project demonstrates a FastAPI application with various message queue implementations and advanced features within a Google Colab environment. It explores different brokers (in-memory, RabbitMQ, Azure Service Bus) and includes concepts like dead-letter queues, priority queuing, background workers, and Prometheus monitoring.

## Setup Instructions
1.  **Clone the Repository (if applicable):**
    ```bash
    # git clone <your-repo-url>
    # cd <your-repo-directory>
    ```
2.  **Install Dependencies:**
    Run the first code cell in the notebook to install all required Python packages:
    ```python
    !pip install fastapi uvicorn[standard] structlog tenacity pyngrok nest-asyncio httpx aio-pika azure-servicebus prometheus_client
    ```
3.  **Configure Secrets:**
    This notebook uses Google Colab secrets for sensitive information. Ensure the following secrets are configured in the Colab Secrets panel (the '🔑' icon on the left sidebar) with 'Notebook access' enabled:
    *   `NGROK_TOKEN`: Your ngrok authentication token for exposing the FastAPI application.
    *   `CLOUDAMQP_URL` (for Extension A): The connection URL for your CloudAMQP (RabbitMQ) instance.
    *   `SB_CONN_STR` (for Extension B): The connection string for your Azure Service Bus namespace.

4.  **Run the FastAPI Application:**
    Execute the core application cell (`xqq_4N_B4ekg`) to start the FastAPI server and ngrok tunnel.

5.  **Explore Functionality:**
    Execute the client interaction cell (`h2Jl0j9co8P9`) to send requests to the FastAPI application and observe the queue behavior. Experiment with different extensions by modifying the broker implementation in the main application cell.

## Extensions Implemented
*   **Extension A: Real RabbitMQ via CloudAMQP**
*   **Extension B: Azure Service Bus Integration**
*   **Extension C: Priority Queueing (In-Memory)**
*   **Extension D: Background Worker with Prometheus DLQ Alert**

## Output:

https://github.com/simha-ren/EY-Training/blob/main/DAY9/Message_Queues/Message_queues.PNG

## Usage
Follow the cells in order, uncommenting and modifying as instructed to switch between different message broker implementations and enable advanced features.
