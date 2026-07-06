"""Locust load test for ProposalForge Pro.

Run against a live instance:

    locust -f tests/load/locustfile.py --host http://127.0.0.1:8001 \
        --headless -u 20 -r 5 -t 60s --only-summary

The task mix is weighted toward cheap read endpoints so the smoke test stays
fast and stable in CI; a single heavier pipeline call exercises the full path.
"""
from locust import HttpUser, task, between


SAMPLE_CONTEXT = (
    "Under the Kisan Credit Card scheme, farmers can get crop loans up to "
    "3 lakh rupees at 4% interest. The scheme covers seasonal operations."
)


class ProposalForgeUser(HttpUser):
    wait_time = between(0.5, 2.0)

    @task(5)
    def health(self):
        self.client.get("/health", name="GET /health")

    @task(2)
    def metrics(self):
        self.client.get("/metrics", name="GET /metrics")

    @task(1)
    def pipeline_run(self):
        self.client.post(
            "/api/v1/pipeline/run",
            json={"query": "How much can a farmer borrow?", "context": SAMPLE_CONTEXT},
            name="POST /api/v1/pipeline/run",
        )
