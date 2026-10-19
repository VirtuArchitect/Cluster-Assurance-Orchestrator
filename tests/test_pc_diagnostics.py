from hashlib import sha256
import json

import pytest

from app.adapters.nutanix import HttpResponse, NutanixReadOnlyAdapter
from app.core.config import Settings
from app.services.pc_diagnostics import collect_pc_diagnostics
from app.services.monitoring import collect_monitoring


def setup(tmp_path):
    adapter = NutanixReadOnlyAdapter(Settings(demo_mode=False, pc_url="https://pc.invalid:9440",
        pe_url="https://pe.invalid:9440", evidence_dir=str(tmp_path)))
    pc, pe = adapter._configured_endpoints()
    return adapter, pc, pe


def fixtures():
    start = "2026-10-19T04:48:05Z"
    return [
        {"uuid": "root", "operation_type": "PC Microservice Infrastructure Deployment", "status": "RUNNING", "creation_time": start},
        {"uuid": "check", "operation_type": "CMSP Prechecks", "status": "FAILED", "creation_time": start,
         "error_detail": "Please ensure that Cluster Virtual IP or Cluster FQDN is set on the Prism Element 'pe.invalid'. Please ensure that Cluster Data Services IP is set on the Prism Element 'pe.invalid'"},
    ], {"uuid": "pe-cluster", "cluster_external_ipaddress": None, "cluster_external_data_services_ipaddress": None}


def install(monkeypatch, tasks, cluster, total=None):
    calls = []
    def request(self, endpoint, method, path, body=None):
        calls.append((method, path, json.loads(body) if body else None))
        if method == "POST":
            offset = json.loads(body)["offset"]
            payload = {"entities": tasks[offset:offset+100], "metadata": {"total_matches": len(tasks) if total is None else total}}
        else:
            payload = cluster
        return HttpResponse(status_code=200, elapsed_ms=1, body=json.dumps(payload).encode())
    monkeypatch.setattr(NutanixReadOnlyAdapter, "_request", request)
    return calls


def test_matched_blocker_with_hashed_read_only_requests(monkeypatch, tmp_path):
    tasks, cluster = fixtures()
    calls = install(monkeypatch, tasks, cluster)
    result = collect_pc_diagnostics(*setup(tmp_path), "run-1")
    assert result["status"] == "BLOCKED"
    assert len(result["blockers"]) == 2
    assert result["tasks"][0]["status"] == "RUNNING"
    assert result["tasks"][1]["status"] == "FAILED"
    assert result["prerequisites"]["fqdn_status"] == "Not verified by this endpoint"
    assert calls == [("POST", "/api/nutanix/v3/tasks/list", {"kind": "task", "length": 100, "offset": 0}),
                     ("GET", "/PrismGateway/services/rest/v2.0/cluster/", None)]
    for e in result["evidence"]:
        assert sha256((tmp_path / "raw" / "run-1" / e["artifact"]).read_bytes()).hexdigest() == e["sha256"]


@pytest.mark.parametrize("change", ["new_success", "other_pe", "configured", "other_precheck"])
def test_historical_or_unmatched_failures_do_not_confirm_blocker(monkeypatch, tmp_path, change):
    tasks, cluster = fixtures()
    if change == "new_success":
        tasks += [{"uuid": "new-root", "operation_type": tasks[0]["operation_type"], "creation_time": "2026-10-20T00:00:00Z", "status": "SUCCEEDED"}]
    elif change == "other_pe":
        tasks[1]["error_detail"] = tasks[1]["error_detail"].replace("pe.invalid", "another.invalid")
    elif change == "configured":
        cluster.update(cluster_external_ipaddress="192.0.2.1", cluster_external_data_services_ipaddress="192.0.2.2")
    else:
        tasks[1]["creation_time"] = "2026-10-18T00:00:00Z"
    install(monkeypatch, tasks, cluster)
    result = collect_pc_diagnostics(*setup(tmp_path), "run-1")
    assert result["status"] == "NO_CONFIRMED_BLOCKER"
    assert result["blockers"] == []


@pytest.mark.parametrize("change", ["missing_field", "duplicate", "incomplete", "invalid_time"])
def test_incomplete_or_malformed_evidence_is_unknown(monkeypatch, tmp_path, change):
    tasks, cluster = fixtures()
    total = None
    if change == "missing_field":
        cluster.pop("cluster_external_ipaddress")
    elif change == "duplicate":
        tasks.append(tasks[0])
    elif change == "incomplete":
        total = 10
    else:
        tasks[0]["creation_time"] = "bad"
    install(monkeypatch, tasks, cluster, total)
    result = collect_pc_diagnostics(*setup(tmp_path), "run-1")
    assert result["status"] == "UNKNOWN"
    assert result["blockers"] == []


