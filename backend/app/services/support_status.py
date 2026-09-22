from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.services.artifacts import public_artifact_ref


def build_support_status(settings: Settings, api_url: str) -> dict[str, Any]:
    latest = latest_run_summary(settings.evidence_dir)
    return {
        "mode": {
            "environment": settings.environment,
            "demo_mode": settings.demo_mode,
            "read_only_mode": settings.read_only_mode,
            "ncc_enabled": settings.enable_ncc,
            "ssh_enabled": settings.enable_ssh,
            "tls_mode": settings.tls_mode,
        },
        "api_url": api_url,
        "config_source": settings.config_source,
        "evidence_directory": "configured locally",
        "admin_database": "configured locally",
        "latest_run": latest,
        "collector_failures": latest.get("collector_failures", []),
        "warnings": runtime_warnings(settings, latest),
    }


def latest_run_summary(evidence_dir: str | Path) -> dict[str, Any]:
    root = Path(evidence_dir)
    candidates = sorted(
        [*root.glob("inventory-run-*.json"), *root.glob("manual-health-run-*.json")],
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )
    if not candidates:
        return {
            "available": False,
            "run_id": None,
            "run_type": None,
            "status": "UNKNOWN",
            "generated_at": None,
            "age_seconds": None,
            "collector_failures": [],
        }

    path = candidates[0]
    payload = json.loads(path.read_text(encoding="utf-8"))
    generated_at = str(payload.get("generated_at") or "")
    parsed_generated_at = parse_timestamp(generated_at)
    collector_failures = [
        {
            "source": collector.get("source"),
            "endpoint_alias": collector.get("endpoint_alias"),
            "domain": collector.get("domain", "inventory"),
            "status": collector.get("status"),
            "status_code": collector.get("status_code"),
            "summary": collector.get("summary"),
        }
        for collector in payload.get("collectors", [])
        if isinstance(collector, dict) and collector.get("status") != "HEALTHY"
    ]
    return {
        "available": True,
        "run_id": payload.get("run_id"),
        "run_type": "manual-demo" if path.name.startswith("manual-health-run-") else "inventory",
        "status": payload.get("status", "UNKNOWN"),
        "generated_at": generated_at or None,
        "age_seconds": int((datetime.now(UTC) - parsed_generated_at).total_seconds()) if parsed_generated_at else None,
        "path": public_artifact_ref(path),
        "collector_failures": collector_failures,
    }


def parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC)


def runtime_warnings(settings: Settings, latest: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if settings.demo_mode:
        warnings.append("Demo mode is active. Manual health checks use synthetic data and do not contact Prism.")
    if settings.tls_mode == "insecure_skip_verify":
        warnings.append("TLS verification is disabled. Evidence is lab-only and not production approval evidence.")
    if latest.get("available") and latest.get("age_seconds") is not None and latest["age_seconds"] > 24 * 60 * 60:
        warnings.append("Latest health evidence is older than 24 hours.")
    if latest.get("collector_failures"):
        warnings.append("One or more mandatory collectors failed or returned UNKNOWN.")
    return warnings
