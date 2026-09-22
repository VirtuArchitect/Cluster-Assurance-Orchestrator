from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import load_settings
from app.services.inventory_run import hash_file, run_inventory, write_inventory_evidence


def main() -> None:
    parser = argparse.ArgumentParser(description="Run read-only lab inventory collection.")
    parser.add_argument(
        "--env-file",
        default="config/local.env",
        help="Path to ignored local env file. Defaults to config/local.env.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print the inventory report without writing a summary evidence artifact.",
    )
    args = parser.parse_args()

    settings = load_settings(Path(args.env_file))
    report = run_inventory(settings)

    if args.no_write:
        print(json.dumps(report.api_dict(), indent=2, sort_keys=True))
        return

    evidence_path = write_inventory_evidence(report, settings.evidence_dir)
    print(
        json.dumps(
            {
                "evidencePath": str(evidence_path),
                "sha256": hash_file(evidence_path),
                "status": report.status,
                "clusterCount": len(report.clusters),
                "collectorStates": {
                    collector.endpoint_alias: collector.status for collector in report.collectors
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

