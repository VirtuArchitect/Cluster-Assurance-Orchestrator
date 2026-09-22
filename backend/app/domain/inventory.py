from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.status import HealthStatus, Observation, evaluate_status


class InventorySource(StrEnum):
    PRISM_CENTRAL = "prism_central"
    PRISM_ELEMENT = "prism_element"


class RawArtifactRef(BaseModel):
    source: InventorySource
    path: str
    method: str
    sha256: str
    size_bytes: int
    uri: str


class ClusterInventoryItem(BaseModel):
    source: InventorySource
    external_id: str
    name: str
    state: str | None = None
    version: str | None = None
    raw_artifact_sha256: str
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class InventoryCollectorResult(BaseModel):
    source: InventorySource
    endpoint_alias: str
    status: HealthStatus
    summary: str
    path: str
    method: str
    status_code: int | None = None
    elapsed_ms: int | None = None
    clusters: list[ClusterInventoryItem] = Field(default_factory=list)
    raw_artifact: RawArtifactRef | None = None
    error: str | None = None


class InventoryRunReport(BaseModel):
    run_id: str
    maturity: str = "lab inventory"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    read_only: bool
    ncc_enabled: bool
    ssh_enabled: bool
    collectors: list[InventoryCollectorResult]
    observations: list[Observation]
    warnings: list[str] = Field(default_factory=list)

    @property
    def status(self) -> HealthStatus:
        return evaluate_status(observations=self.observations, findings=[])

    @property
    def clusters(self) -> list[ClusterInventoryItem]:
        items: list[ClusterInventoryItem] = []
        seen: set[tuple[InventorySource, str]] = set()
        for collector in self.collectors:
            for cluster in collector.clusters:
                key = (cluster.source, cluster.external_id)
                if key not in seen:
                    items.append(cluster)
                    seen.add(key)
        return items

    def api_dict(self) -> dict[str, object]:
        payload = self.model_dump(mode="json")
        payload["status"] = self.status
        payload["clusters"] = [cluster.model_dump(mode="json") for cluster in self.clusters]
        return payload

