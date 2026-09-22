from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from app.core.config import Settings
from app.services.admin_store import AdminStore


BACKUP_SUFFIX = ".dump"


@dataclass(frozen=True)
class BackupFile:
    name: str
    created_at: str
    size_bytes: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "created_at": self.created_at,
            "size_bytes": self.size_bytes,
            "size_label": format_bytes(self.size_bytes),
        }


def storage_status(settings: Settings, store: AdminStore) -> dict[str, Any]:
    healthy = store.check_health()
    return {
        "backend": store.storage_backend,
        "status": "healthy" if healthy else "unhealthy",
        "data_directory": "configured locally",
        "database_location": safe_database_location(settings.admin_database_url) if settings.admin_database_url else "local SQLite fallback",
        "credentials_hidden": True,
        "retention": {
            "audit_days": settings.audit_retention_days,
            "execution_days": settings.execution_retention_days,
            "evidence_days": settings.evidence_retention_days,
            "evidence_minimum_runs": settings.evidence_retention_min_runs,
        },
        "postgres_enabled": store.storage_backend == "postgres",
        "backup_supported": store.storage_backend == "postgres",
        "backups": [backup.as_dict() for backup in list_database_backups(settings)],
    }


def create_database_backup(settings: Settings, store: AdminStore) -> dict[str, Any]:
    if store.storage_backend != "postgres":
        raise ValueError("Postgres backup is only available when CAO_ADMIN_DATABASE_URL is configured")

    backup_dir = database_backup_dir(settings)
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"cluster-assurance-{timestamp}.dump"
    backup_path.write_text(build_logical_sql_export(store), encoding="utf-8")
    backup = backup_file_from_path(backup_path)
    return backup.as_dict()


def get_database_backup(settings: Settings, backup_name: str) -> Path:
    if Path(backup_name).name != backup_name or not backup_name.endswith(BACKUP_SUFFIX):
        raise FileNotFoundError(backup_name)
    path = database_backup_dir(settings) / backup_name
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(backup_name)
    return path


def list_database_backups(settings: Settings) -> list[BackupFile]:
    backup_dir = database_backup_dir(settings)
    if not backup_dir.exists():
        return []
    return [
        backup_file_from_path(path)
        for path in sorted(backup_dir.glob(f"*{BACKUP_SUFFIX}"), key=lambda item: item.stat().st_mtime, reverse=True)
        if path.is_file()
    ]


def build_logical_sql_export(store: AdminStore) -> str:
    exported_at = datetime.now(UTC).isoformat()
    lines = [
        "-- Cluster Assurance Orchestrator PostgreSQL logical export",
        f"-- Exported at: {exported_at}",
        "-- Credentials are not included beyond already sealed application secrets.",
        "BEGIN;",
    ]
    with store.connect() as connection:
        table_rows = list(connection.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        ))
        for table_row in table_rows:
            table_name = str(table_row["table_name"])
            columns = [
                str(column_row["column_name"])
                for column_row in connection.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = ?
                    ORDER BY ordinal_position
                    """,
                    (table_name,),
                )
            ]
            if not columns:
                continue
            lines.append("")
            lines.append(f"-- table: {quote_identifier(table_name)}")
            rows = list(connection.execute(f"SELECT * FROM {quote_identifier(table_name)} ORDER BY 1"))
            for row in rows:
                values = ", ".join(sql_literal(row[column]) for column in columns)
                column_sql = ", ".join(quote_identifier(column) for column in columns)
                lines.append(f"INSERT INTO {quote_identifier(table_name)} ({column_sql}) VALUES ({values}) ON CONFLICT DO NOTHING;")
    lines.append("COMMIT;")
    lines.append("")
    return "\n".join(lines)


def database_backup_dir(settings: Settings) -> Path:
    return Path(settings.evidence_dir) / "database-backups"


def backup_file_from_path(path: Path) -> BackupFile:
    stat = path.stat()
    created_at = datetime.fromtimestamp(stat.st_mtime, UTC).isoformat()
    return BackupFile(name=path.name, created_at=created_at, size_bytes=stat.st_size)


def safe_database_location(database_url: str) -> str:
    parsed = urlsplit(database_url)
    host = parsed.hostname or "postgres"
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path or ""
    return f"{parsed.scheme}://{host}{port}{path}"


def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int | float):
        return str(value)
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size / (1024 * 1024):.1f} MB"
