from __future__ import annotations

from datetime import UTC, datetime

from app.domain.inventory import InventoryRunReport
from app.domain.scheduling import (
    ActiveClusterLock,
    CheckProfileVersion,
    Recurrence,
    ScheduleDefinition,
    SchedulePreview,
    build_schedule_preview,
    profile_definition_hash,
)
from app.services.inventory_run import read_latest_inventory_evidence


DEFAULT_CHECKS = ["HC-001", "HC-002", "HC-003", "HC-016"]


def default_profile() -> CheckProfileVersion:
    checks = DEFAULT_CHECKS
    timeout_minutes = 30
    return CheckProfileVersion(
        profile_id="daily-standard",
        name="Daily Standard",
        version=1,
        definition_hash=profile_definition_hash(checks, timeout_minutes),
        checks=checks,
        timeout_minutes=timeout_minutes,
    )


def default_schedule_for_latest_inventory(evidence_dir: str, active_locks: list[ActiveClusterLock] | None = None) -> SchedulePreview:
    latest = read_latest_inventory_evidence(evidence_dir)
    target_ids = ["no-lab-inventory"]
    if latest:
        target_ids = list(dict.fromkeys(
            str(cluster["external_id"])
            for cluster in latest.get("clusters", [])
            if cluster.get("external_id")
        )) or target_ids
    schedule = ScheduleDefinition(
        schedule_id="daily-standard-lab",
        name="Daily Standard Lab Preview",
        profile=default_profile(),
        target_cluster_ids=target_ids,
        recurrence=Recurrence.DAILY,
        start_time="06:00",
    )
    return build_schedule_preview(schedule, now=datetime.now(UTC), active_locks=active_locks or [])


def preview_schedule(schedule: ScheduleDefinition, active_locks: list[ActiveClusterLock] | None = None) -> SchedulePreview:
    return build_schedule_preview(schedule, now=datetime.now(UTC), active_locks=active_locks or [])
