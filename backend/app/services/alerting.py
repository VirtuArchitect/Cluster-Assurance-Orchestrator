from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.services.support_status import latest_run_summary


def alert_status(settings: Settings) -> dict[str, Any]:
    latest = latest_run_summary(settings.evidence_dir)
    trustworthy = evidence_is_trustworthy(settings, latest)
    return {
        "enabled": settings.enable_alerts,
        "trustworthy_evidence": trustworthy,
        "email": {
            "configured": bool(settings.alert_email_to and settings.smtp_host and settings.smtp_from),
            "target": settings.alert_email_to,
            "state": "READY" if settings.enable_alerts and settings.alert_email_to and settings.smtp_host and settings.smtp_from and trustworthy else "GATED",
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
    from app.services.monitoring_control import transition
    from uuid import uuid4
    from app.services.monitoring_control import channels
    if not channels(settings): return status | {"delivery":"SKIPPED_NO_DESTINATION"}
    transition(settings, "test:"+str(uuid4()), "TEST", {"kind":"test", "severity":"INFO", "summary":"Explicit administrator delivery test"})
    return status | {"delivery": "QUEUED"}


def evidence_is_trustworthy(settings: Settings, latest: dict[str, Any]) -> bool:
    age = latest.get("age_seconds")
    return (bool(latest.get("available")) and not settings.demo_mode and settings.tls_mode == "strict"
            and latest.get("tls_mode") == "strict" and isinstance(age, (int, float)) and 0 <= age <= 120
            and latest.get("collector_count", 0) > 0 and latest.get("collector_failure_count") == 0)


def alert_gate_reason(settings: Settings, latest: dict[str, Any], trustworthy: bool) -> str:
    if not settings.enable_alerts:
        return "Alert delivery is disabled by CAO_ENABLE_ALERTS."
    if not latest.get("available"):
        return "No health evidence is available."
    if not trustworthy:
        return "Evidence is not yet trusted for outbound alerting."
    from app.services.monitoring_control import channels
    return "Durable alert delivery configured; receiver acceptance is not human acknowledgement." if channels(settings) else "No complete email or webhook destination is configured."
