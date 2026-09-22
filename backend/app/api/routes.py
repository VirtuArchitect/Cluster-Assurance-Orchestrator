from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.adapters.nutanix import AdapterDisabledError
from app.domain.catalogue import default_catalogue
from app.domain.demo import build_demo_run
from app.services.lab_discovery import run_lab_discovery
from app.services.inventory_run import inventory_run_history, read_latest_inventory_evidence, run_inventory, write_inventory_evidence
from app.domain.scheduling import ScheduleDefinition
from app.services.scheduling import default_schedule_for_latest_inventory, preview_schedule
from app.services.schedule_runner import active_locks_for_preview, run_due_schedules, run_schedule_now
from app.domain.ncc import NccRunRequest, parse_ncc_output
from app.services.ncc import build_ncc_plan, list_ncc_profiles
from app.services.evidence_manifest import latest_manifest
from app.services.evidence_ops import create_evidence_archive, prune_evidence, restore_drill, retention_report
from app.services.integrations import integration_status
from app.services.readiness import build_readiness_report
from app.services.support_status import build_support_status
from app.services.alerting import alert_status, send_test_alert
from app.services.admin_store import AdminStore, Principal

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class RoleRequest(BaseModel):
    name: str = Field(min_length=1)
    permissions: list[str] = Field(default_factory=list)


class UserRequest(BaseModel):
    username: str = Field(min_length=1)
    name: str = Field(min_length=1)
    email: str = Field(min_length=1)
    role_id: str = Field(min_length=1)
    status: str = "Active"
    password: str | None = None


class PasswordRequest(BaseModel):
    password: str = Field(min_length=1)


class ConnectionRequest(BaseModel):
    name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    url: str = Field(min_length=1)
    username: str = ""
    password: str | None = None
    tls_mode: str = "strict"


def admin_store(request: Request) -> AdminStore:
    store = getattr(request.app.state, "admin_store", None)
    if store is None:
        store = AdminStore(request.app.state.settings)
        request.app.state.admin_store = store
    return store


