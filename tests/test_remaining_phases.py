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


def test_integrations_status_is_disabled_until_configured() -> None:
    client = TestClient(create_app(Settings(demo_mode=True)))
    headers = auth_headers(client)

    response = client.get("/api/v1/integrations/status", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["outbound_enabled"] is False
    assert {adapter["adapter_id"] for adapter in payload["adapters"]} == {
        "checkmk",
        "servicenow",
        "email",
        "webhook",
    }
    assert all(adapter["state"] == "PLANNED" for adapter in payload["adapters"])


def test_security_readiness_reports_open_production_gates() -> None:
    client = TestClient(
        create_app(
            Settings(
                environment="lab",
                demo_mode=False,
                tls_mode="insecure_skip_verify",
                read_only_mode=True,
            )
        )
    )
    headers = auth_headers(client)

    response = client.get("/api/v1/security/readiness", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["maturity"] == "lab validated"
    gates = {gate["gate_id"]: gate for gate in payload["gates"]}
    assert gates["tls-mode"]["status"] == "WARNING"
    assert gates["read-only"]["status"] == "PASS"
    assert gates["rbac"]["status"] == "PASS"
    assert gates["backup-restore"]["status"] == "WARNING"
    assert any(role["permission"] == "enable_integrations" and role["admin"] for role in payload["roles"])


def test_latest_manifest_includes_normalized_and_raw_artifact_hashes(tmp_path) -> None:
    raw_dir = tmp_path / "raw" / "run-1"
    raw_dir.mkdir(parents=True)
    raw_artifact = raw_dir / "collector.json"
    raw_artifact.write_text('{"ok": true}', encoding="utf-8")
    evidence_file = tmp_path / "inventory-run-20260101T000000Z.json"
    evidence_file.write_text(
        """
        {
          "run_id": "run-1",
          "status": "UNKNOWN",
          "maturity": "lab validated",
          "clusters": [{"external_id": "cluster-a"}],
          "collectors": [
            {
              "raw_artifact": {
                "uri": "raw/run-1/collector.json",
                "sha256": "abc123",
                "size_bytes": 12
              }
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    client = TestClient(create_app(Settings(demo_mode=True, evidence_dir=str(tmp_path))))
    headers = auth_headers(client)

    response = client.get("/api/v1/evidence/manifest/latest", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "run-1"
    assert payload["result_summary"]["clusters"] == 1
    assert payload["manifest_sha256"]
    artifact_types = {artifact["artifact_type"] for artifact in payload["artifacts"]}
    assert artifact_types == {"raw_collector_response", "normalized_inventory_run"}


def test_latest_manifest_404_without_inventory_evidence(tmp_path) -> None:
    client = TestClient(create_app(Settings(demo_mode=True, evidence_dir=str(tmp_path))))
    headers = auth_headers(client)

    response = client.get("/api/v1/evidence/manifest/latest", headers=headers)

    assert response.status_code == 404


def test_support_status_reports_runtime_context(tmp_path) -> None:
    evidence_file = tmp_path / "inventory-run-20260101T000000Z.json"
    evidence_file.write_text(
        '{"run_id": "run-1", "status": "UNKNOWN", "generated_at": "2026-01-01T00:00:00Z", "collectors": []}',
        encoding="utf-8",
    )
    client = TestClient(create_app(Settings(demo_mode=True, evidence_dir=str(tmp_path))))
    headers = auth_headers(client)

    response = client.get("/api/v1/support/status", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"]["demo_mode"] is True
    assert payload["latest_run"]["run_id"] == "run-1"
    assert payload["evidence_directory"] == "configured locally"
    assert "\\" not in payload["latest_run"]["path"]
    assert str(tmp_path) not in str(payload)
    assert any("Demo mode" in warning for warning in payload["warnings"])


def test_support_status_prefers_saved_connections(tmp_path) -> None:
    client = TestClient(create_app(Settings(demo_mode=True, evidence_dir=str(tmp_path), admin_db_path=str(tmp_path / "admin.sqlite3"))))
    headers = auth_headers(client)
    response = client.post(
        "/api/v1/connections",
        json={
            "name": "Prism Element Lab",
            "type": "Prism Element",
            "url": "https://192.0.2.201:9440",
            "username": "admin",
            "password": "secret",
            "tls_mode": "insecure_skip_verify",
        },
        headers=headers,
    )
    assert response.status_code == 200

    status = client.get("/api/v1/support/status", headers=headers)

    assert status.status_code == 200
    payload = status.json()
    assert payload["mode"]["demo_mode"] is False
    assert payload["config_source"] == "admin-connections"
    assert not any("Demo mode" in warning for warning in payload["warnings"])


def test_evidence_archive_and_restore_drill(tmp_path) -> None:
    (tmp_path / "inventory-run-20260101T000000Z.json").write_text('{"run_id": "run-1"}', encoding="utf-8")
    client = TestClient(create_app(Settings(demo_mode=True, evidence_dir=str(tmp_path), admin_db_path=str(tmp_path / "admin.sqlite3"))))
    headers = auth_headers(client)

    retention = client.get("/api/v1/evidence/retention", headers=headers)
    archive = client.post("/api/v1/evidence/archive/export", headers=headers)
    drill = client.post("/api/v1/evidence/restore-drill", headers=headers)

    assert retention.status_code == 200
    assert archive.status_code == 200
    assert archive.json()["sha256"]
    assert retention.json()["evidence_dir"] == "configured locally"
    assert "\\" not in archive.json()["archive_path"]
    assert str(tmp_path) not in str(retention.json())
    assert str(tmp_path) not in str(archive.json())
    assert drill.status_code == 200
    assert drill.json()["status"] == "PASS"


def test_alert_status_is_gated_until_evidence_is_trusted(tmp_path) -> None:
    client = TestClient(create_app(Settings(demo_mode=True, evidence_dir=str(tmp_path))))
    headers = auth_headers(client)

    response = client.get("/api/v1/alerts/status", headers=headers)

    assert response.status_code == 200
    assert response.json()["trustworthy_evidence"] is False
