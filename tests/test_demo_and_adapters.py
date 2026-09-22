import pytest
from urllib.error import HTTPError

from app.adapters.ncc import NccDisabledError, NccRunner
from app.adapters.nutanix import AdapterDisabledError, NutanixReadOnlyAdapter
from app.core.config import Settings
from app.domain.demo import build_demo_run
from app.domain.discovery import ProbeState
from app.domain.status import HealthStatus
from app.domain.ncc import parse_ncc_output


def test_demo_run_is_simulated_and_unknown_when_live_data_absent() -> None:
    run = build_demo_run(Settings(demo_mode=True))

    assert run.mode == "simulated"
    assert run.status == HealthStatus.UNKNOWN
    assert "cannot contact Prism" in run.warnings[0]


def test_prism_adapter_refuses_live_calls_in_demo_mode() -> None:
    adapter = NutanixReadOnlyAdapter(Settings(demo_mode=True))

    with pytest.raises(AdapterDisabledError, match="demo mode"):
        adapter.discover_versions()


def test_ncc_runner_disabled_by_default() -> None:
    runner = NccRunner(Settings(demo_mode=False, enable_ncc=False, enable_ssh=False))

    with pytest.raises(NccDisabledError, match="disabled"):
        runner.assert_enabled()


def test_ncc_plan_uses_allowlisted_profile_only() -> None:
    runner = NccRunner(Settings(demo_mode=False, enable_ncc=False, enable_ssh=False))

    plan = runner.build_plan("full-run-all", "cluster-a")

    assert plan.status == "blocked"
    assert plan.profile.command == ("ncc", "health_checks", "run_all")
    assert "profile identifier" in plan.warnings[0]


def test_ncc_plan_rejects_unknown_profile() -> None:
    runner = NccRunner(Settings(demo_mode=False, enable_ncc=False, enable_ssh=False))

    with pytest.raises(ValueError, match="Unknown NCC"):
        runner.build_plan("ncc health_checks run_all; rm -rf /", "cluster-a")


def test_ncc_parser_maps_unknown_output_to_unknown() -> None:
    parsed = parse_ncc_output("totally unexpected output")

    assert parsed.status == HealthStatus.UNKNOWN


def test_ncc_parser_maps_fail_to_critical() -> None:
    parsed = parse_ncc_output("PASS: time_sync_check: ok\nFAIL: resiliency_check: KB 1234 failed")

    assert parsed.status == HealthStatus.CRITICAL
    assert parsed.checks[1].kb == "1234"


class FakeHeaders(dict):
    def get(self, key, default=None):  # noqa: ANN001
        return super().get(key.lower(), default)


class FakeResponse:
    status = 200
    headers = FakeHeaders({"content-type": "application/json"})

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False

    def read(self, _limit: int) -> bytes:
        return b'{"ok": true}'


def test_read_only_discovery_maps_successful_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_urlopen(request, timeout, context):  # noqa: ANN001
        calls.append((request.full_url, request.get_method(), timeout, context))
        return FakeResponse()

    monkeypatch.setattr("app.adapters.nutanix.urlopen", fake_urlopen)
    settings = Settings(
        demo_mode=False,
        read_only_mode=True,
        pc_url="https://pc.example.invalid:9440/",
        pc_username="admin",
        pc_password="secret",
    )

    report = NutanixReadOnlyAdapter(settings).discover()

    assert report.read_only is True
    assert report.ncc_enabled is False
    assert report.endpoints[0].alias == "prism-central"
    assert report.endpoints[0].probes[0].state == ProbeState.SUPPORTED
    assert report.endpoints[0].probes[0].body_sha256 is not None
    assert all(call[1] == "GET" for call in calls)


def test_discovery_refuses_write_capable_mode() -> None:
    adapter = NutanixReadOnlyAdapter(Settings(demo_mode=False, read_only_mode=False))

    with pytest.raises(AdapterDisabledError, match="write-capable"):
        adapter.discover()


class InventoryFakeResponse:
    status = 200
    headers = FakeHeaders({"content-type": "application/json"})

    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False

    def read(self, _limit: int) -> bytes:
        return self._body


