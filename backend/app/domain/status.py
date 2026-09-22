from enum import StrEnum

from pydantic import BaseModel, Field


class HealthStatus(StrEnum):
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"
    WARNING = "WARNING"
    OVERDUE = "OVERDUE"
    HEALTHY = "HEALTHY"


STATUS_PRECEDENCE = (
    HealthStatus.CRITICAL,
    HealthStatus.UNKNOWN,
    HealthStatus.WARNING,
    HealthStatus.OVERDUE,
    HealthStatus.HEALTHY,
)


class Observation(BaseModel):
    check_id: str
    status: HealthStatus
    source: str
    summary: str
    mandatory: bool = True
    evidence_ref: str | None = None


class Finding(BaseModel):
    fingerprint: str
    severity: HealthStatus
    title: str
    explanation: str
    source: str


class ClusterEvaluation(BaseModel):
    cluster_id: str
    cluster_name: str
    observations: list[Observation] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    maintenance: bool = False

    @property
    def status(self) -> HealthStatus:
        return evaluate_status(self.observations, self.findings)


def evaluate_status(
    observations: list[Observation],
    findings: list[Finding],
) -> HealthStatus:
    statuses = [finding.severity for finding in findings]
    statuses.extend(observation.status for observation in observations)

    mandatory_failure = any(
        observation.mandatory and observation.status == HealthStatus.UNKNOWN
        for observation in observations
    )
    if mandatory_failure:
        statuses.append(HealthStatus.UNKNOWN)

    if not statuses:
        return HealthStatus.UNKNOWN

    for status in STATUS_PRECEDENCE:
        if status in statuses:
            return status
    return HealthStatus.UNKNOWN

