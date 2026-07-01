#!/usr/bin/env python3
"""Service Bus worker entrypoint. Runs the analysis pipeline for queued jobs.

Deploy as a separate container/process alongside the web app:
    python worker.py
Requires SERVICEBUS_CONNECTION_STRING (or SERVICEBUS_FQDN + managed identity).
"""
from core.servicebus import run_worker, is_enabled

if __name__ == "__main__":
    if not is_enabled():
        raise SystemExit("Service Bus not configured. Set SERVICEBUS_CONNECTION_STRING.")
    run_worker()