"""Async job worker: consumes pipeline jobs from Azure Service Bus.

Runs as the ``${APP}-worker`` container/site. The heavy lifting lives in
src.orchestrator.service_bus (queue plumbing) and src.orchestrator.pipeline (the actual work); this is
just the entry point that keeps the receive loop alive.

Run locally:   python worker.py
On Azure:      set as the worker container's startup command.
Requires SERVICEBUS_CONNECTION_STRING (or managed identity) + SERVICEBUS_QUEUE.
"""
from __future__ import annotations

from src.orchestrator import service_bus


def main() -> None:
    if not service_bus.is_enabled():
        print("[worker] Service Bus is not configured "
              "(set SERVICEBUS_CONNECTION_STRING). Nothing to do; exiting.")
        return
    # run_worker uses src.orchestrator.service_bus.handle_job by default, which invokes the
    # pipeline and writes results back to the JobStore.
    service_bus.run_worker()


if __name__ == "__main__":
    main()
