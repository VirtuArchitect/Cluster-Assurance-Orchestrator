from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.main import create_app


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "ChangeMe123!"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def schedule_payload(schedule_id: str = "daily-smoke") -> dict[str, object]:
    return {
        "schedule_id": schedule_id,
        "name": "Daily Smoke",
        "profile": {
            "profile_id": "daily-standard",
            "name": "Daily Standard",
            "version": 1,
            "definition_hash": "a" * 64,
            "checks": ["HC-001", "HC-002"],
            "timeout_minutes": 30,
        },
        "target_cluster_ids": ["cluster-a"],
        "timezone": "UTC",
        "recurrence": "daily",
        "start_time": "07:30",
        "weekly_day": 0,
        "enabled": True,
        "misfire_policy": "run_within_grace",
        "misfire_grace_minutes": 30,
    }


def test_manual_health_run_writes_evidence_and_audit(tmp_path) -> None:
    client = TestClient(
        create_app(
            Settings(
                demo_mode=True,
                evidence_dir=str(tmp_path / "evidence"),
                admin_db_path=str(tmp_path / "admin.sqlite3"),
            )
        )
    )
    headers = auth_headers(client)

    response = client.post("/api/v1/health-runs/manual", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"HEALTHY", "WARNING", "UNKNOWN", "CRITICAL"}
    assert list((tmp_path / "evidence").glob("manual-health-run-*.json"))
    audit = client.get("/api/v1/audit/events", headers=headers).json()
    assert any(event["action"] == "health_runs.manual_started" for event in audit)


def test_schedule_crud_and_preview_are_persisted(tmp_path) -> None:
    client = TestClient(create_app(Settings(demo_mode=True, admin_db_path=str(tmp_path / "admin.sqlite3"))))
    headers = auth_headers(client)

    create_response = client.post("/api/v1/schedules", headers=headers, json=schedule_payload())
    assert create_response.status_code == 200
    assert create_response.json()["id"] == "daily-smoke"

    list_response = client.get("/api/v1/schedules", headers=headers)
    assert any(schedule["id"] == "daily-smoke" for schedule in list_response.json())

    updated = schedule_payload()
    updated["name"] = "Daily Smoke Updated"
    updated["enabled"] = False
    update_response = client.put("/api/v1/schedules/daily-smoke", headers=headers, json=updated)
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Daily Smoke Updated"
    assert update_response.json()["enabled"] is False

    preview_response = client.get("/api/v1/schedules/daily-smoke/preview", headers=headers)
    assert preview_response.status_code == 200
    assert preview_response.json()["schedule"]["name"] == "Daily Smoke Updated"

    delete_response = client.delete("/api/v1/schedules/daily-smoke", headers=headers)
    assert delete_response.status_code == 200
    after_delete = client.get("/api/v1/schedules", headers=headers).json()
    assert all(schedule["id"] != "daily-smoke" for schedule in after_delete)


def test_schedule_run_now_records_history_and_audit(tmp_path) -> None:
    client = TestClient(
        create_app(
            Settings(
                demo_mode=True,
                evidence_dir=str(tmp_path / "evidence"),
                admin_db_path=str(tmp_path / "admin.sqlite3"),
            )
        )
    )
    headers = auth_headers(client)
    create_response = client.post("/api/v1/schedules", headers=headers, json=schedule_payload("manual-smoke"))
    assert create_response.status_code == 200

    run_response = client.post("/api/v1/schedules/manual-smoke/run-now", headers=headers)
    assert run_response.status_code == 200
    assert run_response.json()["schedule_id"] == "manual-smoke"

    history_response = client.get("/api/v1/schedules/runs/history", headers=headers)
    assert history_response.status_code == 200
    assert any(row["schedule_id"] == "manual-smoke" for row in history_response.json())
    audit = client.get("/api/v1/audit/events", headers=headers).json()
    assert any(event["action"] == "schedules.run_completed" for event in audit)


def test_manual_health_run_prefers_saved_connections(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    captured = {}

    class FakeReport:
        run_id = "saved-connection-run"
        status = "HEALTHY"

        def api_dict(self):
            return {
                "run_id": self.run_id,
                "status": self.status,
                "clusters": [],
                "collectors": [],
                "observations": [],
                "warnings": [],
            }

    def fake_run_inventory(settings):  # noqa: ANN001
        captured["settings"] = settings
        return FakeReport()

    monkeypatch.setattr("app.api.routes.run_inventory", fake_run_inventory)
    client = TestClient(
        create_app(
            Settings(
                demo_mode=True,
                evidence_dir=str(tmp_path / "evidence"),
                admin_db_path=str(tmp_path / "admin.sqlite3"),
            )
        )
    )
    headers = auth_headers(client)
    client.post(
        "/api/v1/connections",
        headers=headers,
        json={
            "name": "Lab Prism Element",
            "type": "Prism Element",
            "url": "https://pe.example.local:9440/",
            "username": "admin",
            "password": "correct-password",
            "tls_mode": "insecure_skip_verify",
        },
    )

    response = client.post("/api/v1/health-runs/manual", headers=headers)

    assert response.status_code == 200
    assert response.json()["run_id"] == "saved-connection-run"
    assert captured["settings"].demo_mode is False
    assert captured["settings"].pe_url == "https://pe.example.local:9440/"
    assert captured["settings"].pe_password == "correct-password"
