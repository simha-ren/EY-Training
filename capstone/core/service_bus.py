"""Azure Service Bus job queue for the analysis pipeline.

Decouples submission from processing: the API enqueues a job message; a separate
worker (worker.py) consumes messages and runs the pipeline. This scales the heavy
LLM work independently of the web tier.

Config (env):
    SERVICEBUS_CONNECTION_STRING   (or SERVICEBUS_FQDN + managed identity)
    SERVICEBUS_QUEUE               default "pipeline-jobs"

If Service Bus isn't configured/installed, is_enabled() is False and callers fall
back to the in-process BackgroundTasks path. The message build/parse/handle logic
is pure and unit-tested offline.
"""
from __future__ import annotations

import os
import json
from typing import Dict, Any, Callable, Optional

QUEUE = os.getenv("SERVICEBUS_QUEUE", "pipeline-jobs")


def is_enabled() -> bool:
    return bool(os.getenv("SERVICEBUS_CONNECTION_STRING") or os.getenv("SERVICEBUS_FQDN"))


# ---- pure message helpers (unit-tested) ----
def build_message(job_id: str, task: str, context: str) -> str:
    return json.dumps({"job_id": job_id, "task": task, "context": context})


def parse_message(body: str) -> Dict[str, Any]:
    return json.loads(body)


def _client():
    """Create a ServiceBusClient from a connection string or managed identity."""
    from azure.servicebus import ServiceBusClient
    conn = os.getenv("SERVICEBUS_CONNECTION_STRING")
    if conn:
        return ServiceBusClient.from_connection_string(conn)
    fqdn = os.getenv("SERVICEBUS_FQDN")
    if fqdn:
        from azure.identity import DefaultAzureCredential
        return ServiceBusClient(fqdn, credential=DefaultAzureCredential())
    raise RuntimeError("Service Bus not configured")


def enqueue_job(job_id: str, task: str, context: str) -> bool:
    """Send a job onto the queue. Returns False (no raise) if unavailable."""
    if not is_enabled():
        return False
    try:
        from azure.servicebus import ServiceBusMessage
        with _client() as client:
            with client.get_queue_sender(QUEUE) as sender:
                sender.send_messages(ServiceBusMessage(build_message(job_id, task, context)))
        return True
    except Exception as e:  # pragma: no cover - network/SDK dependent
        print(f"Service Bus enqueue failed: {e}")
        return False


def handle_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Core worker logic: run the pipeline for one message, persist, notify.

    Pure enough to unit-test offline (no Service Bus needed).
    """
    from core.pipeline import run_pipeline
    from core.retriever import get_retriever
    from core.job_store import JobStore

    job_id = payload["job_id"]
    task = payload["task"]
    context = payload["context"]
    store = JobStore()
    store.ensure(job_id, task, context, status="running")
    store.set_status(job_id, "running")
    try:
        retriever = get_retriever()
        retriever.build(context, job_id, "servicebus-document")
        docs = [{"filename": "servicebus-document", "content": context,
                 "metadata": {"extension": ".txt"}, "document_id": job_id}]
        result = run_pipeline(docs, task, retriever=retriever)
        store.set_result(job_id, result, status="done")
        try:
            from core.notifications import notify_pipeline_complete
            notify_pipeline_complete(result)
        except Exception:
            pass
        return result
    except Exception as e:
        store.set_result(job_id, {"error": str(e)}, status="error")
        try:
            from core.notifications import get_notifier
            get_notifier().notify("pipeline_error", "Pipeline failed",
                                  f"Job {job_id} errored: {e}", {"job_id": job_id})
        except Exception:
            pass
        raise


def run_worker(handler: Optional[Callable[[Dict[str, Any]], Any]] = None,
               max_messages: Optional[int] = None):
    """Blocking receive loop. Completes messages on success, dead-letters on error.

    max_messages: stop after N messages (for tests/smoke); None = run forever.
    """
    handler = handler or handle_job
    if not is_enabled():
        raise RuntimeError("Service Bus not configured (set SERVICEBUS_CONNECTION_STRING)")
    processed = 0
    with _client() as client:
        with client.get_queue_receiver(QUEUE, max_wait_time=30) as receiver:
            print(f"[worker] listening on queue '{QUEUE}'")
            for msg in receiver:
                try:
                    handler(parse_message(str(msg)))
                    receiver.complete_message(msg)
                except Exception as e:  # pragma: no cover
                    print(f"[worker] job failed, dead-lettering: {e}")
                    receiver.dead_letter_message(msg, reason="processing_error")
                processed += 1
                if max_messages and processed >= max_messages:
                    break