from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "ChangeMe123!"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_lab_discovery_endpoint_returns_conflict_in_demo_mode() -> None:
    client = TestClient(create_app(Settings(demo_mode=True)))
    headers = auth_headers(client)

    response = client.post("/api/v1/lab/discovery", headers=headers)

    assert response.status_code == 409
    assert "demo mode" in response.json()["detail"]


def test_lab_inventory_endpoint_returns_conflict_in_demo_mode(tmp_path) -> None:
    client = TestClient(create_app(Settings(demo_mode=True, admin_db_path=str(tmp_path / "admin.sqlite3"))))
    headers = auth_headers(client)

    response = client.post("/api/v1/lab/inventory-runs", headers=headers)

    assert response.status_code == 409
    assert "demo mode" in response.json()["detail"]


def test_latest_inventory_endpoint_reads_local_evidence(tmp_path) -> None:
    evidence_file = tmp_path / "inventory-run-20260101T000000Z.json"
    evidence_file.write_text('{"status": "UNKNOWN", "clusters": []}', encoding="utf-8")
    client = TestClient(create_app(Settings(demo_mode=True, evidence_dir=str(tmp_path))))
    headers = auth_headers(client)

    response = client.get("/api/v1/lab/inventory-runs/latest", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "UNKNOWN"


def test_latest_inventory_endpoint_404_without_evidence(tmp_path) -> None:
    client = TestClient(create_app(Settings(demo_mode=True, evidence_dir=str(tmp_path))))
    headers = auth_headers(client)

    response = client.get("/api/v1/lab/inventory-runs/latest", headers=headers)

    assert response.status_code == 404


def test_health_run_history_summarizes_recent_evidence(tmp_path) -> None:
    (tmp_path / "inventory-run-20260101T000000Z.json").write_text(
        """
        {
          "run_id": "run-1",
          "status": "WARNING",
          "generated_at": "2026-01-01T00:00:00Z",
          "clusters": [{"external_id": "cluster-a"}],
          "collectors": [
            {"source": "prism_element", "endpoint_alias": "pe", "status": "UNKNOWN", "status_code": 401, "summary": "auth failed"}
          ],
          "warnings": ["lab only"]
        }
        """,
        encoding="utf-8",
    )
    client = TestClient(create_app(Settings(demo_mode=True, evidence_dir=str(tmp_path))))
    headers = auth_headers(client)

    response = client.get("/api/v1/health-runs/history", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["run_id"] == "run-1"
    assert payload[0]["cluster_count"] == 1
    assert payload[0]["collector_failure_count"] == 1
    assert payload[0]["collector_failures"][0]["status_code"] == 401
    assert payload[0]["path"] == "inventory-run-20260101T000000Z.json"
    assert str(tmp_path) not in str(payload)


def test_default_schedule_preview_uses_latest_inventory_targets(tmp_path) -> None:
    evidence_file = tmp_path / "inventory-run-20260101T000000Z.json"
    evidence_file.write_text(
        '{"status": "UNKNOWN", "clusters": [{"external_id": "cluster-a"}]}',
        encoding="utf-8",
    )
    client = TestClient(create_app(Settings(demo_mode=True, evidence_dir=str(tmp_path))))
    headers = auth_headers(client)

    response = client.get("/api/v1/schedules/preview/default", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["schedule"]["target_cluster_ids"] == ["cluster-a"]
    assert payload["occurrences"][0]["blocked_cluster_ids"] == ["cluster-a"]


def test_schedule_preview_endpoint_accepts_explicit_schedule() -> None:
    client = TestClient(create_app(Settings(demo_mode=True)))
    headers = auth_headers(client)
    payload = {
        "schedule_id": "manual",
        "name": "Manual Preview",
        "profile": {
            "profile_id": "daily-standard",
            "name": "Daily Standard",
            "version": 1,
            "definition_hash": "a" * 64,
            "checks": ["HC-001"],
            "timeout_minutes": 30,
        },
        "target_cluster_ids": ["cluster-a"],
        "timezone": "UTC",
        "recurrence": "daily",
        "start_time": "06:00",
        "enabled": True,
    }

    response = client.post("/api/v1/schedules/preview", headers=headers, json=payload)

    assert response.status_code == 200
    assert response.json()["occurrences"][0]["status"] == "ready"


def test_ncc_profiles_endpoint_lists_allowlist() -> None:
    client = TestClient(create_app(Settings(demo_mode=True)))
    headers = auth_headers(client)

    response = client.get("/api/v1/ncc/profiles", headers=headers)

    assert response.status_code == 200
    assert response.json()["profiles"][0]["profile_id"] == "full-run-all"


def test_catalogue_endpoint_returns_expanded_operational_checks() -> None:
    client = TestClient(create_app(Settings(demo_mode=True)))
    headers = auth_headers(client)

    response = client.get("/api/v1/catalogue", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    checks = payload["checks"]
    domains = {check["domain"] for check in checks}
    assert payload["version"] == "2026.09.assurance-expanded"
    assert len(checks) >= 40
    assert {"Storage", "Network", "Capacity", "Data Protection", "Security / Governance", "Operations"}.issubset(domains)
    assert all(check["evidence_artifact"] for check in checks)
    assert all(check["remediation_hint"] for check in checks)
    assert all(check["production_gate_impact"] for check in checks)


def test_ncc_plan_rejects_command_text_as_profile() -> None:
    client = TestClient(create_app(Settings(demo_mode=True)))
    headers = auth_headers(client)

    response = client.post(
        "/api/v1/ncc/plan",
        headers=headers,
        json={"profile_id": "ncc health_checks run_all", "cluster_id": "cluster-a"},
    )

    assert response.status_code == 400


def test_ncc_parse_endpoint_unknown_output_is_unknown() -> None:
    client = TestClient(create_app(Settings(demo_mode=True)))
    headers = auth_headers(client)

    response = client.post("/api/v1/ncc/parse", headers=headers, json={"output": "unrecognized"})

    assert response.status_code == 200
    assert response.json()["status"] == "UNKNOWN"
