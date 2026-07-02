"""Notifications via Azure services.

Backends (selected from the environment, first match wins):
  * Azure Communication Services Email - ACS_CONNECTION_STRING + ACS_SENDER + NOTIFY_EMAIL_TO
  * Azure webhook (Logic App HTTP trigger / Teams / Slack incoming) - NOTIFY_WEBHOOK_URL
  * no-op - nothing configured (app still runs)

Used to alert on pipeline completion, quality-gate flags, and approval requests.
The webhook path uses only the stdlib, so it is fully testable offline.
"""
from __future__ import annotations

import os
import json
import urllib.request
from typing import Optional, Dict, Any


class _NoopNotifier:
    provider = "none"
    enabled = False

    def notify(self, event: str, title: str, message: str,
               data: Optional[Dict[str, Any]] = None) -> bool:
        return False


class WebhookNotifier:
    """POST a JSON card to an Azure Logic App / Teams / Slack incoming webhook."""
    provider = "webhook"
    enabled = True

    def __init__(self, url: Optional[str] = None):
        self.url = url or os.getenv("NOTIFY_WEBHOOK_URL", "")

    def build_payload(self, event, title, message, data):
        # Compatible with Teams "text" cards, Slack, and Logic App HTTP triggers.
        return {"event": event, "title": title, "text": f"**{title}**\n\n{message}",
                "message": message, "data": data or {}}

    def notify(self, event, title, message, data=None) -> bool:
        if not self.url:
            return False
        payload = json.dumps(self.build_payload(event, title, message, data)).encode()
        req = urllib.request.Request(self.url, data=payload,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return 200 <= resp.status < 300
        except Exception as e:  # pragma: no cover - network dependent
            print(f"Webhook notify failed: {e}")
            return False


class AzureEmailNotifier:
    """Azure Communication Services - Email."""
    provider = "azure_email"
    enabled = True

    def __init__(self):
        self.conn = os.getenv("ACS_CONNECTION_STRING", "")
        self.sender = os.getenv("ACS_SENDER", "")
        self.to = [x.strip() for x in os.getenv("NOTIFY_EMAIL_TO", "").split(",") if x.strip()]
        if not (self.conn and self.sender and self.to):
            raise RuntimeError("ACS email requires ACS_CONNECTION_STRING, ACS_SENDER, NOTIFY_EMAIL_TO")

    def notify(self, event, title, message, data=None) -> bool:
        from azure.communication.email import EmailClient  # lazy
        client = EmailClient.from_connection_string(self.conn)
        body = message + ("\n\n" + json.dumps(data, indent=2) if data else "")
        msg = {
            "senderAddress": self.sender,
            "recipients": {"to": [{"address": a} for a in self.to]},
            "content": {"subject": f"[ProposalForge] {title}", "plainText": body},
        }
        try:
            poller = client.begin_send(msg)
            poller.result()
            return True
        except Exception as e:  # pragma: no cover - network dependent
            print(f"Azure email notify failed: {e}")
            return False


_NOTIFIER = None


def get_notifier():
    """Singleton notifier chosen from the environment."""
    global _NOTIFIER
    if _NOTIFIER is not None:
        return _NOTIFIER
    try:
        if os.getenv("ACS_CONNECTION_STRING") and os.getenv("ACS_SENDER") and os.getenv("NOTIFY_EMAIL_TO"):
            _NOTIFIER = AzureEmailNotifier()
            return _NOTIFIER
    except Exception as e:
        print(f"Azure email notifier unavailable ({e}); trying webhook.")
    if os.getenv("NOTIFY_WEBHOOK_URL"):
        _NOTIFIER = WebhookNotifier()
        return _NOTIFIER
    _NOTIFIER = _NoopNotifier()
    return _NOTIFIER


# ---- Convenience helpers for app events ----
def notify_pipeline_complete(result: Dict[str, Any]) -> bool:
    n = get_notifier()
    report = result.get("report", {})
    ev = result.get("evaluation", {}).get("gate", {})
    title = f"Pipeline complete — score {report.get('score')}/10 ({ev.get('verdict', 'n/a')})"
    msg = (f"Run {result.get('run_id')} finished on backend "
           f"{result.get('backend')} in {result.get('latency_s')}s. "
           f"Guardrail hits: {result.get('guardrail_hits', 0)}.")
    return n.notify("pipeline_complete", title, msg, {
        "run_id": result.get("run_id"), "score": report.get("score"),
        "gate": ev.get("verdict"), "trace_url": result.get("trace_url")})


def notify_approval_needed(doc_name: str, requested_by: str, request_id: str) -> bool:
    n = get_notifier()
    return n.notify("approval_needed", "Approval requested",
                    f"'{doc_name}' needs review (requested by {requested_by}).",
                    {"request_id": request_id})
