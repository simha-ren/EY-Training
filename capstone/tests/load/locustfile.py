"""Load test for the ProposalForge API (Locust).

Three request groups, each with its own latency budget (enforced on exit):

  * GET  /health              -> p95 < 50 ms    (liveness, no work)
  * POST /api/v1/retrieve     -> p95 < 50 ms    (retrieval only, NO LLM)
  * POST /api/v1/pipeline/run -> p95 < 5000 ms  (end-to-end: retrieval + LLM)

Local run against a live server:
    locust -f tests/load/locustfile.py --host http://localhost:8001
Headless (CI), e.g. 20 users for 60s:
    locust -f tests/load/locustfile.py --host http://localhost:8001 \
           --headless -u 20 -r 5 -t 60s
On exit the run FAILS (exit code 1) if any group breaches its p95 budget, so it
gates the CI/CD pipeline. Override budgets with env vars P95_HEALTH_MS,
P95_RETRIEVE_MS, P95_E2E_MS.
"""
import os
from locust import HttpUser, task, between, events

CTX = ("Scheme objective: promote millet cultivation. Subsidy INR 5000 per hectare. "
       "Eligibility: small and marginal farmers with up to 2 hectares. "
       "Key risk: low awareness among farmers. Contact: district agriculture office.")

BUDGETS_MS = {
    "GET /health": float(os.getenv("P95_HEALTH_MS", "50")),
    "POST /api/v1/retrieve": float(os.getenv("P95_RETRIEVE_MS", "50")),
    "POST /api/v1/pipeline/run": float(os.getenv("P95_E2E_MS", "5000")),
}


class ApiUser(HttpUser):
    wait_time = between(0.05, 0.25)

    @task(6)
    def health(self):
        self.client.get("/health", name="GET /health")

    @task(4)
    def retrieve_only(self):
        self.client.post("/api/v1/retrieve", name="POST /api/v1/retrieve",
                         json={"query": "eligibility and subsidy amount?",
                               "context": CTX, "top_k": 4})

    @task(2)
    def pipeline_run(self):
        self.client.post("/api/v1/pipeline/run", name="POST /api/v1/pipeline/run",
                         json={"query": "What is the objective and key risk?", "context": CTX})


@events.quitting.add_listener
def _enforce_thresholds(environment, **kwargs):
    failures = []
    stats = environment.stats
    if stats.total.num_failures > 0:
        failures.append(f"{stats.total.num_failures} request failures")
    for name, budget in BUDGETS_MS.items():
        entry = None
        for (n, method), e in stats.entries.items():
            if n == name:
                entry = e
                break
        if entry is None or entry.num_requests == 0:
            continue
        p95 = entry.get_response_time_percentile(0.95)
        status = "OK" if p95 <= budget else "FAIL"
        print(f"[threshold] {name:<28} p95={p95:>7.1f}ms  budget={budget:>7.0f}ms  {status}")
        if p95 > budget:
            failures.append(f"{name} p95 {p95:.0f}ms > {budget:.0f}ms")
    if failures:
        print("LOAD TEST FAILED: " + "; ".join(failures))
        environment.process_exit_code = 1
    else:
        print("LOAD TEST PASSED: all p95 latency budgets met.")
        environment.process_exit_code = 0
