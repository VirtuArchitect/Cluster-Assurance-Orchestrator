from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
import base64
import binascii
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import sqlite3
import ssl
from time import perf_counter
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import Settings
from app.domain.scheduling import ScheduleDefinition
from app.services.artifacts import public_artifact_ref
from app.services.scheduling import default_profile


SESSION_TTL_HOURS = 12
PASSWORD_ITERATIONS = 260_000


@dataclass(frozen=True)
class Principal:
    user_id: str
    username: str
    role_id: str
    role_name: str
    permissions: tuple[str, ...]

    def has_permission(self, permission: str) -> bool:
        return "all_permissions" in self.permissions or permission in self.permissions


class AdminStore:
    def __init__(self, settings: Settings):
        db_path = Path(settings.admin_db_path) if settings.admin_db_path else Path(settings.evidence_dir) / "cao-admin.sqlite3"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.settings = settings
        self._init_db()
        self._seed_defaults()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def login(self, username: str, password: str, request_ip: str = "") -> dict[str, Any]:
        with self.connect() as connection:
            user = connection.execute(
                """
                SELECT users.*, roles.name AS role_name, roles.permissions AS role_permissions
                FROM users JOIN roles ON roles.id = users.role_id
                WHERE users.username = ?
                """,
                (username.strip(),),
            ).fetchone()
            if user is None or user["status"] != "Active" or not verify_password(password, user["password_hash"]):
                self.audit("auth.login_failed", actor_id=None, target_type="user", target_id=username, details={"ip": request_ip})
                raise ValueError("Invalid username or password")

            token = secrets.token_urlsafe(32)
            token_hash = hash_token(token)
            expires_at = utcnow() + timedelta(hours=SESSION_TTL_HOURS)
            connection.execute(
                """
                INSERT INTO sessions (token_hash, user_id, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (token_hash, user["id"], utcnow_iso(), expires_at.isoformat()),
            )
            connection.execute(
                "UPDATE users SET last_login_at = ? WHERE id = ?",
                (utcnow_iso(), user["id"]),
            )
            connection.commit()
            self.audit("auth.login", actor_id=user["id"], target_type="user", target_id=user["id"], details={"ip": request_ip})
            return {"token": token, "expires_at": expires_at.isoformat(), "user": serialize_user_row(user)}

    def logout(self, token: str, principal: Principal | None = None) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))
            connection.commit()
        self.audit("auth.logout", actor_id=principal.user_id if principal else None, target_type="session", target_id="current")

    def principal_from_token(self, token: str) -> Principal | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT users.id AS user_id, users.username, users.status, roles.id AS role_id,
                       roles.name AS role_name, roles.permissions, sessions.expires_at
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                JOIN roles ON roles.id = users.role_id
                WHERE sessions.token_hash = ?
                """,
                (hash_token(token),),
            ).fetchone()
            if row is None or row["status"] != "Active":
                return None
            if datetime.fromisoformat(row["expires_at"]) <= utcnow():
                connection.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))
                connection.commit()
                return None
            return Principal(
                user_id=row["user_id"],
                username=row["username"],
                role_id=row["role_id"],
                role_name=row["role_name"],
                permissions=tuple(parse_permissions(row["permissions"])),
            )

    def list_roles(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return [serialize_role_row(row) for row in connection.execute("SELECT * FROM roles ORDER BY name")]

    def create_role(self, name: str, permissions: list[str], actor: Principal) -> dict[str, Any]:
        role_id = f"role-{secrets.token_hex(8)}"
        now = utcnow_iso()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO roles (id, name, permissions, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (role_id, name.strip(), normalize_permissions(permissions), now, now),
            )
            row = connection.execute("SELECT * FROM roles WHERE id = ?", (role_id,)).fetchone()
            connection.commit()
        self.audit("rbac.role_created", actor.user_id, "role", role_id, {"name": name})
        return serialize_role_row(row)

    def update_role(self, role_id: str, name: str, permissions: list[str], actor: Principal) -> dict[str, Any]:
        with self.connect() as connection:
            connection.execute(
                "UPDATE roles SET name = ?, permissions = ?, updated_at = ? WHERE id = ?",
                (name.strip(), normalize_permissions(permissions), utcnow_iso(), role_id),
            )
            row = connection.execute("SELECT * FROM roles WHERE id = ?", (role_id,)).fetchone()
            if row is None:
                raise KeyError(role_id)
            connection.commit()
        self.audit("rbac.role_updated", actor.user_id, "role", role_id, {"name": name})
        return serialize_role_row(row)

    def delete_role(self, role_id: str, actor: Principal) -> None:
        with self.connect() as connection:
            assigned = connection.execute("SELECT COUNT(*) AS count FROM users WHERE role_id = ?", (role_id,)).fetchone()["count"]
            if assigned:
                raise ValueError("Role is assigned to one or more users")
            deleted = connection.execute("DELETE FROM roles WHERE id = ? AND id NOT IN ('admin')", (role_id,)).rowcount
            connection.commit()
        if not deleted:
            raise KeyError(role_id)
        self.audit("rbac.role_deleted", actor.user_id, "role", role_id)

    def list_users(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return [
                serialize_user_row(row)
                for row in connection.execute(
                    """
                    SELECT users.*, roles.name AS role_name
                    FROM users JOIN roles ON roles.id = users.role_id
                    ORDER BY users.name
                    """
                )
            ]

    def create_user(self, payload: dict[str, Any], actor: Principal) -> dict[str, Any]:
        user_id = f"user-{secrets.token_hex(8)}"
        now = utcnow_iso()
        password_hash = hash_password(str(payload["password"]))
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO users
                (id, username, name, email, role_id, status, password_hash, password_updated_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    str(payload["username"]).strip(),
                    str(payload["name"]).strip(),
                    str(payload["email"]).strip(),
                    str(payload["role_id"]),
                    str(payload.get("status", "Active")),
                    password_hash,
                    now,
                    now,
                    now,
                ),
            )
            row = connection.execute(
                """
                SELECT users.*, roles.name AS role_name
                FROM users JOIN roles ON roles.id = users.role_id
                WHERE users.id = ?
                """,
                (user_id,),
            ).fetchone()
            connection.commit()
        self.audit("rbac.user_created", actor.user_id, "user", user_id, {"username": payload["username"]})
        return serialize_user_row(row)

    def update_user(self, user_id: str, payload: dict[str, Any], actor: Principal) -> dict[str, Any]:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE users
                SET username = ?, name = ?, email = ?, role_id = ?, status = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    str(payload["username"]).strip(),
                    str(payload["name"]).strip(),
                    str(payload["email"]).strip(),
                    str(payload["role_id"]),
                    str(payload["status"]),
                    utcnow_iso(),
                    user_id,
                ),
            )
            row = connection.execute(
                """
                SELECT users.*, roles.name AS role_name
                FROM users JOIN roles ON roles.id = users.role_id
                WHERE users.id = ?
                """,
                (user_id,),
            ).fetchone()
            if row is None:
                raise KeyError(user_id)
            connection.commit()
        self.audit("rbac.user_updated", actor.user_id, "user", user_id, {"username": payload["username"]})
        return serialize_user_row(row)

    def set_user_password(self, user_id: str, password: str, actor: Principal) -> dict[str, Any]:
        now = utcnow_iso()
        with self.connect() as connection:
            connection.execute(
                "UPDATE users SET password_hash = ?, password_updated_at = ?, updated_at = ? WHERE id = ?",
                (hash_password(password), now, now, user_id),
            )
            row = connection.execute(
                """
                SELECT users.*, roles.name AS role_name
                FROM users JOIN roles ON roles.id = users.role_id
                WHERE users.id = ?
                """,
                (user_id,),
            ).fetchone()
            if row is None:
                raise KeyError(user_id)
            connection.commit()
        self.audit("rbac.password_set", actor.user_id, "user", user_id)
        return serialize_user_row(row)

    def reset_user_password_by_username(self, username: str, password: str) -> dict[str, Any]:
        now = utcnow_iso()
        with self.connect() as connection:
            connection.execute(
                "UPDATE users SET password_hash = ?, password_updated_at = ?, updated_at = ? WHERE username = ?",
                (hash_password(password), now, now, username),
            )
            row = connection.execute(
                """
                SELECT users.*, roles.name AS role_name
                FROM users JOIN roles ON roles.id = users.role_id
                WHERE users.username = ?
                """,
                (username,),
            ).fetchone()
            if row is None:
                raise KeyError(username)
            connection.commit()
        self.audit("rbac.password_reset_local", None, "user", row["id"], {"username": username})
        return serialize_user_row(row)

    def delete_user(self, user_id: str, actor: Principal) -> None:
        if user_id == actor.user_id:
            raise ValueError("Cannot delete the active user")
        with self.connect() as connection:
            deleted = connection.execute("DELETE FROM users WHERE id = ?", (user_id,)).rowcount
            connection.commit()
        if not deleted:
            raise KeyError(user_id)
        self.audit("rbac.user_deleted", actor.user_id, "user", user_id)

    def list_connections(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return [serialize_connection_row(row) for row in connection.execute("SELECT * FROM connections ORDER BY name")]

    def inventory_settings_from_connections(self) -> Settings:
        with self.connect() as connection:
            rows = list(connection.execute("SELECT * FROM connections ORDER BY type, name"))
        updates: dict[str, Any] = {"config_source": "admin-connections"}
        tls_modes: list[str] = []
        configured = False
        for row in rows:
            if not row["url"] or not row["username"] or not row["secret_ciphertext"]:
                continue
            try:
                password = unseal_secret(row["secret_ciphertext"], self.settings.auth_secret)
            except (ValueError, TypeError, binascii.Error):
                continue
            tls_modes.append(str(row["tls_mode"]))
            configured = True
            if row["type"] == "Prism Central" and not updates.get("pc_url"):
                updates |= {
                    "pc_url": row["url"],
                    "pc_username": row["username"],
                    "pc_password": password,
                }
            if row["type"] == "Prism Element" and not updates.get("pe_url"):
                updates |= {
                    "pe_url": row["url"],
                    "pe_username": row["username"],
                    "pe_password": password,
                }
        if not configured:
            return self.settings
        if "insecure_skip_verify" in tls_modes:
            updates["tls_mode"] = "insecure_skip_verify"
        return replace(self.settings, demo_mode=False, read_only_mode=True, enable_ncc=False, enable_ssh=False, **updates)

    def upsert_connection(self, payload: dict[str, Any], actor: Principal, connection_id: str | None = None) -> dict[str, Any]:
        now = utcnow_iso()
        target_id = connection_id or f"connection-{secrets.token_hex(8)}"
        secret_ciphertext = None
        if payload.get("password"):
            secret_ciphertext = seal_secret(str(payload["password"]), self.settings.auth_secret)
        with self.connect() as connection:
            existing = connection.execute("SELECT * FROM connections WHERE id = ?", (target_id,)).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO connections
                    (id, name, type, url, username, secret_ciphertext, tls_mode, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        target_id,
                        str(payload["name"]).strip(),
                        str(payload["type"]),
                        str(payload["url"]).strip(),
                        str(payload.get("username", "")).strip(),
                        secret_ciphertext,
                        str(payload.get("tls_mode", "strict")),
                        "Draft",
                        now,
                        now,
                    ),
                )
                action = "connections.created"
            else:
                connection.execute(
                    """
                    UPDATE connections
                    SET name = ?, type = ?, url = ?, username = ?,
                        secret_ciphertext = COALESCE(?, secret_ciphertext),
                        tls_mode = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        str(payload["name"]).strip(),
                        str(payload["type"]),
                        str(payload["url"]).strip(),
                        str(payload.get("username", "")).strip(),
                        secret_ciphertext,
                        str(payload.get("tls_mode", "strict")),
                        now,
                        target_id,
                    ),
                )
                action = "connections.updated"
            row = connection.execute("SELECT * FROM connections WHERE id = ?", (target_id,)).fetchone()
            connection.commit()
        self.audit(action, actor.user_id, "connection", target_id, {"type": payload["type"], "url": payload["url"]})
        return serialize_connection_row(row)

    def delete_connection(self, connection_id: str, actor: Principal) -> None:
        with self.connect() as connection:
            deleted = connection.execute("DELETE FROM connections WHERE id = ?", (connection_id,)).rowcount
            connection.commit()
        if not deleted:
            raise KeyError(connection_id)
        self.audit("connections.deleted", actor.user_id, "connection", connection_id)

    def test_connection(self, connection_id: str, actor: Principal) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM connections WHERE id = ?", (connection_id,)).fetchone()
            if row is None:
                raise KeyError(connection_id)
            status, details = probe_connection_row(row, self.settings.auth_secret)
            connection.execute(
                "UPDATE connections SET status = ?, last_checked_at = ?, updated_at = ? WHERE id = ?",
                (status, utcnow_iso(), utcnow_iso(), connection_id),
            )
            updated = connection.execute("SELECT * FROM connections WHERE id = ?", (connection_id,)).fetchone()
            connection.commit()
        self.audit("connections.tested", actor.user_id, "connection", connection_id, {"status": status, **details})
        return serialize_connection_row(updated)

    def audit(
        self,
        action: str,
        actor_id: str | None,
        target_type: str,
        target_id: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO audit_events (id, occurred_at, actor_id, action, target_type, target_id, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"audit-{secrets.token_hex(12)}",
                    utcnow_iso(),
                    actor_id,
                    action,
                    target_type,
                    target_id,
                    json.dumps(details or {}, sort_keys=True),
                ),
            )
            connection.commit()

    def list_audit_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return [
                serialize_audit_row(row)
                for row in connection.execute(
                    """
                    SELECT audit_events.*, users.username AS actor_username
                    FROM audit_events LEFT JOIN users ON users.id = audit_events.actor_id
                    ORDER BY audit_events.occurred_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            ]

    def list_schedules(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return [
                serialize_schedule_row(row)
                for row in connection.execute("SELECT * FROM schedules ORDER BY name")
            ]

    def list_schedule_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return [
                serialize_schedule_run_row(row)
                for row in connection.execute(
                    "SELECT * FROM schedule_runs ORDER BY started_at DESC LIMIT ?",
                    (limit,),
                )
            ]

    def get_schedule(self, schedule_id: str) -> ScheduleDefinition:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM schedules WHERE id = ?", (schedule_id,)).fetchone()
        if row is None:
            raise KeyError(schedule_id)
        return ScheduleDefinition.model_validate_json(row["definition_json"])

    def upsert_schedule(
        self,
        schedule: ScheduleDefinition,
        actor: Principal,
        schedule_id: str | None = None,
    ) -> dict[str, Any]:
        now = utcnow_iso()
        target_id = schedule_id or schedule.schedule_id
        schedule = schedule.model_copy(update={"schedule_id": target_id})
        with self.connect() as connection:
            existing = connection.execute("SELECT id FROM schedules WHERE id = ?", (target_id,)).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO schedules (id, name, enabled, definition_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        target_id,
                        schedule.name,
                        int(schedule.enabled),
                        schedule.model_dump_json(),
                        now,
                        now,
                    ),
                )
                action = "schedules.created"
            else:
                connection.execute(
                    """
                    UPDATE schedules
                    SET name = ?, enabled = ?, definition_json = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        schedule.name,
                        int(schedule.enabled),
                        schedule.model_dump_json(),
                        now,
                        target_id,
                    ),
                )
                action = "schedules.updated"
            row = connection.execute("SELECT * FROM schedules WHERE id = ?", (target_id,)).fetchone()
            connection.commit()
        self.audit(action, actor.user_id, "schedule", target_id, {"name": schedule.name})
        return serialize_schedule_row(row)

    def delete_schedule(self, schedule_id: str, actor: Principal) -> None:
        with self.connect() as connection:
            deleted = connection.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,)).rowcount
            connection.commit()
        if not deleted:
            raise KeyError(schedule_id)
        self.audit("schedules.deleted", actor.user_id, "schedule", schedule_id)

    def get_active_locks(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            connection.execute("DELETE FROM schedule_locks WHERE expires_at <= ?", (utcnow_iso(),))
            rows = list(connection.execute("SELECT * FROM schedule_locks ORDER BY expires_at"))
            connection.commit()
        return [serialize_schedule_lock_row(row) for row in rows]

    def has_schedule_run(self, idempotency_key: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id FROM schedule_runs WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
        return row is not None

    def create_schedule_run(
        self,
        *,
        idempotency_key: str,
        schedule_id: str,
        occurrence_at: str,
        target_cluster_ids: list[str],
        actor_id: str | None,
    ) -> dict[str, Any]:
        run_row_id = f"scheduled-run-{secrets.token_hex(8)}"
        now = utcnow_iso()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO schedule_runs
                (id, idempotency_key, schedule_id, occurrence_at, target_cluster_ids_json,
                 status, started_at, completed_at, run_id, evidence_path, message, actor_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_row_id,
                    idempotency_key,
                    schedule_id,
                    occurrence_at,
                    json.dumps(target_cluster_ids),
                    "RUNNING",
                    now,
                    None,
                    None,
                    None,
                    "Schedule runner started.",
                    actor_id,
                ),
            )
            row = connection.execute("SELECT * FROM schedule_runs WHERE id = ?", (run_row_id,)).fetchone()
            connection.commit()
        return serialize_schedule_run_row(row)

    def complete_schedule_run(
        self,
        run_row_id: str,
        *,
        status: str,
        run_id: str | None,
        evidence_path: str | None,
        message: str,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE schedule_runs
                SET status = ?, completed_at = ?, run_id = ?, evidence_path = ?, message = ?
                WHERE id = ?
                """,
                (status, utcnow_iso(), run_id, evidence_path, message, run_row_id),
            )
            row = connection.execute("SELECT * FROM schedule_runs WHERE id = ?", (run_row_id,)).fetchone()
            connection.commit()
        return serialize_schedule_run_row(row)

    def acquire_schedule_locks(
        self,
        *,
        owner_run_id: str,
        target_cluster_ids: list[str],
        expires_at: str,
    ) -> dict[str, list[str]]:
        acquired: list[str] = []
        blocked: list[str] = []
        now = utcnow_iso()
        with self.connect() as connection:
            connection.execute("DELETE FROM schedule_locks WHERE expires_at <= ?", (now,))
            for cluster_id in target_cluster_ids:
                existing = connection.execute(
                    "SELECT owner_run_id FROM schedule_locks WHERE cluster_id = ? AND expires_at > ?",
                    (cluster_id, now),
                ).fetchone()
                if existing:
                    blocked.append(cluster_id)
                    continue
                connection.execute(
                    "INSERT INTO schedule_locks (cluster_id, owner_run_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
                    (cluster_id, owner_run_id, expires_at, now),
                )
                acquired.append(cluster_id)
            connection.commit()
        return {"acquired": acquired, "blocked": blocked}

    def release_schedule_locks(self, owner_run_id: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM schedule_locks WHERE owner_run_id = ?", (owner_run_id,))
            connection.commit()

    def _init_db(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS roles (
                  id TEXT PRIMARY KEY,
                  name TEXT NOT NULL UNIQUE,
                  permissions TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS users (
                  id TEXT PRIMARY KEY,
                  username TEXT NOT NULL UNIQUE,
                  name TEXT NOT NULL,
                  email TEXT NOT NULL,
                  role_id TEXT NOT NULL REFERENCES roles(id),
                  status TEXT NOT NULL CHECK (status IN ('Active', 'Disabled')),
                  password_hash TEXT NOT NULL,
                  password_updated_at TEXT,
                  last_login_at TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                  token_hash TEXT PRIMARY KEY,
                  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                  created_at TEXT NOT NULL,
                  expires_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS connections (
                  id TEXT PRIMARY KEY,
                  name TEXT NOT NULL,
                  type TEXT NOT NULL CHECK (type IN ('Prism Central', 'Prism Element')),
                  url TEXT NOT NULL,
                  username TEXT NOT NULL DEFAULT '',
                  secret_ciphertext TEXT,
                  tls_mode TEXT NOT NULL DEFAULT 'strict',
                  status TEXT NOT NULL DEFAULT 'Draft',
                  last_checked_at TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                  id TEXT PRIMARY KEY,
                  occurred_at TEXT NOT NULL,
                  actor_id TEXT,
                  action TEXT NOT NULL,
                  target_type TEXT NOT NULL,
                  target_id TEXT NOT NULL,
                  details_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS schedules (
                  id TEXT PRIMARY KEY,
                  name TEXT NOT NULL,
                  enabled INTEGER NOT NULL,
                  definition_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS schedule_runs (
                  id TEXT PRIMARY KEY,
                  idempotency_key TEXT NOT NULL UNIQUE,
                  schedule_id TEXT NOT NULL,
                  occurrence_at TEXT NOT NULL,
                  target_cluster_ids_json TEXT NOT NULL,
                  status TEXT NOT NULL,
                  started_at TEXT NOT NULL,
                  completed_at TEXT,
                  run_id TEXT,
                  evidence_path TEXT,
                  message TEXT NOT NULL,
                  actor_id TEXT
                );
                CREATE TABLE IF NOT EXISTS schedule_locks (
                  cluster_id TEXT PRIMARY KEY,
                  owner_run_id TEXT NOT NULL,
                  expires_at TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                """
            )
            connection.commit()

    def _seed_defaults(self) -> None:
        now = utcnow_iso()
        with self.connect() as connection:
            for role_id, name, permissions in [
                ("viewer", "Viewer", "view_dashboard, view_evidence"),
                ("operator", "Operator", "view_dashboard, view_evidence, run_read_only_inventory, manage_schedules, plan_ncc_runs"),
                ("admin", "Admin", "all_permissions"),
            ]:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO roles (id, name, permissions, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (role_id, name, permissions, now, now),
                )
            connection.execute(
                """
                INSERT OR IGNORE INTO users
                (id, username, name, email, role_id, status, password_hash, password_updated_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "admin-user",
                    "admin",
                    "Lab Admin",
                    "admin@local",
                    "admin",
                    "Active",
                    hash_password(self.settings.bootstrap_admin_password),
                    now,
                    now,
                    now,
                ),
            )
            default_schedule = ScheduleDefinition(
                schedule_id="daily-standard-lab",
                name="Daily Standard Lab Preview",
                profile=default_profile(),
                target_cluster_ids=["no-lab-inventory"],
                recurrence="daily",
                start_time="06:00",
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO schedules (id, name, enabled, definition_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    default_schedule.schedule_id,
                    default_schedule.name,
                    int(default_schedule.enabled),
                    default_schedule.model_dump_json(),
                    now,
                    now,
                ),
            )
            connection.commit()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, digest_text = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_text)
        expected = base64.b64decode(digest_text)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations_text))
        return hmac.compare_digest(digest, expected)
    except (ValueError, TypeError):
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def seal_secret(secret: str, key: str) -> str:
    nonce = secrets.token_bytes(16)
    key_bytes = hashlib.sha256(key.encode("utf-8")).digest()
    stream = hashlib.pbkdf2_hmac("sha256", nonce, key_bytes, 32, dklen=len(secret.encode("utf-8")))
    ciphertext = bytes(a ^ b for a, b in zip(secret.encode("utf-8"), stream, strict=True))
    tag = hmac.new(key_bytes, nonce + ciphertext, hashlib.sha256).digest()
    return base64.b64encode(nonce + tag + ciphertext).decode("ascii")


def unseal_secret(sealed: str, key: str) -> str:
    payload = base64.b64decode(sealed.encode("ascii"))
    nonce = payload[:16]
    tag = payload[16:48]
    ciphertext = payload[48:]
    key_bytes = hashlib.sha256(key.encode("utf-8")).digest()
    expected_tag = hmac.new(key_bytes, nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected_tag):
        raise ValueError("Secret authentication failed")
    stream = hashlib.pbkdf2_hmac("sha256", nonce, key_bytes, 32, dklen=len(ciphertext))
    return bytes(a ^ b for a, b in zip(ciphertext, stream, strict=True)).decode("utf-8")


def probe_connection_row(row: sqlite3.Row, auth_secret: str) -> tuple[str, dict[str, Any]]:
    if row["type"] not in {"Prism Central", "Prism Element"}:
        return "UNSUPPORTED", {"reason": "Unsupported connection type"}
    if not row["url"] or not row["username"] or not row["secret_ciphertext"]:
        return "INCOMPLETE", {"reason": "URL, username and password are required"}
    try:
        password = unseal_secret(row["secret_ciphertext"], auth_secret)
    except (ValueError, TypeError, binascii.Error):
        return "AUTH_FAILED", {"reason": "Stored secret could not be opened"}

    method, url, body = connection_probe_request(row)
    credential = f"{row['username']}:{password}".encode("utf-8")
    headers = {
        "Accept": "application/json, text/plain;q=0.8, */*;q=0.1",
        "Authorization": "Basic " + base64.b64encode(credential).decode("ascii"),
        "User-Agent": "ClusterAssuranceOrchestrator/0.1 connection-probe",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    context = ssl._create_unverified_context() if row["tls_mode"] == "insecure_skip_verify" else ssl.create_default_context()
    started = perf_counter()
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=10, context=context) as response:
            status_code = response.status
    except HTTPError as error:
        status_code = error.code
    except ssl.SSLError as error:
        return "TLS_FAILED", {"error": type(error).__name__}
    except (TimeoutError, URLError, OSError) as error:
        reason = getattr(error, "reason", None)
        if isinstance(reason, ssl.SSLError):
            return "TLS_FAILED", {"error": type(reason).__name__}
        return "UNREACHABLE", {"error": type(error).__name__}

    elapsed_ms = int((perf_counter() - started) * 1000)
    if 200 <= status_code < 400:
        return "READY", {"status_code": status_code, "elapsed_ms": elapsed_ms}
    if status_code in {401, 403}:
        return "AUTH_FAILED", {"status_code": status_code, "elapsed_ms": elapsed_ms}
    if status_code in {404, 405}:
        return "UNSUPPORTED", {"status_code": status_code, "elapsed_ms": elapsed_ms}
    return "UNREACHABLE", {"status_code": status_code, "elapsed_ms": elapsed_ms}


def connection_probe_request(row: sqlite3.Row) -> tuple[str, str, bytes | None]:
    base_url = str(row["url"]).rstrip("/") + "/"
    body = json.dumps({"kind": "cluster", "length": 1, "offset": 0}).encode("utf-8")
    return "POST", base_url + "api/nutanix/v3/clusters/list", body


def parse_permissions(value: str) -> list[str]:
    return [permission.strip() for permission in value.split(",") if permission.strip()]


def normalize_permissions(permissions: list[str]) -> str:
    clean = [permission.strip() for permission in permissions if permission.strip()]
    return ", ".join(dict.fromkeys(clean))


def serialize_role_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "permissions": parse_permissions(row["permissions"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def serialize_user_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "username": row["username"],
        "name": row["name"],
        "email": row["email"],
        "role_id": row["role_id"],
        "role_name": row["role_name"],
        "status": row["status"],
        "password_set": bool(row["password_hash"]),
        "password_updated_at": row["password_updated_at"],
        "last_login_at": row["last_login_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def serialize_connection_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "url": row["url"],
        "username": row["username"],
        "secret_set": bool(row["secret_ciphertext"]),
        "tls_mode": row["tls_mode"],
        "status": row["status"],
        "last_checked_at": row["last_checked_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def serialize_audit_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "occurred_at": row["occurred_at"],
        "actor_id": row["actor_id"],
        "actor_username": row["actor_username"],
        "action": row["action"],
        "target_type": row["target_type"],
        "target_id": row["target_id"],
        "details": json.loads(row["details_json"]),
    }


def serialize_schedule_row(row: sqlite3.Row) -> dict[str, Any]:
    schedule = ScheduleDefinition.model_validate_json(row["definition_json"])
    return {
        "id": row["id"],
        "name": row["name"],
        "enabled": bool(row["enabled"]),
        "definition": schedule.model_dump(mode="json"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def serialize_schedule_run_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "idempotency_key": row["idempotency_key"],
        "schedule_id": row["schedule_id"],
        "occurrence_at": row["occurrence_at"],
        "target_cluster_ids": json.loads(row["target_cluster_ids_json"]),
        "status": row["status"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "run_id": row["run_id"],
        "evidence_path": public_artifact_ref(row["evidence_path"]),
        "message": row["message"],
        "actor_id": row["actor_id"],
    }


def serialize_schedule_lock_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "cluster_id": row["cluster_id"],
        "owner_run_id": row["owner_run_id"],
        "expires_at": row["expires_at"],
        "created_at": row["created_at"],
    }


def utcnow() -> datetime:
    return datetime.now(UTC)


def utcnow_iso() -> str:
    return utcnow().isoformat()
