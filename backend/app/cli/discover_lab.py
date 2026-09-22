from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import load_settings
from app.services.lab_discovery import hash_file, run_lab_discovery, write_discovery_evidence


def main() -> None:
    parser = argparse.ArgumentParser(description="Run read-only lab discovery probes.")
    parser.add_argument(
        "--env-file",
        default="config/local.env",
        help="Path to ignored local env file. Defaults to config/local.env.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print the redacted report without writing an evidence artifact.",
    )
    args = parser.parse_args()

    settings = load_settings(Path(args.env_file))
    report = run_lab_discovery(settings)

    if args.no_write:
        print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
        return

    evidence_path = write_discovery_evidence(report, settings.evidence_dir)
    print(
        json.dumps(
            {
                "evidencePath": str(evidence_path),
                "sha256": hash_file(evidence_path),
                "endpointStates": {
                    endpoint.alias: endpoint.state for endpoint in report.endpoints
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

