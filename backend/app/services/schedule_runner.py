from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.adapters.nutanix import AdapterDisabledError
from app.core.config import Settings
from app.domain.demo import build_demo_run
from app.domain.scheduling import (
    ActiveClusterLock,
    MisfirePolicy,
    ScheduleDefinition,
    idempotency_key,
    load_zone,
    parse_time,
)
from app.services.inventory_run import run_inventory, write_inventory_evidence
from app.services.admin_store import AdminStore, Principal


def run_due_schedules(settings: Settings, store: AdminStore, actor: Principal) -> dict[str, Any]:
    now = datetime.now(UTC)
    results = []
    for row in store.list_schedules():
        schedule = ScheduleDefinition.model_validate(row["definition"])
        due_at = due_occurrence(schedule, now)
        if due_at is None:
            continue
        results.append(run_schedule_occurrence(settings, store, actor, schedule, due_at))
    return {
        "checked_at": now.isoformat(),
        "due_schedules": len(results),
        "results": results,
    }


def run_schedule_now(settings: Settings, store: AdminStore, actor: Principal, schedule: ScheduleDefinition) -> dict[str, Any]:
    return run_schedule_occurrence(settings, store, actor, schedule, datetime.now(UTC))


def run_schedule_occurrence(
    settings: Settings,
    store: AdminStore,
    actor: Principal,
    schedule: ScheduleDefinition,
    occurrence_at: datetime,
) -> dict[str, Any]:
    key = idempotency_key(schedule.schedule_id, schedule.profile.profile_version_id, occurrence_at)
    if store.has_schedule_run(key):
        return {
            "schedule_id": schedule.schedule_id,
            "occurrence_at": occurrence_at.isoformat(),
            "status": "SKIPPED_DUPLICATE",
            "message": "This occurrence has already been handled.",
        }
    run_row = store.create_schedule_run(
        idempotency_key=key,
        schedule_id=schedule.schedule_id,
        occurrence_at=occurrence_at.isoformat(),
        target_cluster_ids=schedule.target_cluster_ids,
        actor_id=actor.user_id,
    )
    lock_expiry = datetime.now(UTC) + timedelta(minutes=schedule.profile.timeout_minutes)
    locks = store.acquire_schedule_locks(
        owner_run_id=run_row["id"],
        target_cluster_ids=schedule.target_cluster_ids,
        expires_at=lock_expiry.isoformat(),
    )
    if not locks["acquired"]:
        completed = store.complete_schedule_run(
            run_row["id"],
            status="SKIPPED_LOCKED",
            run_id=None,
            evidence_path=None,
            message="All target clusters already have active locks.",
        )
        store.audit("schedules.run_skipped_locked", actor.user_id, "schedule", schedule.schedule_id, {"blocked": locks["blocked"]})
        return completed

    try:
        run_settings = store.inventory_settings_from_connections()
        report = build_demo_run(settings=run_settings) if run_settings.demo_mode else run_inventory(run_settings)
        if hasattr(report, "api_dict"):
            evidence_path = write_inventory_evidence(report, run_settings.evidence_dir)
            status = str(report.status)
        else:
            evidence_path = None
            status = str(report.status)
        completed = store.complete_schedule_run(
            run_row["id"],
            status=status,
            run_id=str(report.run_id),
            evidence_path=str(evidence_path) if evidence_path else None,
            message=f"Schedule runner completed with status {status}.",
        )
        store.audit(
            "schedules.run_completed",
            actor.user_id,
            "schedule",
            schedule.schedule_id,
            {"status": status, "run_id": str(report.run_id), "targets": locks["acquired"]},
        )
        return completed
    except AdapterDisabledError as error:
        completed = store.complete_schedule_run(
            run_row["id"],
            status="FAILED",
            run_id=None,
            evidence_path=None,
            message=str(error),
        )
        store.audit("schedules.run_failed", actor.user_id, "schedule", schedule.schedule_id, {"error": str(error)})
        return completed
    finally:
        store.release_schedule_locks(run_row["id"])


def due_occurrence(schedule: ScheduleDefinition, now: datetime) -> datetime | None:
    if not schedule.enabled or schedule.recurrence == "on_demand":
        return None
    zone = load_zone(schedule.timezone)
    local_now = now.astimezone(zone)
    hour, minute = parse_time(schedule.start_time)
    candidate = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if schedule.recurrence == "weekly":
        days_back = (candidate.weekday() - schedule.weekly_day) % 7
        candidate = candidate - timedelta(days=days_back)
    occurrence_at = candidate.astimezone(UTC)
    if occurrence_at > now:
        return None
    age_minutes = (now - occurrence_at).total_seconds() / 60
    if age_minutes <= schedule.misfire_grace_minutes:
        return occurrence_at
    if schedule.misfire_policy == MisfirePolicy.MARK_MISSED:
        return occurrence_at
    return None


def active_locks_for_preview(store: AdminStore) -> list[ActiveClusterLock]:
    return [
        ActiveClusterLock(
            cluster_id=row["cluster_id"],
            owner_run_id=row["owner_run_id"],
            expires_at=datetime.fromisoformat(row["expires_at"]),
        )
        for row in store.get_active_locks()
    ]
