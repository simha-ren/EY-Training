"""Compatibility shim.

The Service Bus implementation lives at ``src.orchestrator.service_bus``. Some
callers and tests import it as ``src.common.servicebus`` (the pre-restructure
path), so this module re-exports the public API to keep both import paths valid.
"""
from src.orchestrator.service_bus import (  # noqa: F401
    is_enabled,
    build_message,
    parse_message,
    enqueue_job,
    handle_job,
    run_worker,
)
