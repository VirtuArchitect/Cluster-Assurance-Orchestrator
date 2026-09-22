from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import zipfile
from typing import Any

from app.core.config import Settings
from app.services.artifacts import hash_file


def retention_report(settings: Settings) -> dict[str, Any]:
    files = inventory_evidence_files(settings.evidence_dir)
    cutoff = datetime.now(UTC) - timedelta(days=settings.evidence_retention_days)
    deletable = retention_candidates(files, cutoff, settings.evidence_retention_min_runs)
    return {
        "policy": {
            "retention_days": settings.evidence_retention_days,
            "minimum_runs": settings.evidence_retention_min_runs,
        },
        "evidence_dir": str(Path(settings.evidence_dir).resolve()),
        "inventory_runs": len(files),
        "deletable_runs": len(deletable),
        "deletable_files": [str(path) for path in deletable],
    }


def prune_evidence(settings: Settings) -> dict[str, Any]:
    files = inventory_evidence_files(settings.evidence_dir)
    cutoff = datetime.now(UTC) - timedelta(days=settings.evidence_retention_days)
    deletable = retention_candidates(files, cutoff, settings.evidence_retention_min_runs)
    deleted: list[str] = []
    for path in deletable:
        path.unlink(missing_ok=True)
        deleted.append(str(path))
    return retention_report(settings) | {"deleted_files": deleted}


def create_evidence_archive(settings: Settings) -> dict[str, Any]:
    root = Path(settings.evidence_dir)
    root.mkdir(parents=True, exist_ok=True)
    archive_dir = root / "archives"
    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archive_path = archive_dir / f"cao-evidence-{timestamp}.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in root.rglob("*"):
            if path.is_file() and archive_path not in path.parents and path != archive_path:
                archive.write(path, path.relative_to(root))
    return {
        "archive_path": str(archive_path),
        "sha256": hash_file(archive_path),
        "size_bytes": archive_path.stat().st_size,
    }


def restore_drill(settings: Settings) -> dict[str, Any]:
    root = Path(settings.evidence_dir)
    archives = sorted((root / "archives").glob("cao-evidence-*.zip"), reverse=True)
    archive_payload = create_evidence_archive(settings) if not archives else {
        "archive_path": str(archives[0]),
        "sha256": hash_file(archives[0]),
        "size_bytes": archives[0].stat().st_size,
    }
    archive_path = Path(archive_payload["archive_path"])
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        invalid_json = [
            name
            for name in names
            if should_validate_json(name) and not can_parse_json(archive.read(name))
        ]
    return {
        **archive_payload,
        "checked_at": datetime.now(UTC).isoformat(),
        "artifact_count": len(names),
        "json_parse_failures": invalid_json,
        "status": "PASS" if not invalid_json else "FAIL",
    }


def inventory_evidence_files(evidence_dir: str | Path) -> list[Path]:
    root = Path(evidence_dir)
    return sorted(root.glob("inventory-run-*.json"), key=lambda path: path.stat().st_mtime, reverse=True)


def retention_candidates(files: list[Path], cutoff: datetime, minimum_runs: int) -> list[Path]:
    keep = set(files[:minimum_runs])
    return [
        path for path in files
        if path not in keep and datetime.fromtimestamp(path.stat().st_mtime, UTC) < cutoff
    ]


def can_parse_json(data: bytes) -> bool:
    try:
        json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return True


def should_validate_json(name: str) -> bool:
    path = Path(name)
    if len(path.parts) > 1 and path.parts[0] == "raw":
        return False
    return path.name.startswith(("inventory-run-", "manual-health-run-", "lab-discovery-"))
