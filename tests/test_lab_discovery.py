from pathlib import Path

from app.domain.discovery import (
    EndpointDiscoveryResult,
    EndpointKind,
    LabDiscoveryReport,
    ProbeResult,
    ProbeState,
)
from app.services.lab_discovery import hash_file, write_discovery_evidence
from app.domain.inventory import (
    ClusterInventoryItem,
    InventoryCollectorResult,
    InventoryRunReport,
    InventorySource,
)
from app.domain.status import HealthStatus, Observation
from app.services.inventory_run import read_latest_inventory_evidence, write_inventory_evidence


def test_write_discovery_evidence_creates_hashed_report(tmp_path: Path) -> None:
    report = LabDiscoveryReport(
        read_only=True,
        ncc_enabled=False,
        ssh_enabled=False,
        endpoints=[
            EndpointDiscoveryResult(
                kind=EndpointKind.PRISM_CENTRAL,
                alias="prism-central",
                base_url="https://pc.example.invalid:9440/",
                tls_mode="strict",
                probes=[
                    ProbeResult(
                        name="root",
                        path="/",
                        method="GET",
                        state=ProbeState.SUPPORTED,
                        status_code=200,
                        source="test",
                        notes="test probe",
                    )
                ],
            )
        ],
    )

    output = write_discovery_evidence(report, tmp_path)

    assert output.exists()
    assert output.name.startswith("lab-discovery-")
    assert len(hash_file(output)) == 64
    assert "pc.example.invalid" in output.read_text(encoding="utf-8")


def test_write_inventory_evidence_includes_computed_status(tmp_path: Path) -> None:
    report = InventoryRunReport(
        run_id="inventory-test",
        read_only=True,
        ncc_enabled=False,
        ssh_enabled=False,
        collectors=[
            InventoryCollectorResult(
                source=InventorySource.PRISM_ELEMENT,
                endpoint_alias="prism-element",
                status=HealthStatus.HEALTHY,
                summary="one cluster",
                path="/PrismGateway/services/rest/v2.0/cluster/",
                method="GET",
                clusters=[
                    ClusterInventoryItem(
                        source=InventorySource.PRISM_ELEMENT,
                        external_id="cluster-1",
                        name="Cluster 1",
                        raw_artifact_sha256="abc",
                    )
                ],
            )
        ],
        observations=[
            Observation(
                check_id="HC-003",
                status=HealthStatus.HEALTHY,
                source="test",
                summary="one cluster",
            )
        ],
    )

    output = write_inventory_evidence(report, tmp_path)
    content = output.read_text(encoding="utf-8")

    assert '"status": "HEALTHY"' in content
    assert "Cluster 1" in content


def test_read_latest_inventory_evidence_returns_newest_report(tmp_path: Path) -> None:
    older = tmp_path / "inventory-run-20260101T000000Z.json"
    newer = tmp_path / "inventory-run-20260102T000000Z.json"
    older.write_text('{"status": "UNKNOWN"}', encoding="utf-8")
    newer.write_text('{"status": "HEALTHY"}', encoding="utf-8")

    latest = read_latest_inventory_evidence(tmp_path)

    assert latest == {"status": "HEALTHY"}
