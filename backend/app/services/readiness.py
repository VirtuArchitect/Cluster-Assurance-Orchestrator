from __future__ import annotations

from app.core.config import Settings
from app.domain.readiness import GateStatus, ReadinessGate, SecurityReadinessReport, default_rbac_matrix


def build_readiness_report(settings: Settings) -> SecurityReadinessReport:
    gates = [
        ReadinessGate(
            gate_id="tls-mode",
            name="TLS verification",
            status=GateStatus.PASS if settings.tls_mode == "strict" else GateStatus.WARNING,
            summary=(
                "Strict TLS verification is active."
                if settings.tls_mode == "strict"
                else "Lab evidence was captured with certificate verification bypassed."
            ),
            evidence=["CAO_TLS_MODE"],
        ),
        ReadinessGate(
            gate_id="read-only",
            name="Read-only infrastructure posture",
            status=GateStatus.PASS if settings.read_only_mode else GateStatus.BLOCKED,
            summary="Infrastructure adapters are limited to read-only collection.",
            evidence=["CAO_READ_ONLY_MODE"],
        ),
        ReadinessGate(
            gate_id="ncc-transport",
            name="NCC execution transport",
            status=GateStatus.PLANNED if not settings.enable_ncc else GateStatus.WARNING,
            summary="NCC is implemented as an allowlisted plan only; SSH execution remains gated.",
            evidence=["/api/v1/ncc/plan"],
        ),
        ReadinessGate(
            gate_id="rbac",
            name="Role-based access model",
            status=GateStatus.PASS,
            summary="Bearer sessions and role permissions protect administrative, evidence and run-control APIs.",
            evidence=["/api/v1/auth/login", "/api/v1/auth/me", "/api/v1/rbac/roles"],
        ),
        ReadinessGate(
            gate_id="integrations",
            name="Outbound integrations",
            status=GateStatus.PLANNED,
            summary="Checkmk, ServiceNow, email and webhook adapters are defined but disabled.",
            evidence=["/api/v1/integrations/status"],
        ),
        ReadinessGate(
            gate_id="backup-restore",
            name="Backup and restore",
            status=GateStatus.WARNING,
            summary="Evidence retention, archive export and restore-drill APIs are implemented; external backup remains an operations task.",
            evidence=["/api/v1/evidence/retention", "/api/v1/evidence/archive/export", "/api/v1/evidence/restore-drill"],
        ),
        ReadinessGate(
            gate_id="uat",
            name="Controlled UAT",
            status=GateStatus.PLANNED,
            summary="Controlled UAT is required before production approval claims.",
            evidence=["docs/lab-validation-plan.md"],
        ),
    ]
    return SecurityReadinessReport(
        maturity="lab validated" if settings.environment == "lab" else "simulated",
        gates=gates,
        roles=default_rbac_matrix(),
        open_risks=[
            "Shared or production deployment still requires TLS termination, secret rotation and external backup procedures.",
            "Outbound integrations are not enabled.",
            "NCC SSH execution is deliberately unavailable.",
            "Controlled UAT remains open before production approval claims.",
        ],
    )
