import json

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.inventory_run import estate_entries
from app.services.support_status import build_support_status
from app.adapters.nutanix import domain_observation_status
from app.domain.status import HealthStatus


def snapshot(run_id, generated_at, status, clusters):
    return {"run_id": run_id, "generated_at": generated_at, "clusters": clusters,
            "collectors": [{"source": "prism_central", "domain": "inventory", "status": status}]}


def test_failed_source_retains_last_success_without_modifying_current_evidence(tmp_path):
    cluster = {"source": "prism_central", "external_id": "a", "collected_at": "2026-10-01T00:00:00Z"}
    old = snapshot("old", "2026-10-01T00:00:00Z", "HEALTHY", [cluster])
    (tmp_path / "inventory-run-20261001.json").write_text(json.dumps(old))
    (tmp_path / "inventory-run-20261002.json").write_text("broken JSON")
    latest = snapshot("new", "2026-10-17T00:00:00Z", "UNKNOWN", [])
    entries = estate_entries(tmp_path, latest)
    assert entries == [dict(cluster, availability="UNAVAILABLE", evidence_run_id="old")]
    assert latest["clusters"] == []
    assert entries[0]["collected_at"] == cluster["collected_at"]
    # A successful empty response and a removed source must not resurrect old entities.
    assert estate_entries(tmp_path, snapshot("empty", "2026-10-18T00:00:00Z", "HEALTHY", [])) == []
    assert estate_entries(tmp_path, {"run_id": "removed", "collectors": [], "clusters": []}) == []


def test_last_successful_empty_snapshot_stops_historical_resurrection(tmp_path):
    old = snapshot("old", "2026-10-01T00:00:00Z", "HEALTHY", [{"source": "prism_central"}])
    empty = snapshot("empty", "2026-10-02T00:00:00Z", "HEALTHY", [])
    for name, payload in [("20261001", old), ("20261002", empty)]:
        (tmp_path / f"inventory-run-{name}.json").write_text(json.dumps(payload))
    assert estate_entries(tmp_path, snapshot("new", "2026-10-17T00:00:00Z", "UNKNOWN", [])) == []


def test_readiness_uses_saved_connection_tls(tmp_path):
    settings = Settings(admin_db_path=str(tmp_path / "admin.db"), evidence_dir=str(tmp_path), tls_mode="strict")
    app = create_app(settings)
    with TestClient(app) as client:
        token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "ChangeMe123!"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post("/api/v1/connections", headers=headers, json={
            "name": "dev-pc", "type": "Prism Central", "url": "https://pc.invalid:9440",
            "username": "admin", "password": "test-only", "tls_mode": "insecure_skip_verify"})
        assert response.status_code in (200, 201)
        health = client.get("/api/v1/health").json()
        assert health["demoMode"] is False
        assert health["readOnlyMode"] is True
        report = client.get("/api/v1/security/readiness", headers=headers).json()
        tls = next(g for g in report["gates"] if g["gate_id"] == "tls-mode")
        assert tls["status"] == "WARNING"
        assert "UAT unverified" in report["maturity"]


def test_support_separates_current_tls_and_run_tls(tmp_path):
    payload = snapshot("old", "2026-10-01T00:00:00Z", "HEALTHY", [])
    payload["tls_mode"] = "insecure_skip_verify"
    (tmp_path / "inventory-run-20261001.json").write_text(json.dumps(payload))
    support = build_support_status(Settings(evidence_dir=str(tmp_path), demo_mode=False, tls_mode="strict"), "http://test")
    assert support["mode"]["tls_mode"] == "strict"
    assert support["latest_run"]["tls_mode"] == "insecure_skip_verify"
    assert any("Latest run bypassed" in warning for warning in support["warnings"])


def test_unknown_collection_is_not_relabelled_warning():
    assert domain_observation_status(HealthStatus.UNKNOWN) == HealthStatus.UNKNOWN
