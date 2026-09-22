from app.domain.status import Finding, HealthStatus, Observation, evaluate_status


def test_missing_mandatory_observation_is_unknown_not_healthy() -> None:
    status = evaluate_status(
        observations=[
            Observation(
                check_id="HC-001",
                status=HealthStatus.HEALTHY,
                source="test",
                summary="reachable",
            ),
            Observation(
                check_id="HC-002",
                status=HealthStatus.UNKNOWN,
                source="test",
                summary="collector failed",
                mandatory=True,
            ),
        ],
        findings=[],
    )

    assert status == HealthStatus.UNKNOWN


def test_critical_precedes_unknown_warning_overdue_and_healthy() -> None:
    status = evaluate_status(
        observations=[
            Observation(
                check_id="HC-001",
                status=HealthStatus.UNKNOWN,
                source="test",
                summary="missing",
            ),
            Observation(
                check_id="HC-002",
                status=HealthStatus.WARNING,
                source="test",
                summary="warning",
            ),
        ],
        findings=[
            Finding(
                fingerprint="critical-demo",
                severity=HealthStatus.CRITICAL,
                title="Critical issue",
                explanation="Critical finding should dominate.",
                source="test",
            )
        ],
    )

    assert status == HealthStatus.CRITICAL


def test_no_observations_defaults_unknown() -> None:
    assert evaluate_status(observations=[], findings=[]) == HealthStatus.UNKNOWN

