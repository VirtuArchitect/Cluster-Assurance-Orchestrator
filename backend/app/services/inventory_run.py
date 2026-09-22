from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from uuid import uuid4

from app.adapters.nutanix import NutanixReadOnlyAdapter
from app.core.config import Settings
from app.domain.inventory import InventoryRunReport
from app.services.artifacts import hash_file


def run_inventory(settings: Settings) -> InventoryRunReport:
    adapter = NutanixReadOnlyAdapter(settings)
    return adapter.collect_inventory(run_id=str(uuid4()))


def write_inventory_evidence(report: InventoryRunReport, evidence_dir: str | Path) -> Path:
    target_dir = Path(evidence_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = target_dir / f"inventory-run-{timestamp}.json"
    target.write_text(
        json.dumps(report.api_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return target


def read_latest_inventory_evidence(evidence_dir: str | Path) -> dict[str, object] | None:
    target_dir = Path(evidence_dir)
    candidates = sorted(
        target_dir.glob("inventory-run-*.json"),
        key=lambda path: path.name,
        reverse=True,
    )
    if not candidates:
        return None
    return json.loads(candidates[0].read_text(encoding="utf-8"))


def inventory_run_history(evidence_dir: str | Path, limit: int = 20) -> list[dict[str, object]]:
    target_dir = Path(evidence_dir)
    candidates = sorted(
        [*target_dir.glob("inventory-run-*.json"), *target_dir.glob("manual-health-run-*.json")],
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )[:limit]
    history: list[dict[str, object]] = []
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        generated_at = str(payload.get("generated_at") or "")
        parsed_generated_at = _parse_timestamp(generated_at)
        collectors = [collector for collector in payload.get("collectors", []) if isinstance(collector, dict)]
        failures = [
            {
                "source": collector.get("source"),
                "endpoint_alias": collector.get("endpoint_alias"),
                "status": collector.get("status"),
                "status_code": collector.get("status_code"),
                "summary": collector.get("summary"),
            }
            for collector in collectors
            if collector.get("status") != "HEALTHY"
        ]
        history.append(
            {
                "run_id": payload.get("run_id"),
                "run_type": "manual-demo" if path.name.startswith("manual-health-run-") else "inventory",
                "status": payload.get("status", "UNKNOWN"),
                "generated_at": generated_at or None,
                "age_seconds": int((datetime.now(UTC) - parsed_generated_at).total_seconds()) if parsed_generated_at else None,
                "path": str(path),
                "cluster_count": len(payload.get("clusters", [])) if isinstance(payload.get("clusters"), list) else 0,
                "collector_count": len(collectors),
                "collector_failure_count": len(failures),
                "collector_failures": failures,
                "warnings": payload.get("warnings", []) if isinstance(payload.get("warnings"), list) else [],
            }
        )
    return history


def _parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC)
