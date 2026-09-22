from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


SECRET_KEYS = ("PASSWORD", "TOKEN", "SECRET", "COOKIE", "AUTHORIZATION", "DATABASE_URL")


@dataclass(frozen=True)
class Settings:
    environment: str = "dev"
    config_source: str = "defaults+environment"
    demo_mode: bool = True
    timezone: str = "Europe/Berlin"
    pc_url: str = ""
    pc_username: str = ""
    pc_password: str = ""
    pe_url: str = ""
    pe_username: str = ""
    pe_password: str = ""
    tls_mode: str = "strict"
    custom_ca_bundle: str = ""
    read_only_mode: bool = True
    enable_ncc: bool = False
    enable_ssh: bool = False
    global_concurrency: int = 2
    per_cluster_concurrency: int = 1
    evidence_dir: str = "./evidence/lab"
    admin_db_path: str = ""
    admin_database_url: str = ""
    auth_secret: str = "dev-local-auth-secret-change-me"
    bootstrap_admin_password: str = "ChangeMe123!"
    evidence_retention_days: int = 30
    evidence_retention_min_runs: int = 10
    audit_retention_days: int = 90
    execution_retention_days: int = 180
    enable_alerts: bool = False
    alert_email_to: str = ""
    alert_webhook_url: str = ""
    log_level: str = "INFO"

    def validate_safety(self) -> None:
        if self.environment == "production" and self.tls_mode == "insecure_skip_verify":
            raise ValueError("insecure TLS mode is not allowed in production")
        if self.demo_mode and (self.enable_ncc or self.enable_ssh):
            raise ValueError("demo mode cannot enable NCC or SSH")
        if self.enable_ncc and not self.enable_ssh:
            raise ValueError("NCC execution requires the SSH adapter gate")
        if self.global_concurrency < 1 or self.per_cluster_concurrency < 1:
            raise ValueError("concurrency limits must be positive")
        if self.evidence_retention_days < 1 or self.evidence_retention_min_runs < 1:
            raise ValueError("evidence retention limits must be positive")
        if self.audit_retention_days < 1 or self.execution_retention_days < 1:
            raise ValueError("operational retention limits must be positive")

    def redacted(self) -> dict[str, object]:
        output = self.__dict__.copy()
        for key in list(output):
            if is_secret_key(key):
                output[key] = "***REDACTED***" if output[key] else ""
        return output


def is_secret_key(key: str) -> bool:
    upper = key.upper()
    return any(marker in upper for marker in SECRET_KEYS)


def redact_mapping(values: dict[str, object]) -> dict[str, object]:
    redacted: dict[str, object] = {}
    for key, value in values.items():
        if is_secret_key(key):
            redacted[key] = "***REDACTED***" if value else ""
        else:
            redacted[key] = value
    return redacted


def load_settings(env_file: str | Path | None = None) -> Settings:
    values = {}
    if env_file:
        values.update(parse_env_file(Path(env_file)))
    values.update(os.environ)

    settings = Settings(
        environment=str(values.get("CAO_ENVIRONMENT", "dev")),
        config_source=str(values.get("CAO_CONFIG_SOURCE", f"env-file:{env_file}" if env_file else "defaults+environment")),
        demo_mode=parse_bool(values.get("CAO_DEMO_MODE", "true")),
        timezone=str(values.get("CAO_TIMEZONE", "Europe/Berlin")),
        pc_url=str(values.get("CAO_PC_URL", "")),
        pc_username=str(values.get("CAO_PC_USERNAME", "")),
        pc_password=str(values.get("CAO_PC_PASSWORD", "")),
        pe_url=str(values.get("CAO_PE_URL", "")),
        pe_username=str(values.get("CAO_PE_USERNAME", "")),
        pe_password=str(values.get("CAO_PE_PASSWORD", "")),
        tls_mode=str(values.get("CAO_TLS_MODE", "strict")),
        custom_ca_bundle=str(values.get("CAO_CUSTOM_CA_BUNDLE", "")),
        read_only_mode=parse_bool(values.get("CAO_READ_ONLY_MODE", "true")),
        enable_ncc=parse_bool(values.get("CAO_ENABLE_NCC", "false")),
        enable_ssh=parse_bool(values.get("CAO_ENABLE_SSH", "false")),
        global_concurrency=int(values.get("CAO_GLOBAL_CONCURRENCY", "2")),
        per_cluster_concurrency=int(values.get("CAO_PER_CLUSTER_CONCURRENCY", "1")),
        evidence_dir=str(values.get("CAO_EVIDENCE_DIR", "./evidence/lab")),
        admin_db_path=str(values.get("CAO_ADMIN_DB_PATH", "")),
        admin_database_url=str(values.get("CAO_ADMIN_DATABASE_URL", "")),
        auth_secret=str(values.get("CAO_AUTH_SECRET", "dev-local-auth-secret-change-me")),
        bootstrap_admin_password=str(values.get("CAO_BOOTSTRAP_ADMIN_PASSWORD", "ChangeMe123!")),
        evidence_retention_days=int(values.get("CAO_EVIDENCE_RETENTION_DAYS", "30")),
        evidence_retention_min_runs=int(values.get("CAO_EVIDENCE_RETENTION_MIN_RUNS", "10")),
        audit_retention_days=int(values.get("CAO_AUDIT_RETENTION_DAYS", "90")),
        execution_retention_days=int(values.get("CAO_EXECUTION_RETENTION_DAYS", "180")),
        enable_alerts=parse_bool(values.get("CAO_ENABLE_ALERTS", "false")),
        alert_email_to=str(values.get("CAO_ALERT_EMAIL_TO", "")),
        alert_webhook_url=str(values.get("CAO_ALERT_WEBHOOK_URL", "")),
        log_level=str(values.get("CAO_LOG_LEVEL", "INFO")),
    )
    settings.validate_safety()
    return settings


def parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def parse_env_file(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    if not path.exists():
        return parsed
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    return parsed
