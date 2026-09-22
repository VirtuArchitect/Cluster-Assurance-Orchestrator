from fastapi.testclient import TestClient
import pytest
from urllib.error import HTTPError

from app.core.config import Settings
from app.main import create_app


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "ChangeMe123!"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_login_rejects_bad_password_and_audits(tmp_path) -> None:
    client = TestClient(create_app(Settings(demo_mode=True, admin_db_path=str(tmp_path / "admin.sqlite3"))))

    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})

    assert response.status_code == 401
    headers = auth_headers(client)
    audit_response = client.get("/api/v1/audit/events", headers=headers)
    assert audit_response.status_code == 200
    assert any(event["action"] == "auth.login_failed" for event in audit_response.json())


def test_rbac_user_password_lifecycle_is_persisted_and_redacted(tmp_path) -> None:
    client = TestClient(create_app(Settings(demo_mode=True, admin_db_path=str(tmp_path / "admin.sqlite3"))))
    headers = auth_headers(client)

    create_response = client.post(
        "/api/v1/rbac/users",
        headers=headers,
        json={
            "username": "operator",
            "name": "Lab Operator",
            "email": "operator@local",
            "role_id": "operator",
            "status": "Active",
            "password": "Initial123!",
        },
    )

    assert create_response.status_code == 200
    user = create_response.json()
    assert user["password_set"] is True
    assert "password" not in user

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "operator", "password": "Initial123!"},
    )
    assert login_response.status_code == 200

    reset_response = client.post(
        f"/api/v1/rbac/users/{user['id']}/password",
        headers=headers,
        json={"password": "Changed123!"},
    )
    assert reset_response.status_code == 200

    old_login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "operator", "password": "Initial123!"},
    )
    assert old_login_response.status_code == 401
    new_login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "operator", "password": "Changed123!"},
    )
    assert new_login_response.status_code == 200


def test_connections_store_secrets_redacted_and_emit_audit(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    client = TestClient(create_app(Settings(demo_mode=True, admin_db_path=str(tmp_path / "admin.sqlite3"))))
    headers = auth_headers(client)

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

    def fake_urlopen(request, timeout, context):  # noqa: ANN001
        return FakeResponse()

    monkeypatch.setattr("app.services.admin_store.urlopen", fake_urlopen)

    create_response = client.post(
        "/api/v1/connections",
        headers=headers,
        json={
            "name": "Lab Prism Central",
            "type": "Prism Central",
            "url": "https://prism.example.local:9440/",
            "username": "admin",
            "password": "do-not-return",
            "tls_mode": "insecure_skip_verify",
        },
    )

    assert create_response.status_code == 200
    connection = create_response.json()
    assert connection["secret_set"] is True
    assert "password" not in connection
    assert "secret_ciphertext" not in connection

    test_response = client.post(f"/api/v1/connections/{connection['id']}/test", headers=headers)
    assert test_response.status_code == 200
    assert test_response.json()["status"] == "READY"

    audit_response = client.get("/api/v1/audit/events", headers=headers)
    actions = {event["action"] for event in audit_response.json()}
    assert "connections.created" in actions
    assert "connections.tested" in actions


def test_connection_test_maps_inventory_auth_failure(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    client = TestClient(create_app(Settings(demo_mode=True, admin_db_path=str(tmp_path / "admin.sqlite3"))))
    headers = auth_headers(client)

    def fake_urlopen(request, timeout, context):  # noqa: ANN001
        raise HTTPError(request.full_url, 401, "Unauthorized", hdrs=None, fp=None)

    monkeypatch.setattr("app.services.admin_store.urlopen", fake_urlopen)
    create_response = client.post(
        "/api/v1/connections",
        headers=headers,
        json={
            "name": "Lab Prism Element",
            "type": "Prism Element",
            "url": "https://pe.example.local:9440/",
            "username": "admin",
            "password": "candidate-password",
            "tls_mode": "insecure_skip_verify",
        },
    )

    test_response = client.post(f"/api/v1/connections/{create_response.json()['id']}/test", headers=headers)

    assert test_response.status_code == 200
    assert test_response.json()["status"] == "AUTH_FAILED"


def test_storage_status_redacts_locations_and_reports_sqlite_fallback(tmp_path) -> None:
    client = TestClient(create_app(Settings(demo_mode=True, evidence_dir=str(tmp_path), admin_db_path=str(tmp_path / "admin.sqlite3"))))
    headers = auth_headers(client)

    response = client.get("/api/v1/storage/status", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["backend"] == "sqlite"
    assert payload["backup_supported"] is False
    assert payload["data_directory"] == "configured locally"
    assert str(tmp_path) not in response.text


def test_storage_backup_requires_postgres_backend(tmp_path) -> None:
    client = TestClient(create_app(Settings(demo_mode=True, evidence_dir=str(tmp_path), admin_db_path=str(tmp_path / "admin.sqlite3"))))
    headers = auth_headers(client)

    response = client.post("/api/v1/storage/backups", headers=headers)

    assert response.status_code == 409
