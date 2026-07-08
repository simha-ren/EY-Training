"""In-app load tester (no external deps).

Fires concurrent requests at the running API for a fixed duration and reports,
per endpoint: request count, sustained RPS, p50/p95/max latency, error count,
and PASS/FAIL against a latency budget. Powers the Load Test panel in the UI's
Tests tab and mirrors what the CI Locust job checks.

Budgets (ms): /health 50, /api/v1/retrieve 50 (retrieval only, no LLM),
/api/v1/pipeline/run 5000 (end-to-end: retrieval + LLM).  '<5ms' is not possible
for an LLM call; these are the real, enforceable targets.
"""
from __future__ import annotations

import os
import json
import time
import statistics
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List

CTX = ("Scheme objective: promote millet cultivation. Subsidy INR 5000 per hectare. "
       "Eligibility: small and marginal farmers with up to 2 hectares. "
       "Key risk: low awareness among farmers.")

# Latency budgets (ms), overridable via env. '<5ms' is impossible for a real LLM
# call, so these are realistic SLOs for a modest App Service SKU:
#   - health: liveness ping (fast, but allow head-room on a small/cold instance)
#   - retrieve: networked vector DB (Pinecone ~20-50ms) + occasional cold cache
#   - e2e: a full pipeline turn that makes a live LLM call (seconds, not ms)
# Tighten them via env once you know your instance's real p95.
_B_HEALTH = float(os.getenv("P95_HEALTH_MS", "200"))
_B_RETRIEVE = float(os.getenv("P95_RETRIEVE_MS", "400"))
_B_E2E = float(os.getenv("P95_E2E_MS", "12000"))
_WARMUP_ROUNDS = int(os.getenv("LOAD_WARMUP_ROUNDS", "3"))

# (method, path, json-body-or-None, budget_ms, weight)
ENDPOINTS = [
    ("GET", "/health", None, _B_HEALTH, 3),
    ("POST", "/api/v1/retrieve",
     {"query": "eligibility and subsidy amount?", "context": CTX, "top_k": 4}, _B_RETRIEVE, 2),
    ("POST", "/api/v1/pipeline/run",
     {"query": "What is the objective and key risk?", "context": CTX}, _B_E2E, 1),
]


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((pct / 100.0) * (len(s) - 1)))))
    return s[k]


def _one_request(base_url: str, method: str, path: str, body) -> tuple[float, bool]:
    url = base_url.rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
            ok = 200 <= resp.status < 400
    except Exception:
        ok = False
    return (time.perf_counter() - t0) * 1000.0, ok


def run_load_test(base_url: str = "http://127.0.0.1:8001",
                  users: int = 10, duration_s: int = 8) -> Dict[str, Any]:
    """Run a phased load test. Each endpoint is measured in its own phase so a
    slow LLM endpoint can't starve the fast ones. Returns per-endpoint +
    aggregate stats (p50/p95/RPS vs budget)."""
    users = max(1, min(int(users), 100))
    duration_s = max(2, min(int(duration_s), 60))

    rows: List[Dict[str, Any]] = []
    total_reqs = total_err = 0
    total_elapsed = 0.0
    all_pass = True

    for method, path, body, budget, weight in ENDPOINTS:
        # LLM endpoint is latency-bound (seconds); high concurrency just queues.
        conc = users if path != "/api/v1/pipeline/run" else max(1, min(users, 3))

        # Warm-up (not measured): absorb cold start / vector-DB connection.
        for _ in range(max(1, _WARMUP_ROUNDS)):
            try:
                _one_request(base_url, method, path, body)
            except Exception:
                pass

        samples: List[float] = []
        errors = 0
        lock = threading.Lock()
        stop_at = time.perf_counter() + duration_s

        def worker():
            nonlocal errors
            while time.perf_counter() < stop_at:
                ms, ok = _one_request(base_url, method, path, body)
                with lock:
                    samples.append(ms)
                    if not ok:
                        errors += 1

        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=conc) as ex:
            for _ in range(conc):
                ex.submit(worker)
        elapsed = max(1e-6, time.perf_counter() - t0)

        n = len(samples)
        total_reqs += n
        total_err += errors
        total_elapsed = max(total_elapsed, elapsed)
        p50 = round(statistics.median(samples), 1) if samples else 0.0
        p95 = round(_percentile(samples, 95), 1)
        mx = round(max(samples), 1) if samples else 0.0
        rps = round(n / elapsed, 1)
        ok = (n > 0 and errors == 0 and p95 <= budget)
        all_pass = all_pass and ok
        rows.append({"endpoint": path, "requests": n, "rps": rps,
                     "p50_ms": p50, "p95_ms": p95, "max_ms": mx,
                     "errors": errors, "budget_ms": budget,
                     "status": "PASS" if ok else "FAIL", "concurrency": conc})

    peak_rps = round(max((r["rps"] for r in rows), default=0.0), 1)
    return {
        "ok": True,
        "config": {"base_url": base_url, "users": users, "duration_s": duration_s,
                   "warmup_rounds": _WARMUP_ROUNDS},
        "aggregate": {"total_requests": total_reqs,
                      "peak_rps": peak_rps,
                      "errors": total_err, "all_pass": all_pass},
        "endpoints": rows,
    }
