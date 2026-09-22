from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import load_settings
from app.services.evidence_schema import (
    format_schema_report,
    inspect_evidence_schema,
    inspect_latest_evidence_schema,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect saved Prism evidence artifacts and summarize observed JSON shapes."
    )
    parser.add_argument(
        "--env-file",
        default="config/local.env",
        help="Path to local env file used to resolve the evidence directory.",
    )
    parser.add_argument(
        "--evidence-file",
        help="Inspect a specific inventory-run JSON file instead of the latest evidence in the configured directory.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of a text report.",
    )
    args = parser.parse_args()

    if args.evidence_file:
        report = inspect_evidence_schema(Path(args.evidence_file))
    else:
        settings = load_settings(Path(args.env_file))
        report = inspect_latest_evidence_schema(settings.evidence_dir)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_schema_report(report), end="")


if __name__ == "__main__":
    main()
