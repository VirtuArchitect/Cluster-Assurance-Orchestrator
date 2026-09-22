from __future__ import annotations

from pathlib import Path

from app.domain.evidence import EvidenceArtifact, EvidenceManifest
from app.services.artifacts import hash_file, public_artifact_ref
from app.services.inventory_run import read_latest_inventory_evidence


def latest_manifest(evidence_dir: str | Path) -> EvidenceManifest | None:
    latest = read_latest_inventory_evidence(evidence_dir)
    if latest is None:
        return None

    run_id = str(latest.get("run_id", "unknown-run"))
    artifacts: list[EvidenceArtifact] = []
    for collector in latest.get("collectors", []):
        raw = collector.get("raw_artifact") if isinstance(collector, dict) else None
        if not raw:
            continue
        artifacts.append(
            EvidenceArtifact(
                artifact_type="raw_collector_response",
                uri=public_artifact_ref(str(raw.get("uri", ""))) or "",
                sha256=str(raw.get("sha256", "")),
                size_bytes=int(raw.get("size_bytes", 0)),
            )
        )

    evidence_path = _latest_inventory_path(evidence_dir)
    if evidence_path is not None:
        artifacts.append(
            EvidenceArtifact(
                artifact_type="normalized_inventory_run",
                uri=public_artifact_ref(evidence_path) or "",
                sha256=hash_file(evidence_path),
                size_bytes=evidence_path.stat().st_size,
            )
        )

    return EvidenceManifest(
        product_version="0.1.0",
        profile_version="lab-inventory-v1",
        run_id=run_id,
        result_summary={
            "status": latest.get("status", "UNKNOWN"),
            "maturity": latest.get("maturity", "unknown"),
            "clusters": len(latest.get("clusters", [])),
            "collectors": len(latest.get("collectors", [])),
        },
        artifacts=artifacts,
    )


def _latest_inventory_path(evidence_dir: str | Path) -> Path | None:
    root = Path(evidence_dir)
    files = sorted(root.glob("inventory-run-*.json"), key=lambda path: path.name, reverse=True)
    return files[0] if files else None
