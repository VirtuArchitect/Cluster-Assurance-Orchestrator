import json
import os
from pathlib import Path
import subprocess
import sys

from app.services.evidence_schema import format_schema_report, inspect_latest_evidence_schema


def test_evidence_schema_inspector_summarizes_raw_artifact_shapes(tmp_path) -> None:
    raw_dir = tmp_path / "raw" / "run-1"
    raw_dir.mkdir(parents=True)
    raw = raw_dir / "prism-central-storage-abcd.json"
    raw.write_text(
        json.dumps(
            {
                "entities": [
                    {
                        "metadata": {"uuid": "container-1"},
                        "status": {
                            "state": "COMPLETE",
                            "resources": {
                                "usage_stats": {
                                    "storage.capacity_bytes": 1000,
                                    "storage.usage_bytes": 400,
                                }
                            },
                        },
                    }
                ],
                "metadata": {"total_matches": 1},
            }
        ),
        encoding="utf-8",
    )
    evidence = tmp_path / "inventory-run-20260101T000000Z.json"
    evidence.write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "generated_at": "2026-01-01T00:00:00Z",
                "status": "HEALTHY",
                "collectors": [
                    {
                        "endpoint_alias": "prism-central",
                        "source": "prism_central",
                        "domain": "storage",
                        "status": "HEALTHY",
                        "status_code": 200,
                        "method": "POST",
                        "path": "/api/nutanix/v3/storage_containers/list",
                        "summary": "storage collector captured 1 record.",
                        "raw_artifact": {
                            "uri": str(raw),
                            "sha256": "abc",
                            "size_bytes": raw.stat().st_size,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = inspect_latest_evidence_schema(tmp_path)

    assert report["run_id"] == "run-1"
    collector = report["collectors"][0]
    assert collector["domain"] == "storage"
    assert collector["entity_path"] == "entities"
    assert collector["entity_count"] == 1
    assert "metadata" in collector["common_entity_keys"]
    assert any("status.state" in field for field in collector["candidate_health_fields"])
    assert any("capacity_bytes" in field for field in collector["candidate_capacity_fields"])
    assert "storage collector captured" not in format_schema_report(report)


def test_evidence_schema_cli_emits_json_for_specific_file(tmp_path) -> None:
    raw = tmp_path / "raw.json"
    raw.write_text('{"entities": [{"status": {"state": "COMPLETE"}}]}', encoding="utf-8")
    evidence = tmp_path / "inventory-run-20260101T000000Z.json"
    evidence.write_text(
        json.dumps(
            {
                "run_id": "run-cli",
                "collectors": [
                    {
                        "endpoint_alias": "prism-central",
                        "source": "prism_central",
                        "domain": "hardware",
                        "status": "HEALTHY",
                        "status_code": 200,
                        "method": "POST",
                        "path": "/api/nutanix/v3/hosts/list",
                        "raw_artifact": {"uri": str(raw), "sha256": "abc", "size_bytes": raw.stat().st_size},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.cli.inspect_evidence_schema",
            "--evidence-file",
            str(evidence),
            "--json",
        ],
        check=True,
        capture_output=True,
        env=os.environ | {"PYTHONPATH": str(Path.cwd() / "backend")},
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["run_id"] == "run-cli"
    assert payload["collectors"][0]["domain"] == "hardware"
