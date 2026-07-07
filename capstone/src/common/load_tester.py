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

# (method, path, json-body-or-None, budget_ms, weight)
ENDPOINTS = [
    ("GET", "/health", None, 50, 3),
    ("POST", "/api/v1/retrieve",
     {"query": "eligibility and subsidy amount?", "context": CTX, "top_k": 4}, 50, 2),
    ("POST", "/api/v1/pipeline/run",
     {"query": "What is the objective and key risk?", "context": CTX}, 5000, 1),
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
                  users: int = 10, duration_s: int = 10) -> Dict[str, Any]:
    """Run a fixed-duration load test. Returns per-endpoint + aggregate stats."""
    users = max(1, min(int(users), 100))
    duration_s = max(1, min(int(duration_s), 60))
    lat: Dict[str, List[float]] = {p: [] for _, p, _, _, _ in ENDPOINTS}
    err: Dict[str, int] = {p: 0 for _, p, _, _, _ in ENDPOINTS}
    lock = threading.Lock()
    stop_at = time.perf_counter() + duration_s
    # Weighted round-robin plan so ratios roughly match the CI mix.
    plan: List[tuple] = []
    for m, p, b, _, w in ENDPOINTS:
        plan += [(m, p, b)] * w

    def worker():
        i = 0
        while time.perf_counter() < stop_at:
            m, p, b = plan[i % len(plan)]
            i += 1
            ms, ok = _one_request(base_url, m, p, b)
            with lock:
                lat[p].append(ms)
                if not ok:
                    err[p] += 1

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=users) as ex:
        for _ in range(users):
            ex.submit(worker)
    elapsed = max(1e-6, time.perf_counter() - t0)

    budget = {p: b for _, p, _, b, _ in ENDPOINTS}
    rows, total_reqs, total_err, all_pass = [], 0, 0, True
    for _, p, _, _, _ in ENDPOINTS:
        n = len(lat[p])
        total_reqs += n
        total_err += err[p]
        p50 = round(statistics.median(lat[p]), 1) if lat[p] else 0.0
        p95 = round(_percentile(lat[p], 95), 1)
        mx = round(max(lat[p]), 1) if lat[p] else 0.0
        rps = round(n / elapsed, 1)
        ok = (n > 0 and err[p] == 0 and p95 <= budget[p])
        all_pass = all_pass and ok
        rows.append({"endpoint": p, "requests": n, "rps": rps,
                     "p50_ms": p50, "p95_ms": p95, "max_ms": mx,
                     "errors": err[p], "budget_ms": budget[p],
                     "status": "PASS" if ok else "FAIL"})
    return {
        "ok": True,
        "config": {"base_url": base_url, "users": users, "duration_s": duration_s},
        "aggregate": {"total_requests": total_reqs,
                      "total_rps": round(total_reqs / elapsed, 1),
                      "errors": total_err, "elapsed_s": round(elapsed, 1),
                      "all_pass": all_pass},
        "endpoints": rows,
    }
