from uuid import uuid4

from pydantic import BaseModel

from app.core.config import Settings
from app.domain.evidence import EvidenceManifest
from app.domain.status import ClusterEvaluation, HealthStatus, Observation


class DemoRun(BaseModel):
    run_id: str
    mode: str
    status: HealthStatus
    clusters: list[ClusterEvaluation]
    evidence_manifest_hash: str
    warnings: list[str]


def build_demo_run(settings: Settings) -> DemoRun:
    if not settings.demo_mode:
        raise ValueError("demo run is only available when demo mode is enabled")

    run_id = str(uuid4())
    clusters = [
        ClusterEvaluation(
            cluster_id="demo-cluster-01",
            cluster_name="Demo Cluster 01",
            observations=[
                Observation(
                    check_id="HC-001",
                    status=HealthStatus.HEALTHY,
                    source="synthetic",
                    summary="Synthetic Prism endpoint is reachable.",
                ),
                Observation(
                    check_id="HC-002",
                    status=HealthStatus.UNKNOWN,
                    source="synthetic",
                    summary="Inventory collector intentionally lacks live Prism data in demo mode.",
                ),
            ],
        )
    ]
    status = clusters[0].status
    manifest = EvidenceManifest(
        product_version="0.1.0",
        profile_version="demo-foundation",
        run_id=run_id,
        result_summary={"estateStatus": status, "clusterCount": len(clusters)},
    )
    return DemoRun(
        run_id=run_id,
        mode="simulated",
        status=status,
        clusters=clusters,
        evidence_manifest_hash=manifest.stable_hash(),
        warnings=[
            "Demo mode uses synthetic data and cannot contact Prism, SSH, NCC or integrations.",
            "UNKNOWN is expected when live mandatory collectors are unavailable.",
        ],
    )

