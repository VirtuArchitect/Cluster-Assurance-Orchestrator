from __future__ import annotations

from hashlib import sha256
from pathlib import Path


def write_raw_artifact(
    evidence_dir: str | Path,
    run_id: str,
    source: str,
    name: str,
    body: bytes,
) -> tuple[Path, str]:
    artifact_hash = sha256(body).hexdigest()
    target_dir = Path(evidence_dir) / "raw" / run_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{source}-{name}-{artifact_hash[:12]}.json"
    target.write_bytes(body)
    return target, artifact_hash


def hash_file(path: str | Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def public_artifact_ref(path: str | Path | None) -> str | None:
    if not path:
        return None
    return Path(str(path)).name or "local-evidence-artifact"
