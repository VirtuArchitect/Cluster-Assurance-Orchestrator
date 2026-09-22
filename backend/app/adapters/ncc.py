from app.core.config import Settings
from app.domain.ncc import NccRunPlan, approved_ncc_profiles


class NccDisabledError(RuntimeError):
    pass


class NccRunner:
    """Privileged NCC adapter gate. Transport execution is intentionally absent in Phase 5."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def assert_enabled(self) -> None:
        if not self.settings.enable_ncc or not self.settings.enable_ssh:
            raise NccDisabledError("NCC and SSH are disabled until the lab gate is approved")
        if self.settings.demo_mode:
            raise NccDisabledError("demo mode cannot execute NCC")

    def build_plan(self, profile_id: str, cluster_id: str, selected_cvm: str | None = None) -> NccRunPlan:
        profiles = approved_ncc_profiles()
        if profile_id not in profiles:
            raise ValueError("Unknown NCC command profile")
        profile = profiles[profile_id]
        enabled = self.settings.enable_ncc and self.settings.enable_ssh and not self.settings.demo_mode
        return NccRunPlan(
            profile=profile,
            cluster_id=cluster_id,
            selected_cvm=selected_cvm,
            status="ready" if enabled else "blocked",
            reason=(
                "NCC and SSH gates are enabled; transport execution is still pending lab approval."
                if enabled
                else "NCC/SSH execution is disabled. This plan is allowlist validation only."
            ),
            ncc_enabled=self.settings.enable_ncc,
            ssh_enabled=self.settings.enable_ssh,
            command_hash=profile.definition_hash,
            warnings=[
                "The browser selects a profile identifier only, never command text.",
                "No SSH transport is implemented in this phase.",
                "No files, packages, agents or scheduler entries are installed on CVMs.",
            ],
        )
