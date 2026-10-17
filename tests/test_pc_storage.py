import hashlib
import json
from pathlib import Path

import pytest

from app.adapters.nutanix import EndpointConfig, HttpResponse, NutanixReadOnlyAdapter, pc_domain_collectors
from app.core.config import Settings
from app.domain.discovery import EndpointKind
from app.domain.inventory import InventorySource
from app.domain.status import HealthStatus


@pytest.mark.parametrize("payload,code,expected,count", [
    ({"data": [{"containerExtId": "a", "clusterExtId": "cluster-a", "$objectType": "clustermgmt.v4.config.StorageContainer"}], "metadata": {"totalAvailableResults": 1, "flags": [{"name": "hasError", "value": False}, {"name": "isTruncated", "value": False}], "links": [{"rel": "last"}]}}, 200, "HEALTHY", 1),
    ({"data": [{"extId": "a"}, {"extId": "b"}], "metadata": {"totalAvailableResults": 2}}, 200, "HEALTHY", 2),
    ({"data": [], "metadata": {"totalAvailableResults": 0}}, 200, "HEALTHY", 0),
    ({"data": [{"extId": "a"}], "metadata": {"totalAvailableResults": 3}}, 200, "UNKNOWN", None),
    ({"data": [{"extId": "a"}], "metadata": {"totalAvailableResults": 1, "flags": [{"name": "hasError", "value": True}]}}, 200, "UNKNOWN", None),
    ({"data": {"error": "bad"}, "metadata": {"totalAvailableResults": 1}}, 200, "UNKNOWN", None),
    ({"data": [{}], "metadata": {"totalAvailableResults": 1}}, 200, "UNKNOWN", None),
    ({"message": "Unauthorized"}, 401, "UNKNOWN", None),
    ({"message": "Unsupported"}, 404, "UNKNOWN", None),
])
def test_pc_storage_reads_v4_and_preserves_raw_evidence(monkeypatch, tmp_path, payload, code, expected, count):
    adapter = NutanixReadOnlyAdapter(Settings(demo_mode=False, evidence_dir=str(tmp_path)))
    endpoint = EndpointConfig(EndpointKind.PRISM_CENTRAL, "prism-central", "https://pc.invalid", "admin", "test")
    body = json.dumps(payload).encode()
    calls = []

    def request(ep, method, path, body=None):
        calls.append((method, path, body))
        return HttpResponse(status_code=code, body=json.dumps(payload).encode())

    monkeypatch.setattr(adapter, "_request", request)
    result = adapter._collect_domain(endpoint, "storage-test", InventorySource.PRISM_CENTRAL, pc_domain_collectors()[0])
    assert calls == [("GET", "/api/clustermgmt/v4.0.b2/config/storage-containers?$limit=100", None)]
    assert result.status == HealthStatus(expected)
    assert result.item_count == count
    assert result.status_code == code
    assert result.raw_artifact.sha256 == hashlib.sha256(body).hexdigest()
    assert Path(result.raw_artifact.uri).read_bytes() == body
