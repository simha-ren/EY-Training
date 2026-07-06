"""Pipeline worker: consumes analysis jobs from Azure Service Bus and runs them.

Run as a separate container/process from the web tier so heavy LLM work scales
independently. Falls back with a clear message if Service Bus isn't configured.

    python worker.py
"""
from __future__ import annotations

import sys
from core import service_bus


def main() -> int:
    if not service_bus.is_enabled():
        print("Service Bus not configured (set SERVICEBUS_CONNECTION_STRING "
              "or SERVICEBUS_FQDN). Nothing to consume; exiting.")
        return 0
    print(f"Worker starting; consuming queue '{service_bus.QUEUE}'. Ctrl-C to stop.")
    try:
        service_bus.run_worker()
    except KeyboardInterrupt:
        print("Worker stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
