from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class GateStatus(StrEnum):
    PASS = "PASS"
    WARNING = "WARNING"
    PLANNED = "PLANNED"
    BLOCKED = "BLOCKED"


class RolePermission(BaseModel):
    permission: str
    viewer: bool
    operator: bool
    admin: bool


class ReadinessGate(BaseModel):
    gate_id: str
    name: str
    status: GateStatus
    summary: str
    evidence: list[str] = Field(default_factory=list)


class SecurityReadinessReport(BaseModel):
    maturity: str
    gates: list[ReadinessGate]
    roles: list[RolePermission]
    open_risks: list[str] = Field(default_factory=list)


def default_rbac_matrix() -> list[RolePermission]:
    return [
        RolePermission(permission="view_dashboard", viewer=True, operator=True, admin=True),
        RolePermission(permission="view_evidence", viewer=True, operator=True, admin=True),
        RolePermission(permission="run_read_only_inventory", viewer=False, operator=True, admin=True),
        RolePermission(permission="manage_schedules", viewer=False, operator=True, admin=True),
        RolePermission(permission="plan_ncc_runs", viewer=False, operator=True, admin=True),
        RolePermission(permission="enable_integrations", viewer=False, operator=False, admin=True),
        RolePermission(permission="manage_security_settings", viewer=False, operator=False, admin=True),
    ]
