"""Release identity; deployment health and production approval are separate."""
import json
from pathlib import Path

_RELEASE = json.loads(Path(__file__).with_name("release.json").read_text(encoding="utf-8"))
VERSION = _RELEASE["version"]
__version__ = _RELEASE["python_version"]


def build_identity() -> dict:
    path = Path(__file__).with_name("build-info.json")
    built = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {**_RELEASE, "revision": built.get("revision", "unknown"),
            "built_at": built.get("built_at", "unknown"),
            "source_state": built.get("source_state", "unknown")}