def test_inventory_run_collects_and_normalizes_clusters(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    pc_body = (
        b'{"entities":[{"metadata":{"uuid":"pc-cluster-1"},'
        b'"spec":{"name":"PC Cluster"},"status":{"resources":{"version":"6.8"}}}]}'
    )
    pe_body = b'{"cluster_uuid":"pe-cluster-1","name":"PE Cluster","version":"6.8"}'
    domain_body = b'{"entities":[{"metadata":{"uuid":"domain-1"},"spec":{"name":"domain item"}}]}'

    def fake_urlopen(request, timeout, context):  # noqa: ANN001
        if "/api/nutanix/v3/clusters/list" in request.full_url:
            assert request.get_method() == "POST"
            return InventoryFakeResponse(pc_body)
        if request.full_url.startswith("https://pc.example.invalid:9440/api/nutanix/v3/"):
            assert request.get_method() == "POST"
            return InventoryFakeResponse(domain_body)
        assert request.get_method() == "GET"
        return InventoryFakeResponse(pe_body)

    monkeypatch.setattr("app.adapters.nutanix.urlopen", fake_urlopen)
    settings = Settings(
        demo_mode=False,
        read_only_mode=True,
        pc_url="https://pc.example.invalid:9440/",
        pc_username="admin",
        pc_password="secret",
        pe_url="https://pe.example.invalid:9440/",
        pe_username="admin",
        pe_password="secret",
        evidence_dir=str(tmp_path),
    )

    report = NutanixReadOnlyAdapter(settings).collect_inventory(run_id="test-run")

    assert report.status == HealthStatus.HEALTHY
    assert len(report.clusters) == 2
    assert {cluster.name for cluster in report.clusters} == {"PC Cluster", "PE Cluster"}
    assert all(collector.raw_artifact for collector in report.collectors)
    assert {collector.domain for collector in report.collectors} == {"inventory", "storage", "hardware", "network", "capacity"}


def test_prism_element_inventory_falls_back_to_v3_cluster_list(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    pe_v3_body = (
        b'{"entities":[{"metadata":{"uuid":"pe-cluster-1"},'
        b'"spec":{"name":"PE Cluster"},"status":{"resources":{"version":"6.10"}}}]}'
    )

    def fake_urlopen(request, timeout, context):  # noqa: ANN001
        if "/PrismGateway/services/rest/v2.0/cluster/" in request.full_url:
            raise HTTPError(request.full_url, 401, "Unauthorized", hdrs=None, fp=None)
        if "/api/nutanix/v3/clusters/list" in request.full_url:
            assert request.get_method() == "POST"
            return InventoryFakeResponse(pe_v3_body)
        assert request.get_method() == "GET"
        return InventoryFakeResponse(b'{"entities":[{"metadata":{"uuid":"domain-1"}}]}')

    monkeypatch.setattr("app.adapters.nutanix.urlopen", fake_urlopen)
    settings = Settings(
        demo_mode=False,
        read_only_mode=True,
        pe_url="https://pe.example.invalid:9440/",
        pe_username="admin",
        pe_password="secret",
        evidence_dir=str(tmp_path),
    )

    report = NutanixReadOnlyAdapter(settings).collect_inventory(run_id="pe-fallback-run")

    assert report.status == HealthStatus.WARNING
    assert report.collectors[0].status == HealthStatus.HEALTHY
    assert report.clusters[0].name == "PE Cluster"
    assert any(collector.domain == "capacity" and collector.status == HealthStatus.UNKNOWN for collector in report.collectors)


def test_inventory_run_empty_payload_is_unknown(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    def fake_urlopen(request, timeout, context):  # noqa: ANN001
        return InventoryFakeResponse(b'{"entities":[]}')

    monkeypatch.setattr("app.adapters.nutanix.urlopen", fake_urlopen)
    settings = Settings(
        demo_mode=False,
        read_only_mode=True,
        pc_url="https://pc.example.invalid:9440/",
        evidence_dir=str(tmp_path),
    )

    report = NutanixReadOnlyAdapter(settings).collect_inventory(run_id="empty-run")

    assert report.status == HealthStatus.UNKNOWN
    assert report.collectors[0].status == HealthStatus.UNKNOWN


def test_domain_collectors_use_configured_prism_connections(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    calls = []
    pc_cluster_body = (
        b'{"entities":[{"metadata":{"uuid":"pc-cluster-1"},'
        b'"spec":{"name":"PC Cluster"},"status":{"resources":{"version":"6.8"}}}]}'
    )
    domain_body = b'{"entities":[{"metadata":{"uuid":"domain-1"}}]}'

    def fake_urlopen(request, timeout, context):  # noqa: ANN001
        calls.append((request.full_url, request.get_method(), request.headers.get("Authorization")))
        if "/api/nutanix/v3/clusters/list" in request.full_url:
            return InventoryFakeResponse(pc_cluster_body)
        return InventoryFakeResponse(domain_body)

    monkeypatch.setattr("app.adapters.nutanix.urlopen", fake_urlopen)
    settings = Settings(
        demo_mode=False,
        read_only_mode=True,
        pc_url="https://pc.example.invalid:9440/",
        pc_username="admin",
        pc_password="secret",
        evidence_dir=str(tmp_path),
    )

    report = NutanixReadOnlyAdapter(settings).collect_inventory(run_id="domain-run")

    domains = {collector.domain for collector in report.collectors}
    assert {"inventory", "storage", "hardware", "network", "capacity"}.issubset(domains)
    assert all(collector.raw_artifact for collector in report.collectors)
    assert all(auth_header for _, _, auth_header in calls)
    called_urls = "\n".join(url for url, _, _ in calls)
    assert "/api/nutanix/v3/storage_containers/list" in called_urls
    assert "/api/nutanix/v3/hosts/list" in called_urls
    assert "/api/nutanix/v3/subnets/list" in called_urls
