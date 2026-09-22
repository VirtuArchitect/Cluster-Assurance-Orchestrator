from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path

from app.core.config import load_settings
from app.services.admin_store import AdminStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset a local admin/RBAC user password.")
    parser.add_argument("--username", default="admin", help="Username to reset.")
    parser.add_argument("--env-file", default="", help="Optional local env file to load.")
    args = parser.parse_args()

    password = os.environ.get("CAO_ADMIN_RESET_PASSWORD")
    if not password:
        password = getpass.getpass("New password: ")
    if not password:
        raise SystemExit("Password cannot be empty")

    settings = load_settings(Path(args.env_file) if args.env_file else None)
    user = AdminStore(settings).reset_user_password_by_username(args.username, password)
    print(f"Reset password for {user['username']} in {settings.admin_db_path or Path(settings.evidence_dir) / 'cao-admin.sqlite3'}")


if __name__ == "__main__":
    main()
