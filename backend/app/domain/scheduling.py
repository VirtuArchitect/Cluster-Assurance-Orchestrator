from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from enum import StrEnum
from hashlib import sha256
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field


class Recurrence(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    ON_DEMAND = "on_demand"


class MisfirePolicy(StrEnum):
    RUN_WITHIN_GRACE = "run_within_grace"
    MARK_MISSED = "mark_missed"


class CheckProfileVersion(BaseModel):
    profile_id: str
    name: str
    version: int
    definition_hash: str
    checks: list[str]
    timeout_minutes: int = 30

    @property
    def profile_version_id(self) -> str:
        return f"{self.profile_id}:v{self.version}:{self.definition_hash[:12]}"


class ScheduleDefinition(BaseModel):
    schedule_id: str
    name: str
    profile: CheckProfileVersion
    target_cluster_ids: list[str]
    timezone: str = "Europe/Berlin"
    recurrence: Recurrence = Recurrence.DAILY
    start_time: str = "06:00"
    weekly_day: int = 0
    enabled: bool = True
    misfire_policy: MisfirePolicy = MisfirePolicy.RUN_WITHIN_GRACE
    misfire_grace_minutes: int = 30


class ActiveClusterLock(BaseModel):
    cluster_id: str
    owner_run_id: str
    expires_at: datetime


class ScheduleOccurrence(BaseModel):
    occurrence_at: datetime
    idempotency_key: str
    target_cluster_ids: list[str]
    blocked_cluster_ids: list[str] = Field(default_factory=list)
    runnable_cluster_ids: list[str] = Field(default_factory=list)
    status: str
    reason: str


class SchedulePreview(BaseModel):
    schedule: ScheduleDefinition
    generated_at: datetime
    occurrences: list[ScheduleOccurrence]
    active_locks: list[ActiveClusterLock] = Field(default_factory=list)


def profile_definition_hash(checks: list[str], timeout_minutes: int) -> str:
    payload = "|".join(sorted(checks)) + f"|timeout={timeout_minutes}"
    return sha256(payload.encode("utf-8")).hexdigest()


def idempotency_key(schedule_id: str, profile_version_id: str, occurrence_at: datetime) -> str:
    normalized = occurrence_at.astimezone(UTC).isoformat()
    payload = f"{schedule_id}|{profile_version_id}|{normalized}"
    return sha256(payload.encode("utf-8")).hexdigest()


def build_schedule_preview(
    schedule: ScheduleDefinition,
    now: datetime | None = None,
    active_locks: list[ActiveClusterLock] | None = None,
    count: int = 5,
) -> SchedulePreview:
    generated_at = now or datetime.now(UTC)
    locks = active_locks or []
    occurrences = []
    for occurrence_at in next_occurrences(schedule, generated_at, count):
        blocked = locked_targets(schedule.target_cluster_ids, locks, occurrence_at)
        runnable = [cluster_id for cluster_id in schedule.target_cluster_ids if cluster_id not in blocked]
        status = "disabled"
        reason = "Schedule is disabled."
        if schedule.enabled:
            if blocked and not runnable:
                status = "blocked"
                reason = "All target clusters already have active locks."
            elif blocked:
                status = "partial"
                reason = "Some target clusters are locked and will not start twice."
            else:
                status = "ready"
                reason = "All target clusters are available for this occurrence."

        occurrences.append(
            ScheduleOccurrence(
                occurrence_at=occurrence_at,
                idempotency_key=idempotency_key(
                    schedule.schedule_id,
                    schedule.profile.profile_version_id,
                    occurrence_at,
                ),
                target_cluster_ids=schedule.target_cluster_ids,
                blocked_cluster_ids=blocked,
                runnable_cluster_ids=runnable,
                status=status,
                reason=reason,
            )
        )
    return SchedulePreview(
        schedule=schedule,
        generated_at=generated_at,
        occurrences=occurrences,
        active_locks=locks,
    )


def next_occurrences(
    schedule: ScheduleDefinition,
    now: datetime,
    count: int,
) -> list[datetime]:
    if schedule.recurrence == Recurrence.ON_DEMAND:
        return []

    zone = load_zone(schedule.timezone)
    local_now = now.astimezone(zone)
    hour, minute = parse_time(schedule.start_time)
    candidate = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if schedule.recurrence == Recurrence.WEEKLY:
        days_until = (schedule.weekly_day - candidate.weekday()) % 7
        candidate = candidate + timedelta(days=days_until)

    if candidate <= local_now:
        candidate = advance(schedule.recurrence, candidate)

    occurrences = []
    while len(occurrences) < count:
        occurrences.append(candidate.astimezone(UTC))
        candidate = advance(schedule.recurrence, candidate)
    return occurrences


def advance(recurrence: Recurrence, value: datetime) -> datetime:
    if recurrence == Recurrence.WEEKLY:
        return value + timedelta(days=7)
    return value + timedelta(days=1)


def parse_time(value: str) -> tuple[int, int]:
    parsed = time.fromisoformat(value)
    return parsed.hour, parsed.minute


def load_zone(timezone: str):
    if timezone.upper() == "UTC":
        return UTC
    try:
        return ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        return UTC


def locked_targets(
    target_cluster_ids: list[str],
    active_locks: list[ActiveClusterLock],
    occurrence_at: datetime,
) -> list[str]:
    target_set = set(target_cluster_ids)
    return sorted(
        lock.cluster_id
        for lock in active_locks
        if lock.cluster_id in target_set and lock.expires_at > occurrence_at
    )
