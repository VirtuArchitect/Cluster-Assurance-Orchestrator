from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path

from app.adapters.nutanix import NutanixReadOnlyAdapter
from app.core.config import Settings
from app.domain.discovery import LabDiscoveryReport


def run_lab_discovery(settings: Settings) -> LabDiscoveryReport:
    adapter = NutanixReadOnlyAdapter(settings)
    report = adapter.discover()
    return report


def write_discovery_evidence(report: LabDiscoveryReport, evidence_dir: str | Path) -> Path:
    target_dir = Path(evidence_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = target_dir / f"lab-discovery-{timestamp}.json"
    target.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return target


def hash_file(path: str | Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()

