from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.adapters.nutanix import AdapterDisabledError, HttpResponse, NutanixReadOnlyAdapter
from app.core.config import Settings
from app.main import create_app
from app.services.admin_store import AdminStore
from app.services.monitoring import collect_monitoring, latest_monitoring, triage_for, render_vendor_text, normalize_record, COLLECTION_LOCK
from app.services.scheduling import default_profile, default_schedule_for_latest_inventory
from app.domain.scheduling import ScheduleDefinition


def alert(identity="alert-1", **updates):
    return {"id": identity, "severity": "kCritical", "resolved": False, "acknowledged": False,
            "alert_title": "CVM service unavailable", "message": "Service failure; refer to KB-1234",
            "cluster_uuid": "cluster-a", "created_time_stamp_in_usecs": 1_700_000_000_000_000,
            "affected_entities": [{"uuid": "node-a", "entity_name": "Node A", "entity_type": "node"}], **updates}


def response(items, total=None):
    return HttpResponse(status_code=200, elapsed_ms=2, body=json.dumps({"entities": items,
        "metadata": {"total_entities": len(items) if total is None else total}}).encode())


def settings(tmp_path):
    return Settings(demo_mode=False, pc_url="https://pc.invalid:9440", pe_url="https://pe.invalid:9440",
                    pc_username="admin", pe_username="admin", pc_password="test_secret", pe_password="test_secret",
                    evidence_dir=str(tmp_path), admin_db_path=str(tmp_path / "admin.sqlite3"))


def test_monitoring_preserves_source_identity_evidence_and_event_context(monkeypatch, tmp_path):
    calls = []
    def request(self, endpoint, method, path, body=None):
        calls.append((method, path, body))
        return response([alert()] if "/alerts/" in path else [alert("event-1", severity="kAudit", resolved=True)])
    monkeypatch.setattr(NutanixReadOnlyAdapter, "_request", request)
    report = collect_monitoring(settings(tmp_path))
    assert report["status"] == "COLLECTED"
    assert report["summary"]["critical"] == 2
    assert len({item["id"] for item in report["incidents"]}) == 2  # PE/PC source identities retained
    assert len(report["events"]) == 2
    incident = report["incidents"][0]
    assert incident["lifecycle"] == "OPEN"
    assert incident["related_events"]
    assert incident["triage"]["category"] == "Services and availability"
    assert incident["triage"]["kb_links"] == ["https://portal.nutanix.com/kb/1234"]
    assert all(method == "GET" and body is None for method, _, body in calls)
    assert all("/alerts/?" in path or "/events/?" in path for _, path, _ in calls)
    for collector in report["collectors"]:
        page = collector["pages"][0]
        path = tmp_path / "raw" / report["run_id"] / page["artifact"]
        assert sha256(path.read_bytes()).hexdigest() == page["sha256"]
    assert "test_secret" not in json.dumps(report)
    assert latest_monitoring(tmp_path)["run_id"] == report["run_id"]


def test_lifecycle_is_explicit_and_failed_or_missing_sources_do_not_resolve(monkeypatch, tmp_path):
    mode = ["open"]
    def request(self, endpoint, method, path, body=None):
        if "/events/" in path:
            return response([])
        if mode[0] == "failure":
            return HttpResponse(status_code=401, body=b'{"error":"Unauthorized"}')
        if mode[0] == "absent":
            return response([])
        return response([alert(acknowledged=mode[0] == "ack", resolved=mode[0] == "resolved")])
    monkeypatch.setattr(NutanixReadOnlyAdapter, "_request", request)
    config = settings(tmp_path)
    first = collect_monitoring(config)
    mode[0] = "failure"
    failed = collect_monitoring(config)
    assert failed["status"] == "UNKNOWN"
    assert all(i["availability"] == "UNAVAILABLE" and i["resolved"] is False for i in failed["incidents"])
    assert failed["incidents"][0]["observed_at"] == first["incidents"][0]["observed_at"]
    mode[0] = "absent"
    missing = collect_monitoring(config)
    assert all(i["availability"] == "NOT_OBSERVED" and i["resolved"] is False for i in missing["incidents"])
    mode[0] = "ack"
    ack = collect_monitoring(config)
    assert all(i["lifecycle"] == "ACKNOWLEDGED" and i["resolved"] is False for i in ack["incidents"])
    mode[0] = "resolved"
    resolved = collect_monitoring(config)
    assert all(i["lifecycle"] == "RESOLVED_IN_PRISM" for i in resolved["incidents"])
    assert resolved["summary"]["open"] == 0
    assert len(resolved["incidents"][0]["history"]) == 5


@pytest.mark.parametrize("bad", ["repeated", "missing", "error", "malformed", "no_resolution"])
def test_incomplete_or_error_envelopes_never_become_clear_health(monkeypatch, tmp_path, bad):
    def request(self, endpoint, method, path, body=None):
        if bad == "malformed": return HttpResponse(status_code=200, body=b"not json")
        if bad == "error": return HttpResponse(status_code=200, body=b'{"error_info":{"count":1},"entities":[],"metadata":{"total_entities":0}}')
        if bad == "missing": return response([{"severity": "kCritical"}])
        if bad == "no_resolution": return response([{"id":"a", "severity":"kCritical"}])
        return response([alert()], total=2)  # second page repeats the same ID
    monkeypatch.setattr(NutanixReadOnlyAdapter, "_request", request)
    report = collect_monitoring(settings(tmp_path))
    assert report["status"] == "UNKNOWN"
    assert not any(c["complete"] for c in report["collectors"] if c["kind"] == "alerts")


