from pydantic import BaseModel


class HealthCheck(BaseModel):
    check_id: str
    name: str
    source: str
    default_frequency: str
    failure_outcome: str
    mandatory: bool = True


class HealthCatalogue(BaseModel):
    version: str
    checks: list[HealthCheck]


def default_catalogue() -> HealthCatalogue:
    return HealthCatalogue(
        version="2026.09.foundation",
        checks=[
            HealthCheck(
                check_id="HC-001",
                name="Prism endpoint reachability",
                source="HTTPS",
                default_frequency="5 minutes",
                failure_outcome="UNKNOWN",
            ),
            HealthCheck(
                check_id="HC-002",
                name="Cluster availability",
                source="Prism API",
                default_frequency="Daily",
                failure_outcome="CRITICAL",
            ),
            HealthCheck(
                check_id="HC-003",
                name="Host availability",
                source="Prism API",
                default_frequency="Daily",
                failure_outcome="CRITICAL",
            ),
            HealthCheck(
                check_id="HC-004",
                name="CVM availability",
                source="Prism API or NCC",
                default_frequency="Daily",
                failure_outcome="CRITICAL",
            ),
            HealthCheck(
                check_id="HC-016",
                name="Application self-health",
                source="Internal",
                default_frequency="1 minute",
                failure_outcome="CRITICAL",
            ),
        ],
    )