def current_token(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    return authorization.removeprefix("Bearer ").strip()


def current_principal(
    token: Annotated[str, Depends(current_token)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> Principal:
    principal = store.principal_from_token(token)
    if principal is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return principal


def require_admin(principal: Annotated[Principal, Depends(current_principal)]) -> Principal:
    if not principal.has_permission("all_permissions"):
        raise HTTPException(status_code=403, detail="Admin permission required")
    return principal


def require_permission(principal: Principal, permission: str) -> None:
    if not principal.has_permission(permission):
        raise HTTPException(status_code=403, detail=f"{permission} permission required")


@router.post("/auth/login")
def auth_login(payload: LoginRequest, request: Request, store: Annotated[AdminStore, Depends(admin_store)]) -> dict[str, Any]:
    try:
        return store.login(payload.username, payload.password, request.client.host if request.client else "")
    except ValueError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error


@router.post("/auth/logout")
def auth_logout(
    token: Annotated[str, Depends(current_token)],
    principal: Annotated[Principal, Depends(current_principal)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> dict[str, str]:
    store.logout(token, principal)
    return {"status": "ok"}


@router.get("/auth/me")
def auth_me(principal: Annotated[Principal, Depends(current_principal)]) -> dict[str, Any]:
    return {
        "id": principal.user_id,
        "username": principal.username,
        "role_id": principal.role_id,
        "role_name": principal.role_name,
        "permissions": list(principal.permissions),
    }


@router.get("/rbac/roles")
def rbac_roles(
    store: Annotated[AdminStore, Depends(admin_store)],
    _: Annotated[Principal, Depends(current_principal)],
) -> list[dict[str, Any]]:
    return store.list_roles()


@router.post("/rbac/roles")
def rbac_create_role(
    payload: RoleRequest,
    actor: Annotated[Principal, Depends(require_admin)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> dict[str, Any]:
    return store.create_role(payload.name, payload.permissions, actor)


@router.put("/rbac/roles/{role_id}")
def rbac_update_role(
    role_id: str,
    payload: RoleRequest,
    actor: Annotated[Principal, Depends(require_admin)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> dict[str, Any]:
    try:
        return store.update_role(role_id, payload.name, payload.permissions, actor)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Role not found") from error


@router.delete("/rbac/roles/{role_id}")
def rbac_delete_role(
    role_id: str,
    actor: Annotated[Principal, Depends(require_admin)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> dict[str, str]:
    try:
        store.delete_role(role_id, actor)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Role not found") from error
    return {"status": "deleted"}


@router.get("/rbac/users")
def rbac_users(
    store: Annotated[AdminStore, Depends(admin_store)],
    _: Annotated[Principal, Depends(current_principal)],
) -> list[dict[str, Any]]:
    return store.list_users()


@router.post("/rbac/users")
def rbac_create_user(
    payload: UserRequest,
    actor: Annotated[Principal, Depends(require_admin)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> dict[str, Any]:
    if not payload.password:
        raise HTTPException(status_code=422, detail="Password is required")
    return store.create_user(payload.model_dump(), actor)


@router.put("/rbac/users/{user_id}")
def rbac_update_user(
    user_id: str,
    payload: UserRequest,
    actor: Annotated[Principal, Depends(require_admin)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> dict[str, Any]:
    try:
        return store.update_user(user_id, payload.model_dump(), actor)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="User not found") from error


@router.post("/rbac/users/{user_id}/password")
def rbac_set_user_password(
    user_id: str,
    payload: PasswordRequest,
    actor: Annotated[Principal, Depends(require_admin)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> dict[str, Any]:
    try:
        return store.set_user_password(user_id, payload.password, actor)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="User not found") from error


@router.delete("/rbac/users/{user_id}")
def rbac_delete_user(
    user_id: str,
    actor: Annotated[Principal, Depends(require_admin)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> dict[str, str]:
    try:
        store.delete_user(user_id, actor)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="User not found") from error
    return {"status": "deleted"}


@router.get("/connections")
def connections_list(
    store: Annotated[AdminStore, Depends(admin_store)],
    _: Annotated[Principal, Depends(current_principal)],
) -> list[dict[str, Any]]:
    return store.list_connections()


@router.post("/connections")
def connections_create(
    payload: ConnectionRequest,
    actor: Annotated[Principal, Depends(require_admin)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> dict[str, Any]:
    return store.upsert_connection(payload.model_dump(), actor)


@router.put("/connections/{connection_id}")
def connections_update(
    connection_id: str,
    payload: ConnectionRequest,
    actor: Annotated[Principal, Depends(require_admin)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> dict[str, Any]:
    try:
        return store.upsert_connection(payload.model_dump(), actor, connection_id=connection_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Connection not found") from error


@router.post("/connections/{connection_id}/test")
def connections_test(
    connection_id: str,
    actor: Annotated[Principal, Depends(require_admin)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> dict[str, Any]:
    try:
        return store.test_connection(connection_id, actor)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Connection not found") from error


@router.delete("/connections/{connection_id}")
def connections_delete(
    connection_id: str,
    actor: Annotated[Principal, Depends(require_admin)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> dict[str, str]:
    try:
        store.delete_connection(connection_id, actor)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Connection not found") from error
    return {"status": "deleted"}


@router.get("/audit/events")
def audit_events(
    store: Annotated[AdminStore, Depends(admin_store)],
    _: Annotated[Principal, Depends(require_admin)],
    limit: int = 100,
) -> list[dict[str, Any]]:
    return store.list_audit_events(limit=max(1, min(limit, 250)))


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    return {
        "status": "ok",
        "environment": settings.environment,
        "demoMode": settings.demo_mode,
        "readOnlyMode": settings.read_only_mode,
        "nccEnabled": settings.enable_ncc,
        "sshEnabled": settings.enable_ssh,
    }


@router.get("/support/status")
def support_status(
    request: Request,
    store: Annotated[AdminStore, Depends(admin_store)],
    _: Annotated[Principal, Depends(current_principal)],
) -> dict[str, object]:
    return build_support_status(store.inventory_settings_from_connections(), str(request.base_url))


@router.get("/catalogue")
def catalogue(_: Annotated[Principal, Depends(current_principal)]) -> dict[str, object]:
    checks = default_catalogue()
    return {
        "version": checks.version,
        "checks": [check.model_dump(mode="json") for check in checks.checks],
    }


@router.post("/runs/demo")
def demo_run(
    request: Request,
    actor: Annotated[Principal, Depends(current_principal)],
) -> dict[str, object]:
    require_permission(actor, "run_read_only_inventory")
    settings = request.app.state.settings
    run = build_demo_run(settings=settings)
    return run.model_dump(mode="json")


@router.post("/lab/discovery")
def lab_discovery(
    request: Request,
    actor: Annotated[Principal, Depends(current_principal)],
) -> dict[str, object]:
    require_permission(actor, "run_read_only_inventory")
    settings = request.app.state.settings
    try:
        report = run_lab_discovery(settings=settings)
    except AdapterDisabledError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return report.model_dump(mode="json")


@router.post("/lab/inventory-runs")
def lab_inventory_run(
    request: Request,
    actor: Annotated[Principal, Depends(current_principal)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> dict[str, object]:
    require_permission(actor, "run_read_only_inventory")
    settings = store.inventory_settings_from_connections()
    try:
        report = run_inventory(settings=settings)
    except AdapterDisabledError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return report.api_dict()


@router.post("/health-runs/manual")
def manual_health_run(
    request: Request,
    actor: Annotated[Principal, Depends(current_principal)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> dict[str, object]:
    require_permission(actor, "run_read_only_inventory")
    settings = store.inventory_settings_from_connections()
    try:
        report = build_demo_run(settings=settings) if settings.demo_mode else run_inventory(settings=settings)
    except AdapterDisabledError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if hasattr(report, "api_dict"):
        payload = report.api_dict()
        evidence_path = write_inventory_evidence(report, settings.evidence_dir)
    else:
        payload = report.model_dump(mode="json")
        evidence_dir = Path(settings.evidence_dir)
        evidence_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        evidence_path = evidence_dir / f"manual-health-run-{timestamp}.json"
        evidence_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    store.audit(
        "health_runs.manual_started",
        actor.user_id,
        "inventory_run",
        report.run_id,
        {"status": str(report.status), "evidence": str(evidence_path)},
    )
    return payload | {"evidence_path": str(evidence_path)}


@router.get("/lab/inventory-runs/latest")
def latest_lab_inventory_run(
    request: Request,
    actor: Annotated[Principal, Depends(current_principal)],
) -> dict[str, object]:
    require_permission(actor, "view_evidence")
    settings = request.app.state.settings
    latest = read_latest_inventory_evidence(settings.evidence_dir)
    if latest is None:
        raise HTTPException(status_code=404, detail="No local inventory evidence found")
    return latest


@router.get("/health-runs/history")
def health_run_history(
    request: Request,
    actor: Annotated[Principal, Depends(current_principal)],
    limit: int = 20,
) -> list[dict[str, object]]:
    require_permission(actor, "view_evidence")
    settings = request.app.state.settings
    return inventory_run_history(settings.evidence_dir, limit=max(1, min(limit, 100)))


@router.get("/schedules/preview/default")
def default_schedule_preview(
    request: Request,
    _: Annotated[Principal, Depends(current_principal)],
) -> dict[str, object]:
    settings = request.app.state.settings
    return default_schedule_for_latest_inventory(settings.evidence_dir).model_dump(mode="json")


@router.post("/schedules/preview")
def schedule_preview(
    schedule: ScheduleDefinition,
    actor: Annotated[Principal, Depends(current_principal)],
) -> dict[str, object]:
    require_permission(actor, "manage_schedules")
    return preview_schedule(schedule).model_dump(mode="json")


@router.get("/schedules")
def schedules_list(
    store: Annotated[AdminStore, Depends(admin_store)],
    _: Annotated[Principal, Depends(current_principal)],
) -> list[dict[str, Any]]:
    return store.list_schedules()


@router.post("/schedules")
def schedules_create(
    schedule: ScheduleDefinition,
    actor: Annotated[Principal, Depends(current_principal)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> dict[str, Any]:
    require_permission(actor, "manage_schedules")
    return store.upsert_schedule(schedule, actor)


@router.put("/schedules/{schedule_id}")
def schedules_update(
    schedule_id: str,
    schedule: ScheduleDefinition,
    actor: Annotated[Principal, Depends(current_principal)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> dict[str, Any]:
    require_permission(actor, "manage_schedules")
    try:
        return store.upsert_schedule(schedule, actor, schedule_id=schedule_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Schedule not found") from error


@router.delete("/schedules/{schedule_id}")
def schedules_delete(
    schedule_id: str,
    actor: Annotated[Principal, Depends(current_principal)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> dict[str, str]:
    require_permission(actor, "manage_schedules")
    try:
        store.delete_schedule(schedule_id, actor)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Schedule not found") from error
    return {"status": "deleted"}


@router.get("/schedules/runs/history")
def schedules_run_history(
    store: Annotated[AdminStore, Depends(admin_store)],
    actor: Annotated[Principal, Depends(current_principal)],
    limit: int = 50,
) -> list[dict[str, Any]]:
    require_permission(actor, "manage_schedules")
    return store.list_schedule_runs(limit=max(1, min(limit, 250)))


@router.post("/schedules/run-due")
def schedules_run_due(
    request: Request,
    actor: Annotated[Principal, Depends(current_principal)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> dict[str, Any]:
    require_permission(actor, "manage_schedules")
    return run_due_schedules(request.app.state.settings, store, actor)


@router.post("/schedules/{schedule_id}/run-now")
def schedules_run_now(
    schedule_id: str,
    request: Request,
    actor: Annotated[Principal, Depends(current_principal)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> dict[str, Any]:
    require_permission(actor, "manage_schedules")
    try:
        schedule = store.get_schedule(schedule_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Schedule not found") from error
    return run_schedule_now(request.app.state.settings, store, actor, schedule)


@router.get("/schedules/{schedule_id}/preview")
def schedules_stored_preview(
    schedule_id: str,
    store: Annotated[AdminStore, Depends(admin_store)],
    _: Annotated[Principal, Depends(current_principal)],
) -> dict[str, object]:
    try:
        schedule = store.get_schedule(schedule_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Schedule not found") from error
    preview = preview_schedule(schedule)
    preview.active_locks = active_locks_for_preview(store)
    return preview.model_dump(mode="json")


@router.get("/ncc/profiles")
def ncc_profiles(_: Annotated[Principal, Depends(current_principal)]) -> dict[str, object]:
    return list_ncc_profiles()


@router.post("/ncc/plan")
def ncc_plan(
    request: Request,
    payload: NccRunRequest,
    actor: Annotated[Principal, Depends(current_principal)],
) -> dict[str, object]:
    require_permission(actor, "plan_ncc_runs")
    try:
        return build_ncc_plan(request.app.state.settings, payload).model_dump(mode="json")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/ncc/parse")
def ncc_parse(
    payload: dict[str, str],
    actor: Annotated[Principal, Depends(current_principal)],
) -> dict[str, object]:
    require_permission(actor, "plan_ncc_runs")
    output = payload.get("output", "")
    return parse_ncc_output(output).model_dump(mode="json")


@router.get("/evidence/manifest/latest")
def latest_evidence_manifest(
    request: Request,
    actor: Annotated[Principal, Depends(current_principal)],
) -> dict[str, object]:
    require_permission(actor, "view_evidence")
    settings = request.app.state.settings
    manifest = latest_manifest(settings.evidence_dir)
    if manifest is None:
        raise HTTPException(status_code=404, detail="No local inventory evidence found")
    payload = manifest.model_dump(mode="json")
    payload["manifest_sha256"] = manifest.stable_hash()
    return payload


@router.get("/evidence/retention")
def evidence_retention(
    request: Request,
    actor: Annotated[Principal, Depends(require_admin)],
) -> dict[str, Any]:
    return retention_report(request.app.state.settings)


@router.post("/evidence/retention/prune")
def evidence_retention_prune(
    request: Request,
    actor: Annotated[Principal, Depends(require_admin)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> dict[str, Any]:
    result = prune_evidence(request.app.state.settings)
    store.audit("evidence.pruned", actor.user_id, "evidence", "retention", {"deleted": len(result.get("deleted_files", []))})
    return result


@router.post("/evidence/archive/export")
def evidence_archive_export(
    request: Request,
    actor: Annotated[Principal, Depends(require_admin)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> dict[str, Any]:
    result = create_evidence_archive(request.app.state.settings)
    store.audit("evidence.archive_exported", actor.user_id, "evidence", "archive", {"archive_path": result["archive_path"]})
    return result


@router.post("/evidence/restore-drill")
def evidence_restore_drill(
    request: Request,
    actor: Annotated[Principal, Depends(require_admin)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> dict[str, Any]:
    result = restore_drill(request.app.state.settings)
    store.audit("evidence.restore_drill", actor.user_id, "evidence", "archive", {"status": result["status"]})
    return result


@router.get("/integrations/status")
def integrations_status(_: Annotated[Principal, Depends(current_principal)]) -> dict[str, object]:
    return integration_status().model_dump(mode="json")


@router.get("/security/readiness")
def security_readiness(
    request: Request,
    _: Annotated[Principal, Depends(current_principal)],
) -> dict[str, object]:
    return build_readiness_report(request.app.state.settings).model_dump(mode="json")


@router.get("/alerts/status")
def alerts_status(
    request: Request,
    actor: Annotated[Principal, Depends(current_principal)],
) -> dict[str, Any]:
    require_permission(actor, "view_evidence")
    return alert_status(request.app.state.settings)


@router.post("/alerts/test")
def alerts_test(
    request: Request,
    actor: Annotated[Principal, Depends(require_admin)],
    store: Annotated[AdminStore, Depends(admin_store)],
) -> dict[str, Any]:
    result = send_test_alert(request.app.state.settings)
    store.audit("alerts.tested", actor.user_id, "alert", "test", {"delivery": result.get("delivery")})
    return result