def test_pagination_collects_all_pages(monkeypatch, tmp_path):
    def request(self, endpoint, method, path, body=None):
        return response([alert("a" if "page=1" in path else "b")], total=2)
    monkeypatch.setattr(NutanixReadOnlyAdapter, "_request", request)
    result = collect_monitoring(settings(tmp_path))
    assert result["status"] == "COLLECTED"
    assert all(len(c["pages"]) == 2 and c["count"] == 2 for c in result["collectors"])


def test_demo_and_concurrent_collection_are_gated(tmp_path):
    with pytest.raises(AdapterDisabledError): collect_monitoring(Settings(evidence_dir=str(tmp_path)))
    COLLECTION_LOCK.acquire()
    try:
        with pytest.raises(RuntimeError, match="already running"): collect_monitoring(settings(tmp_path))
    finally:
        COLLECTION_LOCK.release()


def test_monitoring_endpoints_require_auth_and_viewers_cannot_collect(tmp_path, monkeypatch):
    client = TestClient(create_app(settings(tmp_path)))
    assert client.get("/api/v1/monitoring/latest").status_code == 401
    assert client.post("/api/v1/monitoring/collect").status_code == 401
    def auth(username, password):
        token = client.post("/api/v1/auth/login", json={"username": username, "password": password}).json()["token"]
        return {"Authorization": f"Bearer {token}"}
    admin = auth("admin", "ChangeMe123!")
    client.post("/api/v1/rbac/users", headers=admin, json={"username":"reader", "name":"Reader", "email":"reader@local", "role_id":"viewer", "password":"test-reader"})
    viewer = auth("reader", "test-reader")
    assert client.get("/api/v1/monitoring/latest", headers=viewer).status_code == 200
    assert client.post("/api/v1/monitoring/collect", headers=viewer).status_code == 403
    monkeypatch.setattr(NutanixReadOnlyAdapter, "_request", lambda *args, **kwargs: response([alert()]))
    collected = client.post("/api/v1/monitoring/collect", headers=admin)
    assert collected.status_code == 200
    identity = collected.json()["incidents"][0]["id"]
    assert client.get(f"/api/v1/monitoring/incidents/{identity}", headers=viewer).json()["incident"]["source_id"] == "alert-1"
    assert client.get("/api/v1/monitoring/incidents/missing", headers=viewer).status_code == 404


def test_previews_use_real_locks_and_unique_inventory_targets(tmp_path):
    (tmp_path / "inventory-run-20261017.json").write_text(json.dumps({"clusters": [{"external_id":"cluster-a"}, {"external_id":"cluster-a"}]}))
    preview = default_schedule_for_latest_inventory(str(tmp_path))
    assert preview.schedule.target_cluster_ids == ["cluster-a"]
    assert preview.active_locks == []
    assert all(not occurrence.blocked_cluster_ids for occurrence in preview.occurrences)
    config = settings(tmp_path)
    app = create_app(config)
    with TestClient(app) as client:
        token = client.post("/api/v1/auth/login", json={"username":"admin","password":"ChangeMe123!"}).json()["token"]
        store = app.state.admin_store
        actor = store.principal_from_token(token)
        schedule = ScheduleDefinition(schedule_id="real", name="Real", profile=default_profile(), target_cluster_ids=["cluster-a"], recurrence="daily", start_time="06:00")
        store.upsert_schedule(schedule, actor)
        store.acquire_schedule_locks(owner_run_id="real-running-run", target_cluster_ids=["cluster-a"], expires_at=(datetime.now(UTC)+timedelta(days=3)).isoformat())
        result = client.get("/api/v1/schedules/real/preview", headers={"Authorization":f"Bearer {token}"}).json()
        assert result["active_locks"][0]["owner_run_id"] == "real-running-run"
        assert result["occurrences"][0]["blocked_cluster_ids"] == ["cluster-a"]


def test_vendor_parameters_and_diagnostic_context_are_rendered_without_evaluation():
    record = alert(message="{vm_type} {ip_address} rebooted at {missing}", context_types=["vm_type", "ip_address", "password", "cause", "resolution", "nos_version"],
                   context_values=["CVM", "192.0.2.1", "never-render-this", "Possible service failure", "Inspect the service health", "7.0.1.15"])
    item = normalize_record(record, "prism-element", "source", "alerts", {}, "2026-10-17T00:00:00Z")
    assert item["message"] == "CVM 192.0.2.1 rebooted at {missing}"
    assert item["unresolved_parameters"] == ["missing"]
    assert item["vendor_guidance"]["recommended_action"] == "Inspect the service health"
    assert item["source_versions"]["software"] == "7.0.1.15"
    assert "never-render-this" not in json.dumps(item)
    assert render_vendor_text("<b>{name}</b><br>{__class__}", {"name":"Node A"}) == "Node A\n{__class__}"
