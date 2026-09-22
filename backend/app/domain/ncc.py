from __future__ import annotations

from enum import StrEnum
from hashlib import sha256
import re

from pydantic import BaseModel, Field

from app.domain.status import HealthStatus


class NccProfileState(StrEnum):
    APPROVED = "approved"
    DISABLED = "disabled"


class NccSeverity(StrEnum):
    PASS = "PASS"
    INFO = "INFO"
    WARN = "WARN"
    FAIL = "FAIL"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


class NccCommandProfile(BaseModel):
    profile_id: str
    name: str
    command: tuple[str, ...]
    state: NccProfileState = NccProfileState.APPROVED
    timeout_minutes: int = 30
    description: str
    source: str

    @property
    def command_display(self) -> str:
        return " ".join(self.command)

    @property
    def definition_hash(self) -> str:
        payload = "|".join(self.command) + f"|timeout={self.timeout_minutes}|state={self.state}"
        return sha256(payload.encode("utf-8")).hexdigest()


class NccRunRequest(BaseModel):
    profile_id: str
    cluster_id: str


class NccRunPlan(BaseModel):
    profile: NccCommandProfile
    cluster_id: str
    selected_cvm: str | None
    status: str
    reason: str
    ncc_enabled: bool
    ssh_enabled: bool
    command_hash: str
    warnings: list[str] = Field(default_factory=list)


class ParsedNccCheck(BaseModel):
    severity: NccSeverity
    check_name: str
    message: str
    kb: str | None = None


class ParsedNccOutput(BaseModel):
    status: HealthStatus
    checks: list[ParsedNccCheck]
    parser_version: str = "ncc-parser-0.1"
    summary: str


def approved_ncc_profiles() -> dict[str, NccCommandProfile]:
    full = NccCommandProfile(
        profile_id="full-run-all",
        name="Full NCC Run All",
        command=("ncc", "health_checks", "run_all"),
        timeout_minutes=30,
        description="Full NCC health check profile. Execution remains gated until lab approval.",
        source="Work package baseline and Nutanix operational references for ncc health_checks run_all.",
    )
    return {full.profile_id: full}


def parse_ncc_output(output: str) -> ParsedNccOutput:
    checks = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parsed = parse_ncc_line(line)
        if parsed:
            checks.append(parsed)

    if not checks:
        return ParsedNccOutput(
            status=HealthStatus.UNKNOWN,
            checks=[],
            summary="NCC output did not contain recognizable health-check result lines.",
        )

    severities = {check.severity for check in checks}
    if severities & {NccSeverity.FAIL, NccSeverity.ERROR}:
        status = HealthStatus.CRITICAL
    elif NccSeverity.UNKNOWN in severities:
        status = HealthStatus.UNKNOWN
    elif NccSeverity.WARN in severities:
        status = HealthStatus.WARNING
    else:
        status = HealthStatus.HEALTHY

    return ParsedNccOutput(
        status=status,
        checks=checks,
        summary=f"Parsed {len(checks)} NCC check result line(s).",
    )


def parse_ncc_line(line: str) -> ParsedNccCheck | None:
    match = re.match(r"^(PASS|INFO|WARN|FAIL|ERROR|UNKNOWN)\s*[:\-]\s*(.+)$", line, re.IGNORECASE)
    if not match:
        return None
    severity = NccSeverity(match.group(1).upper())
    remainder = match.group(2).strip()
    kb_match = re.search(r"\bKB\s*([0-9]+)\b", remainder, re.IGNORECASE)
    kb = kb_match.group(1) if kb_match else None
    check_name = remainder.split(":", 1)[0].strip() if ":" in remainder else remainder[:80]
    return ParsedNccCheck(severity=severity, check_name=check_name, message=remainder, kb=kb)