@pytest.mark.parametrize("code", [401, 403, 404, 500])
def test_http_failures_do_not_clear_or_confirm_blocker(monkeypatch, tmp_path, code):
    monkeypatch.setattr(NutanixReadOnlyAdapter, "_request", lambda *a, **k: HttpResponse(status_code=code, body=b'{}'))
    result = collect_pc_diagnostics(*setup(tmp_path), "run-1")
    assert result["status"] == "UNKNOWN"
    assert str(code) in result["error"]


def test_complete_task_pagination(monkeypatch, tmp_path):
    tasks, cluster = fixtures()
    tasks += [{"uuid": f"other-{i}", "operation_type": "Other"} for i in range(125)]
    calls = install(monkeypatch, tasks, cluster)
    result = collect_pc_diagnostics(*setup(tmp_path), "run-1")
    assert result["status"] == "BLOCKED"
    assert result["task_records_collected"] == 127
    assert [c[2]["offset"] for c in calls if c[0] == "POST"] == [0, 100]


@pytest.mark.parametrize("resolved", [False, True])
def test_monitoring_attaches_blocker_and_prioritizes_dashboard_check(monkeypatch, tmp_path, resolved):
    tasks, cluster = fixtures()
    base = install(monkeypatch, tasks, cluster)
    diagnostic_request = NutanixReadOnlyAdapter._request
    def request(self, endpoint, method, path, body=None):
        if "/alerts/" in path or "/events/" in path:
            records = ([{"id": "alert", "severity": "kCritical", "resolved": resolved,
                "message": "Microservices Infrastructure is not in healthy state", "check_id": "pc::200335"}]
                if endpoint.alias == "prism-central" and "/alerts/" in path else [])
            return HttpResponse(status_code=200, body=json.dumps({"entities": records, "metadata": {"total_entities": len(records)}}).encode())
        return diagnostic_request(self, endpoint, method, path, body)
    monkeypatch.setattr(NutanixReadOnlyAdapter, "_request", request)
    report = collect_monitoring(setup(tmp_path)[0].settings)
    incident = report["incidents"][0]
    assert incident["deployment_diagnostics"]["status"] == "BLOCKED"
    assert "prerequisite blocker" in incident["triage"]["steps"][0]["check"]
    assert incident["lifecycle"] == ("RESOLVED_IN_PRISM" if resolved else "OPEN")
    assert incident["resolved"] is resolved
    assert report["summary"]["open"] == (0 if resolved else 1)
    assert len(base) == 2


@pytest.mark.parametrize("resolved", [False, True])
def test_failed_refresh_does_not_reuse_previous_blocker_as_current(monkeypatch, tmp_path, resolved):
    tasks, cluster = fixtures()
    install(monkeypatch, tasks, cluster)
    diagnostic_request = NutanixReadOnlyAdapter._request
    mode = ["success"]
    def request(self, endpoint, method, path, body=None):
        if "/alerts/" in path or "/events/" in path:
            if mode[0] == "feed_failure" and endpoint.alias == "prism-central":
                return HttpResponse(status_code=401, body=b'{}')
            records = ([{"id": "alert", "severity": "kCritical", "resolved": resolved,
                        "message": "Microservices Infrastructure is not in healthy state"}]
                       if endpoint.alias == "prism-central" and "/alerts/" in path else [])
            return HttpResponse(status_code=200, body=json.dumps({"entities": records, "metadata": {"total_entities": len(records)}}).encode())
        if mode[0] == "diagnostic_failure":
            return HttpResponse(status_code=401, body=b'{}')
        return diagnostic_request(self, endpoint, method, path, body)
    monkeypatch.setattr(NutanixReadOnlyAdapter, "_request", request)
    config = setup(tmp_path)[0].settings
    assert collect_monitoring(config)["incidents"][0]["deployment_diagnostics"]["status"] == "BLOCKED"
    mode[0] = "diagnostic_failure"
    item = collect_monitoring(config)["incidents"][0]
    assert item["deployment_diagnostics"]["status"] == "UNKNOWN"
    assert item["deployment_diagnostics"]["blockers"] == []
    assert "observed CMSP deployment prerequisite blocker" not in item["triage"]["steps"][0]["check"]
    mode[0] = "feed_failure"
    item = collect_monitoring(config)["incidents"][0]
    assert item["availability"] == "UNAVAILABLE"
    assert "deployment_diagnostics" not in item
