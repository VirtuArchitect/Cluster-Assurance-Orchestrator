from datetime import UTC, datetime, timedelta

from app.domain.scheduling import (
    ActiveClusterLock,
    CheckProfileVersion,
    Recurrence,
    ScheduleDefinition,
    build_schedule_preview,
    idempotency_key,
    profile_definition_hash,
)


def make_profile() -> CheckProfileVersion:
    checks = ["HC-001", "HC-002"]
    return CheckProfileVersion(
        profile_id="daily-standard",
        name="Daily Standard",
        version=1,
        definition_hash=profile_definition_hash(checks, 30),
        checks=checks,
    )


def test_idempotency_key_is_stable_for_same_occurrence() -> None:
    occurrence = datetime(2026, 9, 22, 6, 0, tzinfo=UTC)
    profile = make_profile()

    first = idempotency_key("schedule-1", profile.profile_version_id, occurrence)
    second = idempotency_key("schedule-1", profile.profile_version_id, occurrence)

    assert first == second
    assert len(first) == 64


def test_active_lock_blocks_only_matching_target() -> None:
    now = datetime(2026, 9, 22, 5, 0, tzinfo=UTC)
    schedule = ScheduleDefinition(
        schedule_id="schedule-1",
        name="Daily",
        profile=make_profile(),
        target_cluster_ids=["cluster-a", "cluster-b"],
        timezone="UTC",
        recurrence=Recurrence.DAILY,
        start_time="06:00",
    )
    preview = build_schedule_preview(
        schedule,
        now=now,
        active_locks=[
            ActiveClusterLock(
                cluster_id="cluster-a",
                owner_run_id="run-1",
                expires_at=now + timedelta(hours=2),
            )
        ],
        count=1,
    )

    occurrence = preview.occurrences[0]

    assert occurrence.status == "partial"
    assert occurrence.blocked_cluster_ids == ["cluster-a"]
    assert occurrence.runnable_cluster_ids == ["cluster-b"]


def test_weekly_preview_uses_configured_weekday() -> None:
    now = datetime(2026, 9, 22, 5, 0, tzinfo=UTC)  # Tuesday
    schedule = ScheduleDefinition(
        schedule_id="weekly-1",
        name="Weekly",
        profile=make_profile(),
        target_cluster_ids=["cluster-a"],
        timezone="UTC",
        recurrence=Recurrence.WEEKLY,
        weekly_day=5,
        start_time="03:00",
    )

    preview = build_schedule_preview(schedule, now=now, count=2)

    assert preview.occurrences[0].occurrence_at.weekday() == 5
    assert preview.occurrences[1].occurrence_at - preview.occurrences[0].occurrence_at == timedelta(days=7)

