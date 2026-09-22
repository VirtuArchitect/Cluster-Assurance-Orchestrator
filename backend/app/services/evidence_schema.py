from __future__ import annotations

import json
from pathlib import Path
from typing import Any


HEALTH_HINTS = ("health", "status", "state", "alert", "fault", "error", "critical", "warning")
CAPACITY_HINTS = (
    "capacity",
    "usage",
    "used",
    "free",
    "available",
    "bytes",
    "memory",
    "cpu",
    "storage",
    "iops",
)


def inspect_latest_evidence_schema(evidence_dir: str | Path) -> dict[str, Any]:
    evidence_path = latest_evidence_path(evidence_dir)
    if evidence_path is None:
        raise FileNotFoundError(f"No inventory-run evidence found in {evidence_dir}")
    return inspect_evidence_schema(evidence_path)


def inspect_evidence_schema(evidence_path: str | Path) -> dict[str, Any]:
    path = Path(evidence_path)
    evidence = json.loads(path.read_text(encoding="utf-8"))
    collectors = [collector for collector in evidence.get("collectors", []) if isinstance(collector, dict)]
    summaries = []
    for collector in collectors:
        raw = collector.get("raw_artifact") if isinstance(collector.get("raw_artifact"), dict) else None
        summaries.append(_inspect_collector(collector, raw))

    return {
        "evidence_path": str(path),
        "run_id": evidence.get("run_id"),
        "generated_at": evidence.get("generated_at"),
        "status": evidence.get("status", "UNKNOWN"),
        "collector_count": len(collectors),
        "collectors": summaries,
    }


def latest_evidence_path(evidence_dir: str | Path) -> Path | None:
    root = Path(evidence_dir)
    candidates = sorted(
        [*root.glob("inventory-run-*.json"), *root.glob("manual-health-run-*.json")],
        key=lambda candidate: candidate.stat().st_mtime if candidate.exists() else 0,
        reverse=True,
    )
    return candidates[0] if candidates else None


def format_schema_report(report: dict[str, Any]) -> str:
    lines = [
        f"Evidence: {report['evidence_path']}",
        f"Run: {report.get('run_id') or '-'}",
        f"Generated: {report.get('generated_at') or '-'}",
        f"Status: {report.get('status') or 'UNKNOWN'}",
        f"Collectors: {report.get('collector_count', 0)}",
        "",
    ]
    for collector in report.get("collectors", []):
        lines.extend(
            [
                f"{collector.get('domain', 'inventory')} / {collector.get('endpoint_alias', '-')}",
                f"  route: {collector.get('method', '-')} {collector.get('path', '-')}",
                f"  status: {collector.get('status', '-')} / HTTP {collector.get('status_code') or '-'}",
                f"  raw artifact: {collector.get('artifact_uri') or '-'}",
                f"  entity path: {collector.get('entity_path') or '-'}",
                f"  entity count: {collector.get('entity_count')}",
                f"  top-level keys: {', '.join(collector.get('top_level_keys', [])) or '-'}",
                f"  common entity keys: {', '.join(collector.get('common_entity_keys', [])) or '-'}",
                f"  candidate health fields: {', '.join(collector.get('candidate_health_fields', [])) or '-'}",
                f"  candidate capacity fields: {', '.join(collector.get('candidate_capacity_fields', [])) or '-'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _inspect_collector(collector: dict[str, Any], raw: dict[str, Any] | None) -> dict[str, Any]:
    base = {
        "endpoint_alias": collector.get("endpoint_alias"),
        "source": collector.get("source"),
        "domain": collector.get("domain", "inventory"),
        "status": collector.get("status"),
        "status_code": collector.get("status_code"),
        "method": collector.get("method"),
        "path": collector.get("path"),
        "summary": collector.get("summary"),
        "artifact_uri": raw.get("uri") if raw else None,
        "artifact_sha256": raw.get("sha256") if raw else None,
        "artifact_size_bytes": raw.get("size_bytes") if raw else None,
    }
    if not raw or not raw.get("uri"):
        return base | {
            "parse_status": "missing_raw_artifact",
            "top_level_keys": [],
            "entity_path": None,
            "entity_count": 0,
            "common_entity_keys": [],
            "candidate_health_fields": [],
            "candidate_capacity_fields": [],
        }

    try:
        payload = json.loads(Path(str(raw["uri"])).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return base | {
            "parse_status": type(error).__name__,
            "top_level_keys": [],
            "entity_path": None,
            "entity_count": 0,
            "common_entity_keys": [],
            "candidate_health_fields": [],
            "candidate_capacity_fields": [],
        }

    entities, entity_path = _entity_collection(payload)
    field_paths = sorted(_field_paths(payload))
    return base | {
        "parse_status": "ok",
        "top_level_keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
        "entity_path": entity_path,
        "entity_count": len(entities),
        "common_entity_keys": _common_entity_keys(entities),
        "candidate_health_fields": _candidate_fields(field_paths, HEALTH_HINTS),
        "candidate_capacity_fields": _candidate_fields(field_paths, CAPACITY_HINTS),
        "sample_field_paths": field_paths[:80],
    }


def _entity_collection(payload: Any) -> tuple[list[Any], str | None]:
    if isinstance(payload, list):
        return payload, "$"
    if not isinstance(payload, dict):
        return [], None
    for key in ("entities", "storage_containers", "hosts", "networks", "subnets", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return value, key
    return [payload], "$"


def _common_entity_keys(entities: list[Any]) -> list[str]:
    dict_entities = [entity for entity in entities if isinstance(entity, dict)]
    if not dict_entities:
        return []
    common = set(dict_entities[0].keys())
    for entity in dict_entities[1:]:
        common &= set(entity.keys())
    return sorted(common)


def _field_paths(value: Any, prefix: str = "", depth: int = 0) -> set[str]:
    if depth > 5:
        return set()
    if isinstance(value, dict):
        paths: set[str] = set()
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            paths.add(f"{child_prefix}:{_type_name(child)}")
            paths |= _field_paths(child, child_prefix, depth + 1)
        return paths
    if isinstance(value, list):
        sample_paths: set[str] = {f"{prefix}[]:{_type_name(value)}"} if prefix else set()
        for item in value[:3]:
            sample_paths |= _field_paths(item, f"{prefix}[]", depth + 1)
        return sample_paths
    return set()


def _candidate_fields(field_paths: list[str], hints: tuple[str, ...]) -> list[str]:
    candidates = [
        field_path
        for field_path in field_paths
        if any(hint in field_path.lower() for hint in hints)
    ]
    return candidates[:24]


def _type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    if value is None:
        return "null"
    return type(value).__name__
