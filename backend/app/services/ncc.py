from __future__ import annotations

from app.adapters.ncc import NccRunner
from app.core.config import Settings
from app.domain.ncc import NccRunPlan, NccRunRequest, approved_ncc_profiles


def list_ncc_profiles() -> dict[str, object]:
    profiles = approved_ncc_profiles()
    return {
        "profiles": [profile.model_dump(mode="json") | {"command_display": profile.command_display} for profile in profiles.values()],
        "transport": "not_implemented",
        "execution": "gated",
    }


def build_ncc_plan(settings: Settings, request: NccRunRequest) -> NccRunPlan:
    return NccRunner(settings).build_plan(
        profile_id=request.profile_id,
        cluster_id=request.cluster_id,
    )
