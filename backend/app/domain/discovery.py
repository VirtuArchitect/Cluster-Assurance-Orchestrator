from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class EndpointKind(StrEnum):
    PRISM_CENTRAL = "prism_central"
    PRISM_ELEMENT = "prism_element"


class ProbeState(StrEnum):
    SUPPORTED = "supported"
    AUTH_REQUIRED = "auth_required"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class CapabilityProbe(BaseModel):
    name: str
    path: str
    method: str = "GET"
    source: str
    notes: str


class ProbeResult(BaseModel):
    name: str
    path: str
    method: str
    state: ProbeState
    status_code: int | None = None
    elapsed_ms: int | None = None
    content_type: str | None = None
    body_sha256: str | None = None
    body_size_bytes: int = 0
    error: str | None = None
    source: str
    notes: str


class EndpointDiscoveryResult(BaseModel):
    kind: EndpointKind
    alias: str
    base_url: str
    tls_mode: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    probes: list[ProbeResult] = Field(default_factory=list)

    @property
    def state(self) -> ProbeState:
        if any(probe.state == ProbeState.SUPPORTED for probe in self.probes):
            return ProbeState.SUPPORTED
        if any(probe.state == ProbeState.AUTH_REQUIRED for probe in self.probes):
            return ProbeState.AUTH_REQUIRED
        if any(probe.state == ProbeState.UNAVAILABLE for probe in self.probes):
            return ProbeState.UNAVAILABLE
        return ProbeState.UNKNOWN


class LabDiscoveryReport(BaseModel):
    product: str = "Cluster Assurance Orchestrator"
    maturity: str = "lab discovery"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    read_only: bool
    ncc_enabled: bool
    ssh_enabled: bool
    endpoints: list[EndpointDiscoveryResult]
    warnings: list[str] = Field(default_factory=list)


def prism_central_probe_catalogue() -> list[CapabilityProbe]:
    return [
        CapabilityProbe(
            name="pc-root-reachability",
            path="/",
            source="generic HTTPS reachability",
            notes="Confirms HTTPS listener response only; does not prove API support.",
        ),
        CapabilityProbe(
            name="pc-v3-cluster-list-endpoint-presence",
            path="/api/nutanix/v3/clusters/list",
            source="Nutanix Prism API v3 cluster list convention",
            notes=(
                "GET probe only. A 405 or 401 can still indicate the route exists; "
                "read-list POST execution is deferred to contract validation."
            ),
        ),
    ]


def prism_element_probe_catalogue() -> list[CapabilityProbe]:
    return [
        CapabilityProbe(
            name="pe-root-reachability",
            path="/",
            source="generic HTTPS reachability",
            notes="Confirms HTTPS listener response only; does not prove API support.",
        ),
        CapabilityProbe(
            name="pe-v2-cluster-endpoint",
            path="/PrismGateway/services/rest/v2.0/cluster/",
            source="Prism Element REST v2 cluster endpoint convention",
            notes="GET probe for read-only cluster details.",
        ),
    ]

