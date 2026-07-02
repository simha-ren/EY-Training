"""Compatibility shim: re-export functions from `service_bus.py` as
module-level names so `from core import servicebus` provides the expected API.
"""
from .service_bus import (
    is_enabled,
    build_message,
    parse_message,
    enqueue_job,
    handle_job,
    run_worker,
    QUEUE,
)

__all__ = [
    "is_enabled",
    "build_message",
    "parse_message",
    "enqueue_job",
    "handle_job",
    "run_worker",
    "QUEUE",
]
