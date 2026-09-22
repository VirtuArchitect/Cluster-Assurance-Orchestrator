from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.core.config import Settings
from app.services.support_status import latest_run_summary


def alert_status(settings: Settings) -> dict[str, Any]:
    latest = latest_run_summary(settings.evidence_dir)
    trustworthy = evidence_is_trustworthy(settings, latest)
    return {
        "enabled": settings.enable_alerts,
        "trustworthy_evidence": trustworthy,
        "email": {
            "configured": bool(settings.alert_email_to),
            "target": settings.alert_email_to,
            "state": "READY" if settings.enable_alerts and settings.alert_email_to and trustworthy else "GATED",
        },
        "webhook": {
            "configured": bool(settings.alert_webhook_url),
            "state": "READY" if settings.enable_alerts and settings.alert_webhook_url and trustworthy else "GATED",
        },
        "later_adapters": {
            "checkmk": "PLANNED",
            "servicenow": "PLANNED",
        },
        "latest_run": latest,
        "reason": alert_gate_reason(settings, latest, trustworthy),
    }


def send_test_alert(settings: Settings) -> dict[str, Any]:
    status = alert_status(settings)
    if not status["enabled"] or not status["trustworthy_evidence"]:
        return status | {"delivery": "SKIPPED"}
    deliveries = []
    if settings.alert_email_to:
        deliveries.append({"adapter": "email", "status": "DRY_RUN", "target": settings.alert_email_to})
    if settings.alert_webhook_url:
        deliveries.append(send_webhook(settings.alert_webhook_url, status))
    return status | {"delivery": "ATTEMPTED", "deliveries": deliveries}


def evidence_is_trustworthy(settings: Settings, latest: dict[str, Any]) -> bool:
    return bool(latest.get("available")) and not settings.demo_mode and settings.tls_mode == "strict"


def alert_gate_reason(settings: Settings, latest: dict[str, Any], trustworthy: bool) -> str:
    if not settings.enable_alerts:
        return "Alert delivery is disabled by CAO_ENABLE_ALERTS."
    if not latest.get("available"):
        return "No health evidence is available."
    if not trustworthy:
        return "Evidence is not yet trusted for outbound alerting."
    return "Email/webhook alerting is ready; Checkmk and ServiceNow remain planned."


def send_webhook(url: str, status: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps({
        "event": "cao.alert.test",
        "sent_at": datetime.now(UTC).isoformat(),
        "status": status["latest_run"].get("status"),
        "run_id": status["latest_run"].get("run_id"),
    }).encode("utf-8")
    request = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=10) as response:
            return {"adapter": "webhook", "status": "DELIVERED", "status_code": response.status}
    except (OSError, URLError) as error:
        return {"adapter": "webhook", "status": "FAILED", "error": type(error).__name__}
