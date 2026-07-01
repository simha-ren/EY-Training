"""Load test for the ProposalForge API (Locust, open-source).

Local run against a live server:
    locust -f tests/load/locustfile.py --host http://localhost:8001
Headless (CI smoke), e.g. 20 users for 30s with latency thresholds:
    locust -f tests/load/locustfile.py --host http://localhost:8001 \
           --headless -u 20 -r 5 -t 30s
"""
from locust import HttpUser, task, between

CTX = ("Scheme objective: promote millet cultivation. Subsidy INR 5000 per hectare. "
       "Key risk: low awareness among farmers.")


class ApiUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(5)
    def health(self):
        self.client.get("/health", name="GET /health")

    @task(3)
    def metrics(self):
        self.client.get("/metrics", name="GET /metrics")

    @task(2)
    def pipeline_run(self):
        self.client.post("/api/v1/pipeline/run", name="POST /pipeline/run",
                         json={"query": "objective and risks?", "context": CTX})
